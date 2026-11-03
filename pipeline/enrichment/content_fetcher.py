import requests
import io

from pypdf import PdfReader
from bs4 import BeautifulSoup

_TIMEOUT = 15
_HEADERS = {"User-Agent": "Mozilla/5.0"}

def _is_pdf(raw: dict) -> bool:
    return raw["body"][:4] == b"%PDF" or "application/pdf" in raw["content_type"]

def _extract_pdf(body: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(body))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        print(f"[PDF ERROR] {e}")
        return ""

def fetch_raw(url: str) -> dict:
    """Baixa a URL sem interpretar o conteúdo"""

    try:
        response = requests.get(url, timeout=_TIMEOUT, headers=_HEADERS)

        return {
            "status": response.status_code,
            "content_type": response.headers.get("Content-Type", ""),
            "final_url": response.url,
            "encoding": response.encoding or response.apparent_encoding,
            "body": response.content,
            "error": None,
        }

    except Exception as e:
        print(f"[SCRAPING ERROR] {url} -> {e}")

        return {
            "status": None,
            "content_type": "",
            "final_url": url,
            "encoding": None,
            "body": b"",
            "error": str(e),
        }

def _decode(body: bytes, encoding: str | None) -> str:
    try:
        return body.decode(encoding or "utf-8", errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")

def extract_text(raw: dict) -> str:
    """Converte a resposta bruta em texto limpo"""

    if raw["status"] != 200 or not raw["body"]:
        return ""

    if _is_pdf(raw):
        return _extract_pdf(raw["body"])

    soup = BeautifulSoup(_decode(raw["body"], raw["encoding"]), "html.parser")

    # Remove scripts e styles
    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator=" ")

    return " ".join(text.split())

def fetch_full_content(url: str) -> str:
    return extract_text(fetch_raw(url))