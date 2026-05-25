import hashlib
import re

def generate_signature(text: str) -> str:
    if not text:
        return ""
    
    # Normalização
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)

    snippet = text[:1000]

    return hashlib.md5(snippet.encode()).hexdigest()