def confusion(y_true: list[bool], y_pred: list[bool]) -> dict:
    confusion = {"tp": 0, "fp": 0, "tn": 0}

    for true, pred in zip(y_true, y_pred):
        if pred and true:
            confusion["tp"] += 1
        elif pred and not true:
            confusion["fp"] += 1
        elif not pred and true:
            confusion["fn"] += 1
        else:
            confusion["tn"] += 1

    return confusion

def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0

def precision(c: dict) -> float:
    return _safe_div(c["tp"], c["tp"] + c["fp"])

def recall(c: dict) -> float:
    return _safe_div(c["tp"], c["tp"] + c["fn"])

def f_beta(c: dict, beta: float = 1.0) -> float:
    p, r = precision(c), recall(c)
    b2 = beta ** 2
    return _safe_div((1 + b2) * p * r, b2 * p + r)

def summarize(c: dict) -> dict:
    return {
        **c,
        "precision": precision(c),
        "recall": recall(c),
        "f1": f_beta(c, 1.0),
        "f2": f_beta(c, 2.0)
    }