import re
from config.heuristics import DEFAULT, ListingConfig

# Datas no formato dd/mm/aaaa ou dd/mm/aa
_DATE_RE = re.compile(r'\d{1,2}/\d{1,2}/\d{2,4}')

def listing_score(url: str, content: str, cfg: ListingConfig = DEFAULT.listing) -> int:
    url_lower = url.lower()
    content_lower = content.lower()

    listing_score = 0

    # Heurística por URL
    if any(k in url_lower for k in cfg.url_keywords):
        listing_score += cfg.url_keyword_weight
    if any(p in url_lower for p in cfg.url_patterns):
        listing_score += cfg.url_pattern_weight

    # Quantidade de dadas em excesso
    date_matches = _DATE_RE.findall(content_lower)
    if len(date_matches) > cfg.date_low:
        listing_score += cfg.date_weight
    if len(date_matches) > cfg.date_high:
        listing_score += cfg.date_weight

    # Poucas palavras-chave de edital individual
    detail_hits = sum(content_lower.count(k) for k in cfg.detail_keywords)
    if detail_hits < cfg.min_detail_hits:
        listing_score += cfg.low_detail_weight

    # Plurais indicativos de listagem
    if "editais" in content_lower:
        listing_score += cfg.plural_editais_weight
    if "chamadas públicas" in content_lower:
        listing_score += cfg.plural_chamadas_weight

    return listing_score

def is_listing_page(url: str, content: str, cfg: ListingConfig = DEFAULT.listing) -> bool:
    return listing_score(url, content, cfg) >= cfg.threshold
