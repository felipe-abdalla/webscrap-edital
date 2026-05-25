def deduplicate(results):
    seen_urls = set()
    unique = []

    for r in results:
        url = r.get("url")

        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(r)

    return unique

