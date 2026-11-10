"""Uso: python -m pipeline.evaluation.sensitivity_analysis datasets/run_XXXX [param ...]"""
"""Varia um parâmetro por vez (OAT), demais no valor de BASE"""
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config.heuristics import DEFAULT, HeuristicConfig, with_overrides
from pipeline.evaluation.experiments import evaluate_stages, extract_features, load_contents, load_labels
from pipeline.snapshot import load_snapshot

# grupo do parâmetro -> (etapa avaliada, métrica alvo)
TARGETS = {
    "listing": ("listing", "f05"),
    "relevance": ("relevance", "f2"),
    "deadline": ("deadline_date", "accuracy"),
}

# Limiares não mudam os scores: reaproveitam as features da configuração base
THRESHOLDS = {"listing.threshold", "relevance.threshold", "relevance.score_threshold"}

GRID = {
    "listing.threshold": list(range(0, 12)),
    "listing.url_keyword_weight": list(range(0, 7)),
    "listing.url_pattern_weight": list(range(0, 7)),
    "listing.link_low": [0, 5, 10, 15, 20, 25],
    "listing.link_high": [10, 25, 50, 100],
    "listing.link_weight": list(range(0, 5)),
    "listing.date_low": [0, 2, 5, 10, 15, 20],
    "listing.date_high": [5, 10, 20, 30, 50],
    "listing.date_weight": list(range(0, 5)),
    "listing.min_detail_hits": [0, 1, 2, 3, 5, 10],
    "listing.low_detail_weight": list(range(0, 5)),
    "listing.plural_editais_weight": list(range(0, 5)),
    "listing.plural_chamadas_weight": list(range(0, 5)),

    "relevance.threshold": [0, 3, 5, 10, 15, 20, 30, 40, 60, 80],
    "relevance.score_threshold": [0, 2, 5, 10, 20],
    "relevance.density_high": [0.02, 0.03, 0.05, 0.08, 0.1],
    "relevance.density_high_bonus": list(range(0, 7)),
    "relevance.density_low": [0.005, 0.01, 0.02, 0.03],
    "relevance.density_low_bonus": list(range(0, 5)),

    "deadline.keyword_weight": list(range(0, 6)),
    "deadline.negative_keyword_weight": list(range(-6, 1)),
    "deadline.ate_weight": list(range(0, 7)),
    "deadline.encerramento_weight": list(range(0, 9)),
    "deadline.min_sentence_score": list(range(-3, 6)),
    "deadline.regex_fallback_score": list(range(0, 4)),
    "deadline.year_window": [1, 2, 5, 10, 20, 50],
    "deadline.fallback_window": [500, 1000, 2000, 5000, 20000],
}

BASE = with_overrides(DEFAULT, {"deadline.sentence_dates": True})

# Pesos individuais das palavras-chave de relevância: "relevance.keywords[edital]"
for kw in DEFAULT.relevance.keywords:
    GRID[f"relevance.keywords[{kw}]"] = list(range(0, 7))
for kw in DEFAULT.relevance.negative_keywords:
    GRID[f"relevance.negative_keywords[{kw}]"] = list(range(-5, 1))

def _split(param: str) -> tuple[str, str | None]:
    if "[" in param:
        path, key = param[:-1].split("[")
        return path, key
    return param, None

def override(base: HeuristicConfig, param: str, value) -> HeuristicConfig:
    path, key = _split(param)
    if key is not None:
        group, name = path.split(".")
        value = {**getattr(getattr(base, group), name), key: value}
    return with_overrides(base, {path: value})

def current_value(base: HeuristicConfig, param: str):
    path, key = _split(param)
    group, name = path.split(".")
    value = getattr(getattr(base, group), name)
    return value[key] if key is not None else value

def _flatten(results: dict) -> dict:
    row = {}
    for stage, m in results.items():
        for key in ("n", "tp", "fp", "fn", "precision", "recall", "f05", "f1", "f2", "hits", "lost", "accuracy"):
            if key in m:
                row[f"{stage}.{key}"] = m[key]
    return row

def sweep(snapshot: dict, labels: dict, contents: dict, param: str, values: list,
          base: HeuristicConfig = DEFAULT) -> list[dict]:
    base_features = extract_features(snapshot, base, contents) if param in THRESHOLDS else None
    rows = []

    for value in values:
        cfg = override(base, param, value)
        features = base_features or extract_features(snapshot, cfg, contents)
        rows.append({"value": value, **_flatten(evaluate_stages(features, labels, cfg))})

    return rows

# Listing: perder edital é o erro caro; F0.5 só desempata
def score_key(stage: str, column: str, max_wrong: int):
    """Chave de comparação: maior é melhor. Tuplas comparam elemento a elemento"""

    if stage in ("listing", "deadline_date"):

        # 1º não aceita mais itens errados que o valor atual; 2º perde menos editais; 3º maior F0.5
        return lambda r: (r["end_to_end.fp"] <= max_wrong, -r["editais_perdidos.lost"], r[column])
    return lambda r: (r[column],)

def plateau_center(rows: list[dict], key) -> dict:
    """Entre as linhas empatadas na melhor chave, a do meio (mais robusta que a primeira)"""

    best = max(key(r) for r in rows)
    tied = [r for r in rows if key(r) == best]
    return tied[len(tied) // 2]

def summarize(rows: list[dict], column: str, stage: str, current) -> dict:
    """Uma linha do impact.csv: valor atual contra valor sugerido"""

    now = next(r for r in rows if r["value"] == current)
    best = plateau_center(rows, score_key(stage, column, now["end_to_end.fp"]))
    values = [r[column] for r in rows]
    e2e = [r["end_to_end.f1"] for r in rows]

    return {
        "metric": column,
        "current": current,
        "suggested": best["value"],
        "metric_current": now[column],
        "metric_suggested": best[column],
        "lost_current": now["editais_perdidos.lost"],
        "lost_suggested": best["editais_perdidos.lost"],
        "wrong_current": now["end_to_end.fp"],
        "wrong_suggested": best["end_to_end.fp"],
        "amplitude": max(values) - min(values),
        "amplitude_e2e": max(e2e) - min(e2e),
    }

def write_rows(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

def plot(path: Path, param: str, rows: list[dict], column: str, current):
    xs = [r["value"] for r in rows]

    plt.figure(figsize=(6, 4))
    plt.plot(xs, [r[column] for r in rows], marker="o", label=column)
    plt.plot(xs, [r["end_to_end.f1"] for r in rows], marker="s", linestyle="--", label="end_to_end.f1")
    plt.axvline(current, color="gray", linestyle=":", label=f"atual = {current}")
    plt.xlabel(param)
    plt.ylabel("métrica")
    plt.ylim(-0.05, 1.05)
    plt.legend()
    plt.tight_layout()
    try:
        plt.savefig(path, dpi=150)
    except OSError as e:
        print(f"[AVISO] gráfico não gravado ({e}); feche o arquivo se estiver aberto")
    finally:
        plt.close()

def main():
    run_dir = Path(sys.argv[1])
    params = sys.argv[2:] or list(GRID)

    snapshot = load_snapshot(run_dir)
    labels = load_labels(run_dir)
    contents = load_contents(snapshot)
    out_dir = run_dir / ("sensitivity" if BASE == DEFAULT else "sensitivity_base")

    impact = []

    for param in params:
        stage, metric = TARGETS[param.split(".")[0]]
        column = f"{stage}.{metric}"
        current = current_value(BASE, param)

        rows = sweep(snapshot, labels, contents, param, GRID[param], BASE)
        write_rows(out_dir / f"{param}.csv", rows)
        plot(out_dir / f"{param}.png", param, rows, column, current)

        impact.append({"param": param, **summarize(rows, column, stage, current)})
        r = impact[-1]
        print(f"{param:<40} amp={r['amplitude']:.3f} amp_e2e={r['amplitude_e2e']:.3f} "
              f"atual={current} sugerido={r['suggested']} "
              f"perdidos {r['lost_current']}->{r['lost_suggested']} errados {r['wrong_current']}->{r['wrong_suggested']}")

    impact.sort(key=lambda r: (r["amplitude"], r["amplitude_e2e"]), reverse=True)

    # Só a varredura completa grava impact.csv; execuções parciais não sobrescrevem a tabela
    name = "impact.csv" if len(sys.argv) == 2 else "impact_partial.csv"
    write_rows(out_dir / name, impact)


if __name__ == "__main__":
    main()