import csv
from datetime import datetime
from pathlib import Path

from domain.edital import Edital

from pipeline.search.search_service import search_api
from pipeline.search.query_builder import generate_queries
from pipeline.search.query_ranker import prioritize_queries
from pipeline.search.query_feedback import update_query_stats

from pipeline.processing.deduplicator import deduplicate
from pipeline.processing.content_signature import generate_signature
from pipeline.processing.similarity import jaccard_similarity

from pipeline.filtering.deadline_filter import DeadlineExtractor
from pipeline.filtering.relevance_filter import RelevanceFilter
from pipeline.filtering.page_classifier import is_listing_page

from pipeline.enrichment.metadata_extractor import extract_domain
from pipeline.enrichment.content_fetcher import fetch_raw, extract_text

from pipeline.snapshot import new_run_dir, save_snapshot, read_raw

from repositories.edital_repository import EditalRepository

from utils.url_utils import url_id

from config.heuristics import DEFAULT, HeuristicConfig

MAX_RAW_RESULTS = 50

def item_content(run_dir: Path, item: dict) -> tuple[str, str]:
    """Texto usado nas heurísticas"""

    content = item["snippet"]
    full_content = extract_text(read_raw(run_dir, item))

    if len(full_content) > len(content):
        return full_content, "full"

    return content, "snippet"

def find_deadline(extractor: DeadlineExtractor, content: str, fallback_window: int) -> dict:
    result = extractor.extract_deadline(content)

    found = {
        "deadline": result["deadline"],
        "expired": result.get("expired", False),
        "source_sentence": result.get("source_sentence"),
        "best_any_date": result.get("best_any_date"),
        "used_fallback": False,
    }

    # FALLBACK
    if not found["deadline"]:
        fallback = extractor.extract_deadline(content[:fallback_window])

        found["used_fallback"] = True
        found["deadline"] = fallback["deadline"]
        found["expired"] = found["expired"] or fallback.get("expired", False)
        found["best_any_date"] = found["best_any_date"] or fallback.get("best_any_date")

        if fallback.get("source_sentence"):
            found["source_sentence"] = fallback["source_sentence"]

    return found

class EditalPipeline:

    def __init__(self, persist: bool = True, cfg: HeuristicConfig = DEFAULT):
        self.cfg = cfg
        self.persist = persist
        self.repository = EditalRepository() if persist else None
        self.relevance_filter = RelevanceFilter(cfg.relevance)

    def run(self):
        return self.process(self.collect())

    # COLETA
    def collect(self) -> dict:
        run_at = datetime.now().astimezone()

        queries = generate_queries()
        queries = prioritize_queries(queries)

        all_results = []
        executed_queries = []

        # Busca
        for q in queries:
            executed_queries.append(q)
            results = search_api(q)

            if not results:
                continue

            update_query_stats(q, results)

            for r in results:
                r["query"] = q

            all_results.extend(results)

            if len(all_results) >= MAX_RAW_RESULTS:
                break

        print(f"\nResultados brutos: {len(all_results)}")

        # Deduplicação
        unique_results = deduplicate(all_results)

        print(f"Após deduplicação: {len(unique_results)}")

        items = []

        for r in unique_results:
            url = r.get("url")

            items.append({
                "id": url_id(url),
                "url": url,
                "title": r.get("title"),
                "query": r.get("query"),
                "snippet": r.get("content") or "",
                "raw": fetch_raw(url),
            })

        return save_snapshot(
            new_run_dir(run_at), run_at, executed_queries, items, self.cfg.to_dict()
        )

    # PROCESSAMENTO
    def process(self, snapshot: dict, output_file: Path | None = None) -> list[Edital]:
        run_dir: Path = snapshot["run_dir"]
        output_file = output_file or run_dir / "predictions.csv"
        cfg = self.cfg

        deadline_extractor = DeadlineExtractor(today=snapshot["run_at"], cfg=cfg.deadline)
        seen_signatures = set()
        saved_contents = []

        evaluation_log = []
        valid_editais = []

        for item in snapshot["items"]:
            url = item["url"]

            evaluation_entry = {
                "id": item["id"],
                "url": url,
                "title": item["title"],
                "content_source": "snippet",
                "pipeline_detected": False,
                "relevance_pred": None,
                "relevance_score": None,
                "deadline_pred": None,
                "expired_detected": None,
                "used_fallback": False,
                "reason": None,
                "source_sentence": None,
            }

            content, evaluation_entry["content_source"] = item_content(run_dir, item)

            # Evita duplicados no banco
            if self.persist and self.repository.exists_by_url(url):
                evaluation_entry["reason"] = "url_duplicada"
                evaluation_log.append(evaluation_entry)
                continue

            print(f"\n[PROCESSANDO]")
            print(f"[URL]: {url}")

            # Detecta páginas agregadoras
            if is_listing_page(url, content, cfg.listing):
                print("[LISTING PAGE]")

                evaluation_entry["reason"] = "listing_page"

                evaluation_log.append(evaluation_entry)
                continue

            # Relevância
            relevance = self.relevance_filter.is_relevant(content)

            evaluation_entry["relevance_pred"] = relevance["is_relevant"]
            evaluation_entry["relevance_score"] = relevance["score"]

            if not relevance["is_relevant"]:
                print("[NOT RELEVANT]")

                evaluation_entry["reason"] = "not_relevant"

                evaluation_log.append(evaluation_entry)
                continue

            score = relevance["score"]
            print(f"[SCORE]: {score}")

            if score < cfg.relevance.score_threshold:
                print("[LOW SCORE]")

                evaluation_entry["reason"] = "low_score"

                evaluation_log.append(evaluation_entry)
                continue

            # Deadline
            found = find_deadline(deadline_extractor, content, cfg.deadline.fallback_window)

            deadline = found["deadline"]
            expired_flag = found["expired"]

            evaluation_entry["source_sentence"] = found["source_sentence"]
            evaluation_entry["used_fallback"] = found["used_fallback"]

            evaluation_entry["deadline_pred"] = deadline is not None
            evaluation_entry["expired_detected"] = expired_flag

            # Sem deadline valida
            if not deadline:

                if expired_flag:
                    print("[EXPIRED DEADLINE]")
                    evaluation_entry["reason"] = "expired_deadline"

                else:
                    print("[NO DEADLINE]")
                    evaluation_entry["reason"] = "no_deadline"

                evaluation_log.append(evaluation_entry)
                continue

            # Deduplicação por assinatura hash
            signature = generate_signature(content, cfg.dedup.signature_window)

            if signature in seen_signatures:
                print("[DUPLICATE SIGNATURE]")

                evaluation_entry["reason"] = "duplicate_signature"

                evaluation_log.append(evaluation_entry)
                continue

            seen_signatures.add(signature)

            # Deduplicação por Similaridade de Jaccard
            is_duplicate = False

            for existing in saved_contents:
                w = cfg.dedup.jaccard_window
                sim = jaccard_similarity(content[:w], existing[:w])

                if sim > cfg.dedup.jaccard_threshold:
                    print(f"[DUPLICATE (SIMILARITY {sim:.2f})]")

                    evaluation_entry["reason"] = f"duplicate_similarity_{sim:.2f}"

                    evaluation_log.append(evaluation_entry)

                    is_duplicate = True
                    break

            if is_duplicate:
                continue

            sentence = evaluation_entry["source_sentence"]

            print(f"[DEADLINE]: {deadline}")
            print(f"[FRASE]: {sentence}")

            # Enriquecimento de dados
            domain = extract_domain(url)

            # Criação do objeto
            edital = Edital(
                title=item["title"],
                url=url,
                content=content,
                deadline=deadline,
                domain=domain,
                score=score,
                phrase=sentence,
            )

            if self.persist:
                self.repository.save(edital)

            saved_contents.append(content)

            evaluation_entry["pipeline_detected"] = True
            evaluation_entry["deadline"] = deadline.isoformat()
            evaluation_entry["reason"] = "accepted"

            evaluation_log.append(evaluation_entry)
            valid_editais.append(edital)

        self._write_evaluation_log(evaluation_log, output_file)

        print(f"\nAvaliação salva em: {output_file}")
        print(f"Editais válidos: {len(valid_editais)}/{len(snapshot['items'])}")

        return valid_editais

    def _write_evaluation_log(self, evaluation_log: list[dict], output_file: Path):
        if not evaluation_log:
            return

        # Obtem os headers
        fieldnames = []

        for entry in evaluation_log:
            for key in entry.keys():
                if key not in fieldnames:
                    fieldnames.append(key)

        # utf-8-sig
        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
                delimiter=",",
                extrasaction="ignore",
            )

            writer.writeheader()
            writer.writerows(evaluation_log)