import hashlib
import re

def generate_signature(text: str, window: int = 1000) -> str:
    if not text:
        return ""
    
    # Normalização
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)

    snippet = text[:window]

    return hashlib.md5(snippet.encode()).hexdigest()