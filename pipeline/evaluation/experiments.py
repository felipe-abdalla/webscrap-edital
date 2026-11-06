"""Uso: python -m pipeline.evaluation.experiments datasets/run_XXXX"""
"""Avaliação isolada: todo item passa por todas as heurísticas, sem a cadeia de filtros"""
import csv
import sys
from datetime import date
from pathlib import Path

from config.heuristics import DEFAULT, HeuristicConfig
from pipeline.evaluation.evaluator import LABEL_COLUMNS, _read_csv, parse_bool
from pipeline.evaluation.metrics import confusion, summarize
from pipeline.filtering.deadline_filter import DeadlineExtractor
from pipeline.filtering.page_classifier import listing_score
from pipeline.filtering.relevance_filter import RelevanceFilter
from pipeline.pipeline import find_deadline, item_content
from pipeline.snapshot import load_snapshot

def extract_features(snapshot: dict, cfg: HeuristicConfig = DEFAULT) -> list[dict]:
    run_dir = snapshot["run_dir"]
    relevance = RelevanceFilter(cfg.relevance)
    extractor = DeadlineExtractor(today=snapshot["run_at"], cfg=cfg.deadline)

    features = []

    for item in snapshot["items"]:
        content, source = item_content(run_dir, item)
        found = find_deadline(extractor, content, cfg.deadline.fallback_window)

        features.append({
            "id": item["id"],
            "content_source": source,
            "listing_score": listing_score(item["url"], content, cfg.listing),
            "relevance_score": relevance.calculate_score(content),
            "deadline": found["deadline"],
            "best_any_date": found["best_any_date"],
            "expired": found["expired"],
            "source_sentence": found["source_sentence"],
        })

    return features

def load_labels(run_dir: Path) -> dict:
    labels = {}

    for row in _read_csv(run_dir / "labels.csv"):
        label = {c: parse_bool(row.get(c)) for c in LABEL_COLUMNS}
        raw_date = (row.get("deadline_date_real") or "").strip()
        label["deadline_date_real"] = date.fromisoformat(raw_date) if raw_date else None
        labels[row["id"]] = label

    return labels

def _binary(pairs: list[tuple[bool, bool]]) -> dict:
    y_true = [t for t, _ in pairs]
    y_pred = [p for _, p in pairs]
    return summarize(confusion(y_true, y_pred)) | {"n": len(pairs)}

# Os limiares são aplicados aqui, não em extract_features: varrer um limiar não exige reextrair
def evaluate_stages(features: list[dict], labels: dict, cfg: HeuristicConfig = DEFAULT) -> dict:
    rows = [(f, labels[f["id"]]) for f in features if f["id"] in labels]
    editais = [(f, l) for f, l in rows if l["is_edital_real"]]

    results = {
        "listing": _binary([
            (l["is_listing_real"], f["listing_score"] >= cfg.listing.threshold)
            for f, l in rows if l["is_listing_real"] is not None
        ]),
        "relevance": _binary([
            (l["is_relevant_real"], f["relevance_score"] >= cfg.relevance.threshold)
            for f, l in rows if l["is_relevant_real"] is not None
        ]),
        "deadline_exists": _binary([
            (l["deadline_real"], f["deadline"] is not None or f["expired"])
            for f, l in editais if l["deadline_real"] is not None
        ]),
        "deadline_open": _binary([
            (l["deadline_status_real"], f["deadline"] is not None)
            for f, l in editais if l["deadline_status_real"] is not None
        ]),
    }

    dated = [(f, l) for f, l in editais if l["deadline_date_real"]]
    hits = sum(f["best_any_date"] == l["deadline_date_real"] for f, l in dated)
    results["deadline_date"] = {"n": len(dated), "hits": hits,
                                "accuracy": hits / len(dated) if dated else 0.0}

    return results

def write_features(run_dir: Path, features: list[dict]):
    with open(run_dir / "features.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(features[0].keys()))
        writer.writeheader()
        writer.writerows(features)

def main():
    run_dir = Path(sys.argv[1])

    features = extract_features(load_snapshot(run_dir))
    write_features(run_dir, features)

    results = evaluate_stages(features, load_labels(run_dir))

    for stage, m in results.items():
        if "accuracy" in m:
            print(f"{stage:<16} n={m['n']:<3} acertos={m['hits']} acc={m['accuracy']:.3f}")
        else:
            print(f"{stage:<16} n={m['n']:<3} P={m['precision']:.3f} "
                  f"R={m['recall']:.3f} F1={m['f1']:.3f} F2={m['f2']:.3f}")

if __name__ == "__main__":
    main()
