"""Acceptance checks for L5: no future information, clean data, reproducible split."""
import json

import pandas as pd
import pytest

from triage.baselines import IMPACT_PHRASES, MajorityClass, PhraseRule
from triage.data import (CATEGORIES, COLUMN_POLICY, clean, feature_columns, load_raw,
                         load_tickets, policy_for)
from triage.evaluate import evaluate_flags
from triage.split import SplitError, freeze_split, load_development, read_manifest


def test_post_submission_columns_are_never_features():
    for leak in ("assigned_priority", "handling_team", "resolution_hours"):
        assert not COLUMN_POLICY[leak].available_at_submission
        assert leak not in feature_columns(COLUMN_POLICY)
    for col in feature_columns(COLUMN_POLICY):
        assert COLUMN_POLICY[col].available_at_submission


def test_identifiers_target_and_sensitive_columns_are_not_features():
    features = feature_columns(COLUMN_POLICY)
    for col in ("ticket_id", "requester_id", "requester_type", "urgent_label", "submitted_at"):
        assert col not in features


def test_undocumented_columns_are_excluded_by_default():
    assert not policy_for("days_until_closed").is_feature
    assert feature_columns(["category", "days_until_closed"]) == ["category"]


def test_cleaning(workspace):
    raw = load_raw(workspace.tickets_csv)
    df, log = clean(raw)
    assert len(df) == len(raw.drop_duplicates())
    assert df["ticket_id"].is_unique
    assert set(df["category"]) <= set(CATEGORIES)
    assert df["initial_channel"].notna().all()
    assert (df["description_length"] == df["description"].str.len()).all()
    assert df["submitted_at"].is_monotonic_increasing
    assert {step["step"] for step in log}


def test_channel_recovered_only_from_explicit_prefix():
    raw = pd.DataFrame({
        "ticket_id": ["a", "b", "c"],
        "submitted_at": ["2025-09-01 10:00:00"] * 3,
        "category": ["software"] * 3,
        "initial_channel": [None, None, "email"],
        "description": ["Caller reports: printer down", "Printer down", "Walk-in: hello"],
        "description_length": [None, 12, 14],
        "urgent_label": [0, 1, 0],
    })
    df, _ = clean(raw)
    assert df["initial_channel"].tolist() == ["phone", "unknown", "email"]


def test_split_is_time_ordered_and_reproducible(workspace):
    first = freeze_split(workspace)
    dev = load_development(workspace)
    train, val = dev[dev["split"] == "train"], dev[dev["split"] == "val"]
    assert train["submitted_at"].max() < val["submitted_at"].min()
    assert set(dev["split"]) == {"train", "val"}, "development data must never contain test rows"
    assert first["windows"]["test"]["rows"] > 0
    assert "urgent" not in first["windows"]["test"], "test labels must stay unseen"

    again = freeze_split(workspace, force=True)
    for w in ("train", "val", "test"):
        assert again["windows"][w]["ids_sha256"] == first["windows"][w]["ids_sha256"]


def test_split_detects_changed_data(workspace):
    freeze_split(workspace)
    with open(workspace.tickets_csv, "a", encoding="utf-8") as f:
        f.write("T-999999,2026-01-01 10:00:00,R0001,employee,software,email,Hi,2,0,P4,tier1,1.0,0\n")
    with pytest.raises(SplitError):
        load_development(workspace)


def test_split_is_final_once_test_used(workspace):
    freeze_split(workspace)
    workspace.artifacts.mkdir()
    workspace.test_lock.write_text("{}")
    with pytest.raises(SplitError):
        freeze_split(workspace, force=True)
    assert read_manifest(workspace)


def test_metrics_match_the_worked_example_from_the_brief():
    y = [1] * 20 + [0] * 80
    flags = [1] * 16 + [0] * 4 + [1] * 12 + [0] * 68
    m = evaluate_flags(y, flags, cost_fn=10, cost_fp=1)
    assert (m["tp"], m["fn"], m["fp"], m["tn"]) == (16, 4, 12, 68)
    assert m["recall"] == pytest.approx(0.80)
    assert m["precision"] == pytest.approx(16 / 28)
    assert m["f1"] == pytest.approx(0.667, abs=1e-3)
    assert m["accuracy"] == pytest.approx(0.84)
    assert m["cost"] == 4 * 10 + 12 * 1


def test_baselines(workspace):
    df, _ = load_tickets(workspace.tickets_csv)
    majority = MajorityClass().fit(df, df["urgent_label"])
    assert majority.predict(df).sum() == 0
    rule = PhraseRule(IMPACT_PHRASES).fit(df)
    sample = pd.DataFrame({"description": ["My whole team is blocked.", "Thanks, no rush."]})
    assert rule.predict(sample).tolist() == [1, 0]


def test_manifest_is_valid_json(workspace):
    freeze_split(workspace)
    data = json.loads(workspace.split_manifest.read_text(encoding="utf-8"))
    assert set(data["ids"]) == {"train", "val"}
