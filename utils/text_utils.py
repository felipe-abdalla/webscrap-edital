import unicodedata
import re

def normalize_text(text):
    if not text:
        return ""
    
    text = text.lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')

    return text

def clean_text(text):
    if not text:
        return ""
    
    text = re.sub(r'\s+', ' ', text)
    return text.strip()