from urllib.parse import urlparse

def extract_domain(url):
    try:
        return urlparse(url).netloc
    except:
        return ""