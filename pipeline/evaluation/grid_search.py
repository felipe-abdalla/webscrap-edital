"""Uso: python -m pipeline.evaluation.grid_search datasets/run_XXXX"""
"""Grade do listing sobre a BASE, validação cruzada da escolha e bootstrap contra a BASE"""
import random
import sys
from collections import Counter
from dataclasses import replace
from itertools import product
from pathlib import Path

from config.heuristics import with_overrides
from pipeline.evaluation.evaluator import _end_to_end_label
from pipeline.evaluation.experiments import evaluate_stages, extract_features, load_contents, load_labels, pipeline_accepts
from pipeline.evaluation.sensitivity_analysis import BASE, _flatten, write_rows
from pipeline.filtering.page_classifier import listing_score
from pipeline.snapshot import load_snapshot

GRID = {
    "listing.url_pattern_weight": [0, 1, 3],
    "listing.url_keyword_weight": [2, 3],
    "listing.date_weight": [2, 3, 4],
    "listing.date_high": [10, 20, 30],
    "listing.plural_editais_weight": [1, 2],
    "listing.threshold": [3, 4, 5, 6],
}

_CACHE = {}

def with_listing(features, snapshot, contents, cfg):
    """Só o listing_score depende dos pesos do listing; o limiar não muda o score"""
    key = replace(cfg.listing, threshold=0)
    if key not in _CACHE:
        urls = {it["id"]: it["url"] for it in snapshot["items"]}
        _CACHE[key] = {f["id"]: listing_score(urls[f["id"]], contents[f["id"]][0], cfg.listing) for f in features}
    return [{**f, "listing_score": _CACHE[key][f["id"]]} for f in features]

def grid(snapshot, labels, contents, features, base=BASE):
    current = {p: getattr(base.listing, p.split(".")[1]) for p in GRID}
    max_wrong = _flatten(evaluate_stages(features, labels, base))["end_to_end.fp"]
    rows = []

    for combo in product(*GRID.values()):
        params = dict(zip(GRID, combo))
        cfg = with_overrides(base, params)
        r = _flatten(evaluate_stages(with_listing(features, snapshot, contents, cfg), labels, cfg))
        rows.append({**params, "changed": sum(params[p] != current[p] for p in GRID),
                     "lost": r["editais_perdidos.lost"], "wrong": r["end_to_end.fp"], "f05": r["listing.f05"]})

    # Lexicográfico: não mais errados que a BASE, menos perdidos, F0.5; empate: menos parâmetros mudados
    rows.sort(key=lambda r: (r["wrong"] <= max_wrong, -r["lost"], round(r["f05"], 3), -r["changed"]), reverse=True)
    return rows

def cross_validate(snapshot, labels, contents, features, k=5, repeats=10, seed=0):
    ids = sorted(labels)
    rows = []

    for rep in range(repeats):
        order = ids[:]
        random.Random(seed + rep).shuffle(order)

        for fold in range(k):
            test_ids = set(order[fold::k])
            train = {i: labels[i] for i in ids if i not in test_ids}
            test = {i: labels[i] for i in test_ids}

            # A escolha usa só os rótulos de treino; a avaliação, só os de fora
            best = grid(snapshot, train, contents, features)[0]
            chosen = with_overrides(BASE, {p: best[p] for p in GRID})

            for name, cfg in (("escolhida", chosen), ("base", BASE)):
                r = _flatten(evaluate_stages(with_listing(features, snapshot, contents, cfg), test, cfg))
                rows.append({"repeat": rep, "fold": fold, "config": name,
                             "choice": "|".join(str(best[p]) for p in GRID),
                             "lost": r["editais_perdidos.lost"], "wrong": r["end_to_end.fp"]})
    return rows

def per_item(features, labels, cfg):
    """(edital perdido, errado aceito) por item: o bootstrap reamostra itens, não métricas"""
    out = []
    for f in features:
        l = labels.get(f["id"])
        if l is None:
            continue
        lost = bool(l["is_edital_real"]) and f["listing_score"] >= cfg.listing.threshold
        wrong = pipeline_accepts(f, cfg) and _end_to_end_label(l) is False
        out.append((int(lost), int(wrong)))
    return out

def bootstrap(a, b, n=2000, seed=0):
    rng = random.Random(seed)
    diffs = {"lost": [], "wrong": []}

    for _ in range(n):
        idx = [rng.randrange(len(a)) for _ in a]
        diffs["lost"].append(sum(b[i][0] - a[i][0] for i in idx))
        diffs["wrong"].append(sum(b[i][1] - a[i][1] for i in idx))

    return {m: (sorted(v)[int(0.025 * n)], sorted(v)[int(0.975 * n)]) for m, v in diffs.items()}

def main():
    run_dir = Path(sys.argv[1])
    snapshot, labels = load_snapshot(run_dir), load_labels(run_dir)
    contents = load_contents(snapshot)
    features = extract_features(snapshot, BASE, contents)
    out = run_dir / "grid"

    rows = grid(snapshot, labels, contents, features)
    write_rows(out / "grid_listing.csv", rows)
    best = rows[0]
    print("melhor da grade:", best)
    print("empatados no topo:", sum((r["wrong"], r["lost"], round(r["f05"], 3)) ==
                                    (best["wrong"], best["lost"], round(best["f05"], 3)) for r in rows))

    cv = cross_validate(snapshot, labels, contents, features)
    write_rows(out / "cv_listing.csv", cv)
    for name in ("base", "escolhida"):
        sel = [r for r in cv if r["config"] == name]
        print(f"CV {name:<10} perdidos={sum(r['lost'] for r in sel)} errados={sum(r['wrong'] for r in sel)}")
    choices = Counter(r["choice"] for r in cv if r["config"] == "escolhida")
    print("estabilidade:", choices.most_common(3), "de", sum(choices.values()), "dobras")

    chosen = with_overrides(BASE, {p: best[p] for p in GRID})
    a = per_item(with_listing(features, snapshot, contents, BASE), labels, BASE)
    b = per_item(with_listing(features, snapshot, contents, chosen), labels, chosen)
    print("bootstrap IC95% (escolhida - base):", bootstrap(a, b))

if __name__ == "__main__":
    main()
