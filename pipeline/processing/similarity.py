def jaccard_similarity(text1: str, text2: str) -> float:
    set1 = set(text1.split())
    set2 = set(text2.split())

    if not set1 or not set2:
        return 0.0
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)

    return intersection / union