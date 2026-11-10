from dataclasses import dataclass, field, asdict, replace

@dataclass(frozen=True)
class ListingConfig:
    url_keywords: tuple[str, ...] = (
        "editais", "oportunidades", "noticias", "notícias", "chamadas", "bolsas",
        "programas", "arquivo", "resultados", "catalogo", "catálogo", "lista",
        "todas-as-chamadas", "todas-as-oportunidades",
    )
    url_patterns: tuple[str, ...] = (
        "/noticias/", "/notícias/", "/oportunidades/", "/editais-2026", "/bolsas/", "/programas/", "/resultados/",
    )
    detail_keywords: tuple[str, ...] = (
        "chamada pública", "edital", "nº", "numero",
        "inscrição", "prazo", "submissão", "cronograma",
    )
    url_keyword_weight: int = 2
    url_pattern_weight: int = 0
    date_low: int = 5
    date_high: int = 20
    date_weight: int = 2
    min_detail_hits: int = 2
    low_detail_weight: int = 2
    plural_editais_weight: int = 2
    plural_chamadas_weight: int = 1
    threshold: int = 6

@dataclass(frozen=True)
class RelevanceConfig:
    keywords: dict[str, int] = field(default_factory=lambda: {
        "edital": 3,
        "chamada pública": 3,
        "financiamento": 2,
        "inovação": 2,
        "incentivo": 2,
    })
    negative_keywords: dict[str, int] = field(default_factory=lambda: {
        "resultado": -2,
        "publicado": -1,
        "notícia": -2,
        "evento": -1,
    })
    density_high: float = 0.05
    density_high_bonus: int = 3
    density_low: float = 0.02
    density_low_bonus: int = 1
    threshold: int = 3

@dataclass(frozen=True)
class DeadlineConfig:
    keywords: tuple[str, ...] = (
        "prazo", "inscrições", "inscrição", "submissão", "submissao", "até", "ate",
        "deadline", "data limite", "encerramento", "período", "periodo",
        "vigência", "vigencia", "cronograma", "datas importantes", "envio", "abertas",
    )
    negative_keywords: tuple[str, ...] = (
        "resultado", "resultado final", "divulgação",
        "homologação", "publicado", "assinatura",
    )
    keyword_weight: int = 2
    negative_keyword_weight: int = -3
    ate_weight: int = 3
    encerramento_weight: int = 4
    min_sentence_score: int = 0
    regex_fallback_score: int = 1
    year_window: int = 10
    fallback_window: int = 2000
    sentence_dates: bool = True 
    open_from_best: bool = True
    date_by_keyword: bool = True

@dataclass(frozen=True)
class DedupConfig:
    signature_window: int = 1000
    jaccard_window: int = 1000
    jaccard_threshold: float = 0.8

@dataclass(frozen=True)
class HeuristicConfig:
    listing: ListingConfig = field(default_factory=ListingConfig)
    relevance: RelevanceConfig = field(default_factory=RelevanceConfig)
    deadline: DeadlineConfig = field(default_factory=DeadlineConfig)
    dedup: DedupConfig = field(default_factory=DedupConfig)

    def to_dict(self) -> dict:
        return asdict(self)

DEFAULT = HeuristicConfig()

def with_overrides(cfg: HeuristicConfig, overrides: dict) -> HeuristicConfig:
    """Ex.: {"relevance.threshold": 5} -> nova config com o valor trocado"""

    for path, value in overrides.items():
        group, name = path.split(".")
        cfg = replace(cfg, **{group: replace(getattr(cfg, group), **{name: value})})

    return cfg