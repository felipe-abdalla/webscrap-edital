import requests
from bs4 import BeautifulSoup

def fetch_full_content(url: str) -> str:
    try:
        response = requests.get(
            url,
            timeout=5,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        if response.status_code != 200:
            return ""
        
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove scripts e styles
        for tag in soup(["script", "style"]):
            tag.decompose()

        text = soup.get_text(separator=" ")

        text = " ".join(text.split())

        return text
    
    except Exception as e:
        print(f"[SCRAPING ERROR] {url} -> {e}")
        return ""