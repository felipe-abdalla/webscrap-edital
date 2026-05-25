import json

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
from pipeline.enrichment.content_fetcher import fetch_full_content

from repositories.edital_repository import EditalRepository

class EditalPipeline:

    def __init__(self):
        self.repository = EditalRepository()
        self.relevance_filter = RelevanceFilter()
        self.deadline_extractor = DeadlineExtractor()
        self.seen_signatures = set()
        self.saved_contents = []

    def run(self):
        queries = generate_queries()
        queries = prioritize_queries(queries)
        all_results = []
        score_threshold = 2
        evaluation_log = []

        # Search
        for q in queries:
            results = search_api(q)

            if not results:
                continue

            update_query_stats(q, results)    
            all_results.extend(results)

            if len(all_results) >= 50:
                break

        print(f"\nResultados brutos: {len(all_results)}")

        # Deduplicate
        unique_results = deduplicate(all_results)

        print(f"Após deduplicação: {len(unique_results)}")

        valid_editais = []

        for r in unique_results:
            url = r.get("url")
            content = r.get("content", "")

            evaluation_entry = {
                "url": url,
                "title": r.get("title"),

                "pipeline_detected": False,

                "relevance_pred": None,
                "relevance_score": None,

                "deadline_pred": None,
                "expired_detected": None,

                "used_fallback": False,
                "reason": None,

                "source_sentence": None,

                "is_edital_real": None,
                "is_relevant_real": None,

                "deadline_status_real": None
            }

            full_content = fetch_full_content(url)

            if len(full_content) > len(content):
                content = full_content

            # Evita duplicados no banco
            if self.repository.exists_by_url(url):
                evaluation_entry["reason"] = "url_duplicada"
                evaluation_log.append(evaluation_entry)
                continue
            
            print(f"\n[PROCESSANDO]")
            print(f"[URL]: {url}")

            # Detecta páginas agregadoras
            if is_listing_page(url, content):
                print("[LISTING PAGE]")

                evaluation_entry["pipeline_detected"] = False

                evaluation_entry["relevance_pred"] = None
                evaluation_entry["relevance_score"] = None

                evaluation_entry["deadline_pred"] = None
                evaluation_entry["expired_detected"] = None

                evaluation_entry["reason"] = "listing_page"

                evaluation_log.append(evaluation_entry)
                continue

            # Relevância
            relevance = self.relevance_filter.is_relevant(content)

            evaluation_entry["relevance_pred"] = relevance["is_relevant"]
            evaluation_entry["relevance_score"] = relevance["score"]

            if not relevance["is_relevant"]:
                print("[NOT RELEVANT]")

                evaluation_entry["deadline_pred"] = None
                evaluation_entry["expired_detected"] = None

                evaluation_entry["reason"] = "not_relevant"

                evaluation_log.append(evaluation_entry)
                continue


            score = relevance["score"]
            print(f"[SCORE]: {score}")

            if score < score_threshold:
                print("[LOW SCORE]")

                evaluation_entry["deadline_pred"] = None
                evaluation_entry["expired_detected"] = None

                evaluation_entry["reason"] = "low_score"

                evaluation_log.append(evaluation_entry)
                continue

            # Deadline
            result = self.deadline_extractor.extract_deadline(content)

            deadline = result["deadline"]
            expired_flag = result.get("expired", False)

            evaluation_entry["source_sentence"] = result.get("source_sentence")

            # FALLBACK
            if not deadline:
                fallback_result = self.deadline_extractor.extract_deadline(content[:2000])

                evaluation_entry["used_fallback"] = True

                deadline = fallback_result["deadline"]

                expired_flag = (
                    expired_flag or
                    fallback_result.get("expired", False)
                )

                if fallback_result.get("source_sentence"):
                    evaluation_entry["source_sentence"] = fallback_result.get("source_sentence")


            evaluation_entry["deadline_pred"] = deadline is not None
            evaluation_entry["expired_detected"] = expired_flag

            # Sem deadline válido
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

            if signature in self.seen_signatures:
                print("[DUPLICATE SIGNATURE]")

                evaluation_entry["reason"] = "duplicate_signature"

                evaluation_log.append(evaluation_entry)
                continue

            self.seen_signatures.add(signature)

            is_duplicate = False

            for existing in self.saved_contents:
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
                title=r.get("title"),
                url=url,
                content=content,
                deadline=deadline,
                domain=domain,
                score=score,
                # DEBUG
                phrase=sentence,
            )

            self.repository.save(edital)
            self.saved_contents.append(content)
            
            evaluation_entry["pipeline_detected"] = True
            evaluation_entry["deadline"] = deadline.isoformat()
            
            evaluation_entry["reason"] = "accepted"

            evaluation_log.append(evaluation_entry)

            valid_editais.append(edital)

        print(f"Editais válidos: {len(valid_editais)}/{len(unique_results)}")
        with open("evaluation_raw.json", "w", encoding="utf-8") as f:
            json.dump(evaluation_log, f, indent=2, ensure_ascii=False)

        return valid_editais