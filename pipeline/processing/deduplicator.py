from utils.url_utils import normalize_url

def deduplicate(results):
    seen_urls = set()
    unique = []

    for r in results:
        url = r.get("url")

        if not url:
            continue

        key = normalize_url(url)

        if key not in seen_urls:
            seen_urls.add(key)
            unique.append(r)

    return unique

