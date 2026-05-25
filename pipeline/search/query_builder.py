# Variáveis mutáveis em nível de módulo — alteráveis pela web app em tempo de execução
TOPICS: list[str] = [
    "inovação",
    "tecnologia",
    "agro",
    "startup",
]


def prioritize_queries(queries: list[str]) -> list[str]:
    # Queries com "site:" primeiro (mais direcionadas), mantendo ordem estável
    return sorted(queries, key=lambda q: "site:" not in q)


def generate_queries() -> list[str]:
    base_terms = [
        "edital",
        "chamada pública",
        "bolsa pesquisa",
        "financiamento inovação",
    ]

    domains = [
        "site:gov.br",
        "site:fapesp.br",
        "site:cnpq.br",
        "site:capes.gov.br",
    ]

    from pipeline.search.query_ranker import YEAR
    time_terms = [YEAR, "aberto", "inscrições abertas"]

    queries = []

    # Queries direcionadas por domínio
    for base in base_terms:
        for domain in domains:
            queries.append(f"{base} {domain} {YEAR}")

    # Queries temáticas usando os tópicos configuráveis
    for topic in TOPICS:
        queries.append(f"edital {topic} Brasil {YEAR}")
        queries.append(f"chamada pública {topic} inscrições abertas")

    # Queries regionais
    queries.extend([
        "edital inovação Espírito Santo 2026",
        "chamada pública tecnologia Sudeste Brasil",
    ])

    # Remove duplicatas preservando ordem (dict mantém inserção no Python 3.7+)
    queries = list(dict.fromkeys(queries))

    # Prioriza ANTES de cortar — garante que as melhores queries não sejam descartadas
    queries = prioritize_queries(queries)

    return queries[:20]
