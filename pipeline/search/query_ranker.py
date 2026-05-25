from pipeline.search.query_storage import load_stats

# Ano configurável em tempo de execução pela web app
YEAR: str = "2026"


def score_query(query: str, stats: dict) -> int:
    score = 0

    if "site:" in query:
        score += 3
    if YEAR in query:
        score += 2
    if "edital" in query:
        score += 2
    if "inscrições abertas" in query:
        score += 1

    # Histórico de performance da query
    if query in stats:
        score += stats[query].get("score", 0)

    return score


def prioritize_queries(queries: list[str]) -> list[str]:
    stats = load_stats()

    return sorted(
        queries,
        key=lambda q: score_query(q, stats),
        reverse=True,
    )
