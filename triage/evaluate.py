"""Metrics that matter to the client: the full confusion matrix and the cost of mistakes."""
from __future__ import annotations

import numpy as np

from .config import COST_FN, COST_FP


def confusion(y_true, flags) -> dict:
    y = np.asarray(y_true).astype(bool)
    f = np.asarray(flags).astype(bool)
    return {"tp": int((y & f).sum()), "fn": int((y & ~f).sum()),
            "fp": int((~y & f).sum()), "tn": int((~y & ~f).sum())}


def _ratio(num: float, den: float) -> float:
    return float(num / den) if den else 0.0


def rates(cm: dict) -> dict:
    tp, fn, fp, tn = cm["tp"], cm["fn"], cm["fp"], cm["tn"]
    n = tp + fn + fp + tn
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    return {
        "precision": precision,
        "recall": recall,
        "f1": _ratio(2 * precision * recall, precision + recall),
        "accuracy": _ratio(tp + tn, n),
        "specificity": _ratio(tn, tn + fp),
        "flag_rate": _ratio(tp + fp, n),
    }


def cost(cm: dict, cost_fn: float = COST_FN, cost_fp: float = COST_FP) -> float:
    return float(cm["fn"] * cost_fn + cm["fp"] * cost_fp)


def evaluate_flags(y_true, flags, cost_fn: float = COST_FN, cost_fp: float = COST_FP) -> dict:
    cm = confusion(y_true, flags)
    n = sum(cm.values())
    total = cost(cm, cost_fn, cost_fp)
    return {**cm, **rates(cm), "n": n, "cost": total, "cost_per_100": _ratio(100 * total, n)}
