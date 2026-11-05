import re
from datetime import datetime
from typing import List, Optional, Dict
from config.heuristics import DEFAULT, DeadlineConfig

import dateparser

class DeadlineExtractor:

    def __init__(self, today: Optional[datetime] = None, cfg: DeadlineConfig = DEFAULT.deadline):
        self.cfg = cfg
        self.today_datetime = (today or datetime.now()).replace(tzinfo=None)
        self.today_date = self.today_datetime.date()

    # No replay, "hoje" [e a data da coleta (snapshot), não a data em que o código roda
    def __init__(self, today: Optional[datetime] = None):
        self.today_datetime = (today or datetime.now()).replace(tzinfo=None)
        self.today_date = self.today_datetime.date()

    # Extrair possíveis candidatos
    def extract_candidate_sentences(self, text: str) -> List[str]:
        sentences = re.split(r'[.\n]', text.lower())

        return [
            s.strip()
            for s in sentences
            if any(keyword in s for keyword in self.cfg.keywords)
        ]

    # Extrair datas com NLP
    def parse_date(self, text: str) -> Optional[datetime]:
        return dateparser.parse(
            text,
            languages=['pt'],
            settings={
                'PREFER_DATES_FROM': 'future',
                'RELATIVE_BASE': self.today_datetime,
                'DATE_ORDER': 'DMY'
            }
        )

    # Fallback com regex
    def regex_dates(self, text: str) -> List[str]:
        patterns = [
            r'\d{1,2}/\d{1,2}/\d{2,4}',
            r'\d{4}-\d{2}-\d{2}'
        ]

        matches = []

        for p in patterns:
            matches.extend(re.findall(p, text))

        return matches

    # Score
    def score_sentence(self, sentence: str) -> int:
        score = 0

        for keyword in self.cfg.keywords:
            if keyword in sentence:
                score += self.cfg.keyword_weight

        for keyword in self.cfg.negative_keywords:
            if keyword in sentence:
                score += self.cfg.negative_keyword_weight

        if "até" in sentence or "ate" in sentence:
            score += self.cfg.ate_weight

        if "encerramento" in sentence:
            score += self.cfg.encerramento_weight

        return score

    # Corrigir anos quebrados
    def normalize_year(self, date: datetime) -> datetime:
        current_year = self.today_date.year

        if date.year > current_year + self.cfg.year_window:
            return date.replace(year=date.year - 100)

        if date.year < current_year - self.cfg.year_window:
            return date.replace(year=date.year + 100)

        return date

    # Selecionar melhor deadline
    def extract_deadline(self, text: str) -> Dict:
        candidates = self.extract_candidate_sentences(text)
        scored_dates = []
        expired_found = False

        for sentence in candidates:
            parsed_date = self.parse_date(sentence)

            if parsed_date:
                parsed_date = self.normalize_year(parsed_date)
                score = self.score_sentence(sentence)

                if score <= self.cfg.min_sentence_score:
                    continue

                # Deadline expirado
                if parsed_date.date() < self.today_date:
                    print("[INSCRIÇÕES ENCERRADAS]")
                    expired_found = True
                    continue

                scored_dates.append((parsed_date, score, sentence))

        # Fallback regex
        if not scored_dates:
            regex_matches = self.regex_dates(text)

            for match in regex_matches:
                parsed_date = self.parse_date(match)

                if parsed_date:
                    parsed_date = self.normalize_year(parsed_date)

                    # Também ignora expiradas no fallback
                    if parsed_date.date() < self.today_date:
                        expired_found = True
                        continue

                    scored_dates.append((parsed_date, self.cfg.regex_fallback_score, match))

        # Nenhuma válida encontrada
        if not scored_dates:

            if expired_found:
                return {
                    "deadline": None,
                    "score": 0,
                    "confidence": 0.0,
                    "expired": True
                }

            return {
                "deadline": None,
                "score": 0,
                "confidence": 0.0,
                "expired": False
            }

        best_date, best_score, best_sentence = max(
            scored_dates,
            key=lambda x: x[1]
        )

        confidence = min(1.0, best_score / 10)

        return {
            "deadline": best_date.date(),
            "score": best_score,
            "confidence": confidence,
            "source_sentence": best_sentence,
            "expired": False
        }