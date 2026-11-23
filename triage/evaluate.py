"""Metrics that matter to the client: the full confusion matrix and the cost of mistakes."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

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


def score_metrics(y_true, scores) -> dict:
    """Threshold-free quality of the scores."""
    y = np.asarray(y_true).astype(int)
    p = np.asarray(scores, dtype=float)
    if y.min() == y.max():
        return {"average_precision": None, "roc_auc": None, "brier": float(np.mean((p - y) ** 2))}
    return {"average_precision": float(average_precision_score(y, p)),
            "roc_auc": float(roc_auc_score(y, p)),
            "brier": float(np.mean((p - y) ** 2))}


THRESHOLDS = np.round(np.arange(0.01, 1.0, 0.01), 2)


def sweep(y_true, scores, cost_fn: float = COST_FN, cost_fp: float = COST_FP,
          thresholds=THRESHOLDS) -> list[dict]:
    p = np.asarray(scores, dtype=float)
    return [{"threshold": float(t), **evaluate_flags(y_true, p >= t, cost_fn, cost_fp)}
            for t in thresholds]


SMOOTHING = 2  # thresholds on each side, i.e. a moving average over ±0.02


def choose_threshold(y_true, scores, cost_fn: float = COST_FN, cost_fp: float = COST_FP,
                     smoothing: int = SMOOTHING) -> dict:
    """Threshold with the lowest *smoothed* total cost.

    A cost curve measured on a few hundred tickets is jagged: a dip can come
    from four or five tickets. Averaging each point with its neighbours keeps
    the choice from hinging on that noise. On a tie, the lower threshold wins,
    because it catches more urgent tickets.
    """
    rows = sweep(y_true, scores, cost_fn, cost_fp)
    costs = np.array([r["cost"] for r in rows])
    padded = np.pad(costs, smoothing, mode="edge")
    smoothed = np.convolve(padded, np.ones(2 * smoothing + 1) / (2 * smoothing + 1), mode="valid")
    for r, s in zip(rows, smoothed):
        r["smoothed_cost"] = float(s)
    best = min(rows, key=lambda r: (round(r["smoothed_cost"], 9), r["threshold"]))
    return {"threshold": best["threshold"], "metrics": best, "sweep": rows}


def calibration(y_true, scores, n_bins: int = 10) -> dict:
    """Reliability table: does a score of 0.7 mean about 70% urgent?"""
    y = np.asarray(y_true).astype(int)
    p = np.asarray(scores, dtype=float)
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    bins, ece = [], 0.0
    for b in range(n_bins):
        mask = idx == b
        if not mask.any():
            continue
        mean_p, frac = float(p[mask].mean()), float(y[mask].mean())
        ece += mask.mean() * abs(mean_p - frac)
        bins.append({"low": float(edges[b]), "high": float(edges[b + 1]), "count": int(mask.sum()),
                     "mean_score": mean_p, "urgent_rate": frac})
    return {"bins": bins, "ece": float(ece), "brier": float(np.mean((p - y) ** 2)),
            "mean_score": float(p.mean()), "urgent_rate": float(y.mean())}
