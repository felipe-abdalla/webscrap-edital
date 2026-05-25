import re
from typing import Dict, Tuple

KEYWORDS: Dict[str, int] = {
    "edital": 3,
    "chamada pública": 3,
    "financiamento": 2,
    "inovação": 2,
    "incentivo": 2,
}

NEGATIVE_KEYWORDS: Dict[str, int] = {
    "resultado": -2,
    "publicado": -1,
    "notícia": -2,
    "evento": -1,
}


def _word_pattern(keyword: str) -> re.Pattern:
    """
    Cria um padrão que respeita fronteiras de palavra para texto em português.

    O \b nativo do Python não reconhece caracteres acentuados como parte de
    palavra (ex.: "inovação" pode não ser detectado antes de pontuação ou
    espaço). A solução é usar lookahead/lookbehind negativos que verificam
    se o caractere adjacente NÃO é alfanumérico (incluindo Unicode).
    """
    escaped = re.escape(keyword)
    return re.compile(
        rf"(?<![^\W])(?:{escaped})(?![^\W])",
        re.IGNORECASE | re.UNICODE,
    )


# Pré-compila os padrões uma única vez para eficiência
_KEYWORD_PATTERNS: Dict[str, Tuple[re.Pattern, int]] = {
    kw: (_word_pattern(kw), weight) for kw, weight in KEYWORDS.items()
}

_NEGATIVE_PATTERNS: Dict[str, Tuple[re.Pattern, int]] = {
    kw: (_word_pattern(kw), weight) for kw, weight in NEGATIVE_KEYWORDS.items()
}


class RelevanceFilter:

    def normalize_text(self, text: str) -> str:
        return text.lower()

    def count_keywords(
        self,
        text: str,
        patterns: Dict[str, Tuple[re.Pattern, int]],
    ) -> int:
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
            for _kw, (pattern, _weight) in _KEYWORD_PATTERNS.items()
        )

        density = keyword_hits / total_words

        if density > 0.05:
            return 3
        elif density > 0.02:
            return 1

        return 0

    def calculate_score(self, text: str) -> int:
        text = self.normalize_text(text)

        positive_score = self.count_keywords(text, _KEYWORD_PATTERNS)
        negative_score = self.count_keywords(text, _NEGATIVE_PATTERNS)
        density_bonus = self.keyword_density_bonus(text)

        return positive_score + negative_score + density_bonus

    def is_relevant(self, text: str, threshold: int = 3) -> Dict:
        score = self.calculate_score(text)
        confidence = min(1.0, score / 10)

        return {
            "is_relevant": score >= threshold,
            "score": score,
            "confidence": confidence,
        }
