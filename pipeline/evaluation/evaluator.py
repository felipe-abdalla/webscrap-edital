"""Uso: python -m pipeline.evaluation.evaluator datasets/run_XXXX"""
"""Etapas não executadas contam como negativas"""
import csv
import sys
from pathlib import Path

from pipeline.evaluation.metrics import confusion, summarize

LABEL_COLUMNS = [
    "is_listing_real",
    "is_edital_real",
    "is_relevant_real",
    "deadline_real",
    "deadline_status_real",
]

_TRUE = {"true", "1", "sim", "s", "verdadeiro", "yes"}
_FALSE = {"false", "0", "nao", "não", "n", "falso", "no"}

def parse_bool(value: str | None) -> bool | None:
    answer = (value or "").strip().lower()
    if answer in _TRUE:
        return True
    if answer in _FALSE:
        return False
    return None

def _pred(value: str | None) -> bool:
    return parse_bool(value) is True

def _end_to_end_label(l: dict) -> bool | None:
    parts = [l["is_edital_real"], l["is_relevant_real"], l["deadline_status_real"]]
    return None if None in parts else all(parts)

# nome -> (predição a partir de predictions.csv, rótulo a partir de labels.csv)
TASKS = {
    "listing": (lambda p: p["reason"] == "listing_page", lambda l: l["is_listing_real"]),
    "relevance": (lambda p: _pred(p["relevance_pred"]), lambda l: l["is_relevant_real"]),
    "deadline": (lambda p: _pred(p["deadline_pred"]), lambda l: l["deadline_status_real"]),
    "is_edital": (lambda p: _pred(p["pipeline_detected"]), lambda l: l["is_edital_real"]),
    "end_to_end": (lambda p: _pred(p["pipeline_detected"]), _end_to_end_label),
}

def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

# Cria um labels.csv em branco, uma linha por item, para rotulação manual
def init_labels(run_dir: Path, predictions: list[dict]) -> Path:
    path = run_dir / "labels.csv"

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "url", "title", *LABEL_COLUMNS, "observacao"])

        for p in predictions:
            writer.writerow([p["id"], p["url"], p["title"], *[""] * len(LABEL_COLUMNS), "", ""])

    return path

def evaluate(run_dir: Path) -> dict:
    predictions = {p["id"]: p for p in _read_csv(run_dir / "predictions.csv")}

    labels = {}
    for row in _read_csv(run_dir / "labels.csv"):
        labels[row["id"]] = {c: parse_bool(row.get(c)) for c in LABEL_COLUMNS}

    missing = predictions.keys() - labels.keys()
    if missing:
        print(f"[AVISO] {len(missing)} itens sem linha em labels.csv")

    results = {}

    for task, (get_pred, get_label) in TASKS.items():
        y_true, y_pred = [], []

        for item_id, p in predictions.items():
            if item_id not in labels:
                continue

            label = get_label(labels[item_id])
            if label is None:
                continue

            y_true.append(label)
            y_pred.append(get_pred(p))

        results[task] = summarize(confusion(y_true, y_pred)) | {"n": len(y_true)}

    return results

def write_metrics(run_dir: Path, results: dict):
    with open(run_dir / "metrics.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["DATA", "N", "TP", "FP", "FN", "TN",
                         "PRECISION", "RECALL", "F1-SCORE", "F2-SCORE"])

        for task, m in results.items():
            writer.writerow([task, m["n"], m["tp"], m["fp"], m["fn"], m["tn"],
                             f"{m['precision']:.3f}", f"{m['recall']:.3f}",
                             f"{m['f1']:.3f}", f"{m['f2']:.3f}"])

def main():
    run_dir = Path(sys.argv[1])

    if not (run_dir / "labels.csv").exists():
        path = init_labels(run_dir, _read_csv(run_dir / "predictions.csv"))
        print(f"labels.csv criado em {path}. Preencha os rótulos e rode novamente.")
        return

    results = evaluate(run_dir)
    write_metrics(run_dir, results)

    for task, m in results.items():
        print(f"{task:<12} n={m['n']:<3} P={m['precision']:.3f} "
              f"R={m['recall']:.3f} F1={m['f1']:.3f} F2={m['f2']:.3f}")

if __name__ == "__main__":
    main()