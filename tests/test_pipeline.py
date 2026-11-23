"""Acceptance checks for L6–L8: pipeline, threshold on validation only, one-shot test."""
import json
import shutil

import numpy as np
import pandas as pd
import pytest

from triage import features, models, pipeline
from triage.config import PROJECT_ROOT, TEST_CONFIRMATION, TEST_START, Paths
from triage.evaluate import calibration, choose_threshold
from triage.final import FinalTestError, run_final_test, sealed_test_status
from triage.split import SplitError, freeze_split

# A reduced ladder keeps the suite fast; it still has both model families.
FAST = tuple(e for e in models.EXPERIMENTS
             if e.id in ("logreg_C1", "logreg_C1_no_text", "logreg_C10", "logreg_C10_tone", "forest_leaf8"))


def _workspace(root, flip_test_labels=False) -> Paths:
    (root / "data").mkdir(parents=True)
    target = root / "data" / "tickets.csv"
    shutil.copy(PROJECT_ROOT / "data" / "tickets.csv", target)
    if flip_test_labels:
        df = pd.read_csv(target)
        test = pd.to_datetime(df["submitted_at"]) >= pd.Timestamp(TEST_START)
        df.loc[test, "urgent_label"] = 1 - df.loc[test, "urgent_label"]
        df.to_csv(target, index=False)
    paths = Paths(root=root)
    freeze_split(paths)
    return paths


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setattr(pipeline, "EXPERIMENTS", FAST)
    quiet = lambda *a, **k: None  # noqa: E731
    original = _workspace(tmp_path_factory.mktemp("original"))
    flipped = _workspace(tmp_path_factory.mktemp("flipped"), flip_test_labels=True)
    results = pipeline.run_development(original, log=quiet)
    results_flipped = pipeline.run_development(flipped, log=quiet)
    yield original, results, flipped, results_flipped
    mp.undo()


def test_threshold_and_model_do_not_depend_on_test_labels(runs):
    original, results, flipped, results_flipped = runs
    a = json.loads(original.frozen_config.read_text(encoding="utf-8"))
    b = json.loads(flipped.frozen_config.read_text(encoding="utf-8"))
    assert a["model"] == b["model"]
    assert a["threshold"] == b["threshold"]
    assert a["val_scores_sha256"] == b["val_scores_sha256"]


def test_confusion_matrix_is_complete(runs):
    _, results, _, _ = runs
    v = results["validation"]
    assert v["tp"] + v["fn"] + v["fp"] + v["tn"] == results["windows"]["val"]["rows"]
    assert v["tp"] + v["fn"] == results["windows"]["val"]["urgent"]


def test_model_earns_its_place(runs):
    _, results, _, _ = runs
    v = results["validation"]
    for baseline in v["baselines"]:
        assert v["cost_per_100"] < baseline["cost_per_100"], baseline["id"]


def test_at_least_ten_errors_inspected(runs):
    _, results, _, _ = runs
    errors = results["validation"]["errors"]
    assert len(errors) >= 10
    assert {e["kind"] for e in errors} == {"missed", "false_alarm"}
    assert all(e["hypothesis"] for e in errors)


def test_leakage_demo_is_flagged_and_never_selected(runs):
    _, results, _, _ = runs
    leak = [e for e in results["experiments"] if not e["allowed"]]
    assert len(leak) == 1 and not leak[0].get("selected")
    assert leak[0]["cv_roc_auc"] > 0.9


def test_reports_contain_intended_and_prohibited_use(runs):
    original, *_ = runs
    card = (original.reports / "model_card.md").read_text(encoding="utf-8")
    assert "## Intended use" in card and "## Prohibited use" in card
    assert "Not run yet" in card
    for name in ("experiments.md", "experiments.csv", "validation_report.md",
                 "error_analysis.md", "decision_note.md"):
        assert (original.reports / name).exists()


def test_test_set_is_used_exactly_once(runs):
    original, *_ = runs
    with pytest.raises(FinalTestError):
        run_final_test(original, "yes please")
    assert not sealed_test_status(original)["used"]

    results = run_final_test(original, TEST_CONFIRMATION)
    assert results["tp"] + results["fn"] + results["fp"] + results["tn"] == results["tickets"]
    assert sealed_test_status(original)["used"]
    with pytest.raises(FinalTestError):
        run_final_test(original, TEST_CONFIRMATION)
    with pytest.raises(SplitError):
        freeze_split(original, force=True)
    card = (original.reports / "model_card.md").read_text(encoding="utf-8")
    assert "Not run yet" not in card


def test_frozen_settings_cannot_change_after_the_test(runs):
    original, *_ = runs
    assert original.test_lock.exists()  # set by the previous test
    frozen = json.loads(original.frozen_config.read_text(encoding="utf-8"))
    with pytest.raises(pipeline.FrozenSettingsError):
        pipeline._store(original, {**frozen, "threshold": 0.5}, pipeline.load_model(original))


def test_make_X_refuses_post_submission_sources(monkeypatch):
    monkeypatch.setitem(features.SOURCES, "priority", "assigned_priority")
    with pytest.raises(features.LeakageError):
        features.make_X(pd.DataFrame())


def test_choose_threshold_ignores_a_one_point_dip():
    rng = np.random.default_rng(0)
    y = rng.random(2000) < 0.2
    scores = np.clip(y * 0.3 + rng.random(2000) * 0.7, 0, 1)
    choice = choose_threshold(y, scores, cost_fn=5, cost_fp=1)
    smoothed = [r["smoothed_cost"] for r in choice["sweep"]]
    assert choice["metrics"]["smoothed_cost"] == min(smoothed)


def test_calibration_of_honest_scores():
    rng = np.random.default_rng(1)
    p = rng.random(20000)
    y = rng.random(20000) < p
    assert calibration(y, p)["ece"] < 0.02
