import re

LISTING_KEYWORDS = [
    "editais",
    "oportunidades",
    "noticias",
    "notícias",
    "chamadas",
    "bolsas",
    "programas",
    "arquivo",
    "resultados",
    "catalogo",
    "catálogo",
    "lista",
    "todas-as-chamadas",
    "todas-as-oportunidades",
]

DETAIL_KEYWORDS = [
    "chamada pública",
    "edital",
    "nº",
    "numero",
    "inscrição",
    "prazo",
    "submissão",
    "cronograma",
]

LISTING_URL_PATTERNS = [
    "/noticias/",
    "/notícias/",
    "/oportunidades/",
    "/editais-2026",
    "/editais/",
    "/chamadas/",
    "/bolsas/",
    "/programas/",
    "/resultados/",
]

# Padrão de URL markdown: [texto](https://...) — indica página agregadora
_MARKDOWN_LINK_RE = re.compile(r'\[([^\]]+)\]\(https?://[^\)]+\)')

# Datas no formato dd/mm/aaaa ou dd/mm/aa
_DATE_RE = re.compile(r'\d{1,2}/\d{1,2}/\d{2,4}')


def is_listing_page(url: str, content: str) -> bool:
    """
    Detecta páginas agregadoras (listas de editais) que não devem ser
    processadas individualmente.

    O conteúdo recebido é texto limpo extraído pelo Tavily — não HTML —
    portanto a contagem de 'href=' não é aplicável aqui. Em vez disso,
    contamos links em formato Markdown ([texto](url)), que é como o Tavily
    representa hiperlinks no texto extraído.
    """
    url_lower = url.lower()
    content_lower = content.lower()

    listing_score = 0

    # Heurística por URL
    if any(k in url_lower for k in LISTING_KEYWORDS):
        listing_score += 2
    if any(p in url_lower for p in LISTING_URL_PATTERNS):
        listing_score += 3

    # Links em formato Markdown no conteúdo (indicativo de lista)
    link_count = len(_MARKDOWN_LINK_RE.findall(content))
    if link_count > 10:
        listing_score += 2
    if link_count > 25:
        listing_score += 2

    # Muitas datas — provável calendário ou lista
    date_matches = _DATE_RE.findall(content_lower)
    if len(date_matches) > 5:
        listing_score += 2
    if len(date_matches) > 10:
        listing_score += 2

    # Poucas palavras-chave de edital individual
    detail_hits = sum(content_lower.count(k) for k in DETAIL_KEYWORDS)
    if detail_hits < 2:
        listing_score += 2

    # Plurais indicativos de listagem
    if "editais" in content_lower:
        listing_score += 1
    if "chamadas públicas" in content_lower:
        listing_score += 1

    return listing_score >= 5
