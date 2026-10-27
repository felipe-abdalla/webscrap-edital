import hashlib
from urllib.parse import urlsplit

def normalize_url(url: str) -> str:
    """Forma canônica da URL, usada para deduplicar e para gerar o id. Ignora esquema (http/https), 'www.', porta, barra final e fragmento (#)."""

    parts = urlsplit(url.strip())

    host = parts.hostname or ""
    if host.startswith("www."):
        host = host[4:]

    path = parts.path.rstrip("/")
    query = f"?{parts.query}" if parts.query else ""

    return f"{host}{path}{query}"

def url_id(url: str) -> str:
    """Identificador estável do item"""

    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()[:16]