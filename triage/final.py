"""L8: open the sealed test window exactly once, with frozen settings.

The lock file is written *before* any score is computed, so even an
interrupted run counts as the one allowed look. After that, this module
only returns the stored results.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .analysis import predict, queue_effect, slices
from .baselines import BASELINES
from .config import TEST_CONFIRMATION, Paths
from .data import TARGET, load_tickets
from .evaluate import calibration, evaluate_flags, score_metrics
from .markdown import write_text
from .pipeline import load_model, scores_digest
from .split import assign_windows, ids_digest, load_development, read_manifest, verify_data_unchanged


class FinalTestError(RuntimeError):
    pass


def sealed_test_status(paths: Paths) -> dict:
    if not paths.test_lock.exists():
        return {"used": False}
    lock = json.loads(paths.test_lock.read_text(encoding="utf-8"))
    results = (json.loads(paths.test_results.read_text(encoding="utf-8"))
               if paths.test_results.exists() else None)
    return {"used": True, "lock": lock, "results": results}


def run_final_test(paths: Paths, confirmation: str) -> dict:
    if confirmation.strip() != TEST_CONFIRMATION:
        raise FinalTestError(f'Type the confirmation exactly: "{TEST_CONFIRMATION}"')
    if paths.test_lock.exists():
        raise FinalTestError("The test set has already been used. Results: reports/test_results.json")
    if not paths.frozen_config.exists():
        raise FinalTestError("Nothing is frozen yet. Run: python -m triage run")

    frozen = json.loads(paths.frozen_config.read_text(encoding="utf-8"))
    manifest = read_manifest(paths)
    verify_data_unchanged(paths, manifest)
    if frozen["data_sha256"] != manifest["data_sha256"]:
        raise FinalTestError("The frozen settings were made on different data.")
    model = load_model(paths)

    # The saved model must be exactly the one whose threshold was frozen.
    dev = load_development(paths)
    val = dev[dev["split"] == "val"].reset_index(drop=True)
    if scores_digest(predict(model, val)) != frozen["val_scores_sha256"]:
        raise FinalTestError("artifacts/model.joblib is not the frozen model. Run: python -m triage run")

    df, _ = load_tickets(paths.tickets_csv)
    test = df[assign_windows(df["submitted_at"]) == "test"].reset_index(drop=True)
    if ids_digest(test["ticket_id"]) != manifest["windows"]["test"]["ids_sha256"]:
        raise FinalTestError("The test window does not match the frozen manifest.")

    opened_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lock = {"opened_at": opened_at, "model": frozen["model"]["id"], "threshold": frozen["threshold"]}
    paths.artifacts.mkdir(parents=True, exist_ok=True)
    write_text(paths.test_lock, json.dumps(lock, indent=2))

    threshold = frozen["threshold"]
    p = predict(model, test)
    flags = p >= threshold
    train = dev[dev["split"] == "train"]
    baselines = []
    for key, (name, make) in BASELINES.items():
        b = make().fit(train, train[TARGET])
        baselines.append({"id": key, "name": name, **evaluate_flags(test[TARGET], b.predict(test))})

    results = {
        "opened_at": opened_at,
        "model": frozen["model"],
        "threshold": threshold,
        "costs": frozen["costs"],
        "tickets": int(len(test)),
        "period": [test["submitted_at"].min().isoformat(sep=" "), test["submitted_at"].max().isoformat(sep=" ")],
        **evaluate_flags(test[TARGET], flags),
        **score_metrics(test[TARGET], p),
        "calibration": calibration(test[TARGET], p),
        "baselines": baselines,
        "queue": queue_effect(test, flags),
        "slices": slices(test, p, threshold),
    }
    write_text(paths.test_results, json.dumps(results, indent=2))

    from .reports import write_reports
    write_reports(paths)
    return results
