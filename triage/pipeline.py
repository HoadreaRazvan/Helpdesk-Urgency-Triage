"""L6–L7: compare models with grouped CV, choose a threshold on validation, freeze everything.

Nothing in this module can see the test window: it only receives the
development data from ``split.load_development``.
"""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn

from .analysis import (inspect_errors, leakage_demo, predict, queue_effect, shift_scenarios, slices,
                       tone_table)
from .baselines import evaluate_baselines
from .config import COMPLEXITY_MARGIN, COST_FN, COST_FP, Paths
from .data import TARGET
from .evaluate import calibration, choose_threshold, evaluate_flags, score_metrics
from .features import make_X
from .markdown import write_text
from .models import EXPERIMENTS, Experiment, build, cross_validate, cv_folds
from .split import load_development, read_manifest

COST_RATIOS = (2, 5, 10, 20)


class FrozenSettingsError(RuntimeError):
    pass


def scores_digest(scores) -> str:
    return hashlib.sha256(",".join(f"{s:.6f}" for s in scores).encode()).hexdigest()


def _versions() -> dict:
    return {"python": platform.python_version(), "scikit-learn": sklearn.__version__,
            "numpy": np.__version__, "pandas": pd.__version__}


def _finalist(rows: list[dict], families: tuple[str, ...]) -> Experiment:
    pool = [r for r in rows if r["allowed"] and r["family"] in families]
    best = max(pool, key=lambda r: (r["cv_average_precision"], -r["cv_brier"]))
    return next(e for e in EXPERIMENTS if e.id == best["id"])


def run_development(paths: Paths, log=print) -> dict:
    manifest = read_manifest(paths)
    dev = load_development(paths)
    train = dev[dev["split"] == "train"].reset_index(drop=True)
    val = dev[dev["split"] == "val"].reset_index(drop=True)
    X_train, y_train = make_X(train), train[TARGET]
    folds = cv_folds(y_train, train["requester_id"])

    log(f"L6 · {len(EXPERIMENTS)} experiments, {len(folds)}-fold CV grouped by requester "
        f"({len(train)} training tickets)")
    experiments = []
    for exp in EXPERIMENTS:
        cv = cross_validate(lambda: build(exp), X_train, y_train, folds)
        experiments.append({"id": exp.id, "name": exp.name, "family": exp.family,
                            "params": exp.describe(), "allowed": True, "note": exp.note, **cv})
        log(f"  {exp.id:<24} CV average precision {cv['cv_average_precision']:.3f} "
            f"± {cv['cv_average_precision_std']:.3f}")
    leak = leakage_demo(train, val, folds)
    log(f"  {leak['id']:<24} CV average precision {leak['cv_average_precision']:.3f}  <- excluded")

    log("L7 · threshold and model choice on validation")
    finalists = {}
    for role, families in (("A", ("logreg",)), ("B", ("forest", "boosting"))):
        exp = _finalist(experiments, families)
        model = build(exp).fit(X_train, y_train)
        p = predict(model, val)
        choice = choose_threshold(val[TARGET], p)
        finalists[role] = {"experiment": exp, "model": model, "scores": p, "choice": choice}
        for row in experiments:
            if row["id"] == exp.id:
                row.update({"finalist": role, "val_threshold": choice["threshold"],
                            "val_cost_per_100": choice["metrics"]["cost_per_100"],
                            **{f"val_{k}": v for k, v in score_metrics(val[TARGET], p).items()}})
        log(f"  Model {role}: {exp.id:<22} threshold {choice['threshold']:.2f} -> "
            f"validation cost {choice['metrics']['cost_per_100']:.1f} per 100 tickets")

    cost_a = finalists["A"]["choice"]["metrics"]["cost"]
    cost_b = finalists["B"]["choice"]["metrics"]["cost"]
    chosen_role = "B" if cost_b < cost_a * (1 - COMPLEXITY_MARGIN) else "A"
    chosen = finalists[chosen_role]
    exp, model, p = chosen["experiment"], chosen["model"], chosen["scores"]
    threshold = chosen["choice"]["threshold"]
    flags = p >= threshold
    for row in experiments:
        row["selected"] = row["id"] == exp.id
    log(f"  Selected: {exp.name} ({exp.id}), threshold {threshold:.2f}")

    sensitivity = []
    for ratio in COST_RATIOS:
        c = choose_threshold(val[TARGET], p, cost_fn=ratio, cost_fp=1)
        sensitivity.append({"cost_ratio": ratio, "threshold": c["threshold"],
                            **{k: c["metrics"][k] for k in ("recall", "precision", "flag_rate", "tp", "fn", "fp", "tn")}})

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "costs": {"fn": COST_FN, "fp": COST_FP},
        "windows": manifest["windows"],
        "tone": tone_table(train),
        "experiments": experiments + [leak],
        "selection": {
            "rule": (f"Best CV average precision per family; the tree ensemble replaces logistic "
                     f"regression only if it lowers validation cost by more than {COMPLEXITY_MARGIN:.0%}."),
            "chosen": chosen_role,
        },
        "finalists": {
            role: {"id": f["experiment"].id, "name": f["experiment"].name,
                   "params": f["experiment"].describe(), "threshold": f["choice"]["threshold"],
                   **evaluate_flags(val[TARGET], f["scores"] >= f["choice"]["threshold"]),
                   **score_metrics(val[TARGET], f["scores"]),
                   "calibration": calibration(val[TARGET], f["scores"])}
            for role, f in finalists.items()
        },
        "model": {"id": exp.id, "name": exp.name, "family": exp.family, "params": exp.describe()},
        "threshold": threshold,
        "validation": {
            **evaluate_flags(val[TARGET], flags), **score_metrics(val[TARGET], p),
            "baselines": evaluate_baselines(dev),
            "sweep": chosen["choice"]["sweep"],
            "calibration": calibration(val[TARGET], p),
            "sensitivity": sensitivity,
            "queue": queue_effect(val, flags),
            "slices": slices(val, p, threshold),
            "shifts": shift_scenarios(model, val, threshold),
            "errors": inspect_errors(model, train, val, p, threshold),
        },
    }

    frozen = {
        "frozen_at": results["generated_at"],
        "model": results["model"],
        "threshold": threshold,
        "costs": results["costs"],
        "data_sha256": manifest["data_sha256"],
        "split_ids_sha256": {w: s["ids_sha256"] for w, s in manifest["windows"].items()},
        "val_scores_sha256": scores_digest(p),
        "versions": _versions(),
    }
    _store(paths, frozen, model)
    write_text(paths.reports / "validation_results.json", json.dumps(results, indent=2, default=_json))

    from .reports import write_reports
    write_reports(paths)
    return results


def _json(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat(sep=" ")
    raise TypeError(type(value))


def _store(paths: Paths, frozen: dict, model) -> None:
    """Save the model and freeze the settings. After the test run, settings may not change."""
    if paths.test_lock.exists():
        old = json.loads(paths.frozen_config.read_text(encoding="utf-8"))
        same = (old["model"]["id"] == frozen["model"]["id"] and old["threshold"] == frozen["threshold"]
                and old["val_scores_sha256"] == frozen["val_scores_sha256"])
        if not same:
            raise FrozenSettingsError(
                "The test set has been used: this run would change the frozen model or threshold. "
                "Restore the code and environment that produced artifacts/frozen_config.json.")
        frozen = old  # identical model rebuilt: keep the original freeze record
    paths.artifacts.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, paths.model_file)
    write_text(paths.frozen_config, json.dumps(frozen, indent=2))


def load_model(paths: Paths):
    if not paths.model_file.exists():
        raise FileNotFoundError("No trained model yet. Run: python -m triage run")
    return joblib.load(paths.model_file)
