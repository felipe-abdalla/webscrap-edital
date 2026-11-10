import re
from datetime import datetime
from typing import List, Optional, Dict
from config.heuristics import DEFAULT, DeadlineConfig

import dateparser

_MONTHS = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

# AAAA-MM-DD | DD/MM/AA(AA) | DD de mês [de AAAA]
_DATE_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})"
    r"|(\d{1,2})/(\d{1,2})/(\d{2,4})"
    r"|(\d{1,2})º?\s+de\s+(" + "|".join(_MONTHS) + r")(?:\s+de\s+(\d{4}))?"
)

# Palavras que marcam o fim do prazo; a data seguinte é o prazo
_LIMIT_ANCHOR_RE = re.compile(r"limite|encerramento|término|termino|retificad|prorrogad")
_NEG_ANCHOR_RE = re.compile(r"resultado|divulga|homologa|publicad|assinatura")

class DeadlineExtractor:

    # No replay, "hoje" é a data da coleta (snapshot), não a data em que o código roda
    def __init__(self, today: Optional[datetime] = None, cfg: DeadlineConfig = DEFAULT.deadline):
        self.cfg = cfg
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

    # Todas as datas escritas na frase, com a posição onde começam
    def date_matches(self, sentence: str) -> List[tuple]:
        dates = []

        for m in _DATE_RE.finditer(sentence):
            try:
                if m[1]:
                    d = datetime(int(m[1]), int(m[2]), int(m[3]))
                elif m[4]:
                    year = int(m[6])
                    d = datetime(year + 2000 if year < 100 else year, int(m[5]), int(m[4]))
                else:
                    # Sem ano explícito: o ano da coleta
                    year = int(m[9]) if m[9] else self.today_date.year
                    d = datetime(year, _MONTHS[m[8]], int(m[7]))
            except ValueError:
                continue
            dates.append((d, m.start()))

        return dates

    def dates_in_sentence(self, sentence: str) -> List[datetime]:
        return [d for d, _ in self.date_matches(sentence)]

    # Primeira data depois de "limite", "encerramento"...; vale a última âncora que tem data
    def pick_by_keyword(self, sentence: str, found: List[tuple]) -> datetime:
        best = None

        for anchor in _LIMIT_ANCHOR_RE.finditer(sentence):
            after = [(d, start) for d, start in found if start > anchor.start()]
            if after and not _NEG_ANCHOR_RE.search(sentence, anchor.end(), after[0][1]):
                best = after[0][0]

        return best or found[-1][0]


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
        all_dates = []
        expired_found = False

        for sentence in candidates:
            if self.cfg.sentence_dates:
                found = self.date_matches(sentence)
                if self.cfg.date_by_keyword and len(found) > 1:
                    parsed_date = self.pick_by_keyword(sentence, found)
                else:
                    # Em "de X a Y", Y é o fim do período de inscrição
                    parsed_date = found[-1][0] if found else None
            else:
                parsed_date = self.parse_date(sentence)

            if parsed_date:
                if not self.cfg.sentence_dates:
                    parsed_date = self.normalize_year(parsed_date)

                score = self.score_sentence(sentence)

                if score <= self.cfg.min_sentence_score:
                    continue
                
                all_dates.append((parsed_date, score, sentence))
                
                # Deadline expirado
                if parsed_date.date() < self.today_date:
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
                    all_dates.append((parsed_date, self.cfg.regex_fallback_score, match))

                    # Também ignora expiradas no fallback
                    if parsed_date.date() < self.today_date:
                        expired_found = True
                        continue

                    scored_dates.append((parsed_date, self.cfg.regex_fallback_score, match))

        # A data de maior score é o prazo; se já passou, o edital está encerrado
        if self.cfg.open_from_best and all_dates:
            best_date, best_score, best_sentence = max(all_dates, key=lambda x: x[1])

            if best_date.date() < self.today_date:
                return {
                    "deadline": None,
                    "score": 0,
                    "confidence": 0.0,
                    "expired": True,
                    "best_any_date": best_date.date()
                }

            return {
                "deadline": best_date.date(),
                "score": best_score,
                "confidence": min(1.0, best_score / 10),
                "source_sentence": best_sentence,
                "expired": False,
                "best_any_date": best_date.date()
            }


        # Nenhuma válida encontrada
        if not scored_dates:
            best_any_date = max(all_dates, key=lambda x: x[1])[0].date() if all_dates else None

            if expired_found:
                return {
                    "deadline": None,
                    "score": 0,
                    "confidence": 0.0,
                    "expired": True,
                    "best_any_date": best_any_date
                }

            return {
                "deadline": None,
                "score": 0,
                "confidence": 0.0,
                "expired": False,
                "best_any_date": best_any_date
            }

        best_date, best_score, best_sentence = max(
            scored_dates,
            key=lambda x: x[1]
        )

        confidence = min(1.0, best_score / 10)

        best_any_date = max(all_dates, key=lambda x: x[1])[0].date() if all_dates else None

        return {
            "deadline": best_date.date(),
            "score": best_score,
            "confidence": confidence,
            "source_sentence": best_sentence,
            "expired": False,
            "best_any_date": best_any_date
        }