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

from pipeline.filtering import deadline_filter, relevance_filter
from pipeline.filtering.deadline_filter import DeadlineExtractor
from pipeline.filtering.relevance_filter import RelevanceFilter
from pipeline.filtering.page_classifier import is_listing_page

from pipeline.enrichment.metadata_extractor import extract_domain
from pipeline.enrichment.content_fetcher import fetch_raw, extract_text

from repositories.edital_repository import EditalRepository

from utils.url_utils import url_id

MAX_RAW_RESULTS = 50
RELEVANCE_THRESHOLD = 3
SCORE_THRESHOLD = 2

def current_config() -> dict:
    """Pesos e limiares vigentes, gravados no manifest de cada coleta"""

    return {
        "relevance_threshold": RELEVANCE_THRESHOLD,
        "score_threshold": SCORE_THRESHOLD,
        "relevance_keywords": relevance_filter.KEYWORDS,
        "relevance_negative_keywords": relevance_filter.NEGATIVE_KEYWORDS,
        "deadline_keywords": deadline_filter.KEYWORDS,
        "deadline_negative_keywords": deadline_filter.NEGATIVE_KEYWORDS,
        "deadline_keyword_weight": deadline_filter.DEADLINE_KEYWORD_WEIGHT,
        "deadline_negative_keyword_weight": deadline_filter.NEGATIVE_KEYWORD_WEIGHT,
        "ate_weight": deadline_filter.ATE_WEIGHT,
        "encerramento_weight": deadline_filter.ENCERRAMENTO_WEIGHT,
    }

class EditalPipeline:

    def __init__(self, persist: bool = True):
        self.persist = persist
        self.repository = EditalRepository() if persist else None
        self.relevance_filter = RelevanceFilter()

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
            new_run_dir(run_at), run_at, executed_queries, items, current_config()
        )

    # PROCESSAMENTO
    def process(self, snapshot: dict) -> list[Edital]:
        run_dir: Path = snapshot["run_dir"]

        deadline_extractor = DeadlineExtractor(today=snapshot["run_at"])
        seen_signatures = set()
        saved_contents = []

        evaluation_log = []
        valid_editais = []

        for item in snapshot["items"]:
            url = item["url"]
            content = item["snippet"]

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

            full_content = extract_text(read_raw(run_dir, item))

            if len(full_content) > len(content):
                content = full_content
                evaluation_entry["content_source"] = "full"

            # Evita duplicados no banco
            if self.persist and self.repository.exists_by_url(url):
                evaluation_entry["reason"] = "url_duplicada"
                evaluation_log.append(evaluation_entry)
                continue

            print(f"\n[PROCESSANDO]")
            print(f"[URL]: {url}")

            # Detecta páginas agregadoras
            if is_listing_page(url, content):
                print("[LISTING PAGE]")

                evaluation_entry["reason"] = "listing_page"

                evaluation_log.append(evaluation_entry)
                continue

            # Relevância
            relevance = self.relevance_filter.is_relevant(
                content, threshold=RELEVANCE_THRESHOLD
            )

            evaluation_entry["relevance_pred"] = relevance["is_relevant"]
            evaluation_entry["relevance_score"] = relevance["score"]

            if not relevance["is_relevant"]:
                print("[NOT RELEVANT]")

                evaluation_entry["reason"] = "not_relevant"

                evaluation_log.append(evaluation_entry)
                continue

            score = relevance["score"]
            print(f"[SCORE]: {score}")

            if score < SCORE_THRESHOLD:
                print("[LOW SCORE]")

                evaluation_entry["reason"] = "low_score"

                evaluation_log.append(evaluation_entry)
                continue

            # Deadline
            result = deadline_extractor.extract_deadline(content)

            deadline = result["deadline"]
            expired_flag = result.get("expired", False)

            evaluation_entry["source_sentence"] = result.get("source_sentence")

            # FALLBACK
            if not deadline:
                fallback_result = deadline_extractor.extract_deadline(content[:2000])

                evaluation_entry["used_fallback"] = True

                deadline = fallback_result["deadline"]

                expired_flag = (
                    expired_flag
                    or fallback_result.get("expired", False)
                )

                if fallback_result.get("source_sentence"):
                    evaluation_entry["source_sentence"] = fallback_result.get("source_sentence")

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
            signature = generate_signature(content)

            if signature in seen_signatures:
                print("[DUPLICATE SIGNATURE]")

                evaluation_entry["reason"] = "duplicate_signature"

                evaluation_log.append(evaluation_entry)
                continue

            seen_signatures.add(signature)

            # Deduplicação por Similaridade de Jaccard
            is_duplicate = False

            for existing in saved_contents:
                sim = jaccard_similarity(content[:1000], existing[:1000])

                if sim > 0.8:
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

        output_file = run_dir / "predictions.csv"
        self._write_evaluation_log(evaluation_log, output_file)

        print(f"\nAvaliação salva em: {output_file}")
        print(f"Editais válidos: {len(valid_editais)}/{len(snapshot['items'])}")

        return valid_editais

    def _write_evaluation_log(self, evaluation_log: list[disct], output_file: Path):
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