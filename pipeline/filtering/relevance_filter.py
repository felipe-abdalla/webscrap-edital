import re
from typing import Dict, Tuple
from config.heuristics import DEFAULT, RelevanceConfig

def _word_pattern(keyword: str) -> re.Pattern:
    escaped = re.escape(keyword)
    return re.compile(
        rf"(?<![^\W])(?:{escaped})(?![^\W])",
        re.IGNORECASE | re.UNICODE,
    )

def _compile(keywords: Dict[str, int]) -> Dict[str, Tuple[re.Pattern, int]]:
    return {kw: (_word_pattern(kw), weight) for kw, weight in keywords.items()}

class RelevanceFilter:

    def __init__(self, cfg: RelevanceConfig = DEFAULT.relevance):
        self.cfg = cfg
        self.keyword_patterns = _compile(cfg.keywords)
        self.negative_patterns = _compile(cfg.negative_keywords)

    def normalize_text(self, text: str) -> str:
        return text.lower()

    def count_keywords(self, text: str, patterns: Dict[str, Tuple[re.Pattern, int]]) -> int:
        score = 0
        for _kw, (pattern, weight) in patterns.items():
            matches = pattern.findall(text)
            score += len(matches) * weight
        return score

    def keyword_density_bonus(self, text: str) -> int:
        words = text.split()
        total_words = len(words)

        if total_words == 0:
            return 0

        keyword_hits = sum(
            len(pattern.findall(text))
            for _kw, (pattern, _weight) in self.keyword_patterns.items()
        )
        density = keyword_hits / total_words

        if density > self.cfg.density_high:
            return self.cfg.density_high_bonus
        elif density > self.cfg.density_low:
            return self.cfg.density_low_bonus

        return 0

    def calculate_score(self, text: str) -> int:
        text = self.normalize_text(text)

        positive_score = self.count_keywords(text, self.keyword_patterns)
        negative_score = self.count_keywords(text, self.negative_patterns)
        density_bonus = self.keyword_density_bonus(text)

        return positive_score + negative_score + density_bonus

    def is_relevant(self, text: str) -> Dict:
        score = self.calculate_score(text)
        confidence = min(1.0, score / 10)

        return {
            "is_relevant": score >= self.cfg.threshold,
            "score": score,
            "confidence": confidence,
        }
