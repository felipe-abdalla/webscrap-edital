from pipeline.search.query_storage import load_stats, save_stats

def evaluate_results(results):
    # Penaliza query ruim
    if not results:
        return -2
    
    score = 0

    for r in results:
        title = (r.get("title") or "").lower()
        content = (r.get("content") or "").lower()

        if "edital" in title:
            score += 2
        if "inscrição" in content or "prazo" in content:
            score += 1
        if "2026" in content:
            score += 1

    return score

def update_query_stats(query, results):
    stats = load_stats()

    score = evaluate_results(results)

    if query not in stats:
        stats[query] = {"score": 0, "uses": 0}

    stats[query]["score"] += score
    stats[query]["uses"] += 1

    save_stats(stats)