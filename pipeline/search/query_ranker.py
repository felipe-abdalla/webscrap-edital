from datetime import datetime
from zoneinfo import ZoneInfo

from pipeline.search.query_storage import load_stats

_TZ = ZoneInfo("America/Sao_Paulo")


def current_year() -> str:
    """Ano de referência das consultas: o ano corrente no horário de Brasília.
    É calculado a cada chamada, para que um servidor que fique no ar durante
    a virada do ano passe a usar o novo ano sem ser reiniciado."""
    return str(datetime.now(_TZ).year)


def score_query(query: str, stats: dict) -> int:
    score = 0

    if "site:" in query:
        score += 3
    if current_year() in query:
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
