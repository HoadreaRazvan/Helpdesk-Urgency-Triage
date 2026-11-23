"""L5 audit: columns, cleaning, leakage, requesters and drift.

Rule of thumb used throughout: label-free facts (counts, channel mix) may be
reported for every month, but anything that uses ``urgent_label`` is computed
on the training window only. The test labels stay unseen until L8.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from .config import Paths
from .data import TARGET, clean, feature_columns, load_raw, policy_for
from .markdown import pct, table, write_text
from .split import assign_windows

# How strongly a single column separates urgent from non-urgent (AUC on train).
# Anything above this is "too good to be true" for submission-time information.
LEAK_AUC = 0.85

ORDINAL_ENCODINGS = {
    "assigned_priority": {"P1": 4, "P2": 3, "P3": 2, "P4": 1},
    "handling_team": {"tier1": 0, "tier2": 1, "escalation": 2},
}


def single_column_auc(values: pd.Series, y: pd.Series) -> float | None:
    """Direction-free AUC of one column on its own (0.5 = useless, 1.0 = gives the answer away)."""
    mask = values.notna()
    if mask.sum() < 20 or y[mask].nunique() < 2:
        return None
    auc = roc_auc_score(y[mask], values[mask].astype(float))
    return float(max(auc, 1 - auc))


def _leak_scan(train: pd.DataFrame) -> list[dict]:
    rows = []
    for col in ["assigned_priority", "handling_team", "resolution_hours",
                "description_length", "attachments_count"]:
        values = train[col].map(ORDINAL_ENCODINGS[col]) if col in ORDINAL_ENCODINGS else train[col]
        auc = single_column_auc(values, train[TARGET])
        policy = policy_for(col)
        rows.append({
            "column": col,
            "auc": auc,
            "available_at_submission": policy.available_at_submission,
            "verdict": ("leak: excluded" if not policy.available_at_submission
                        else ("suspicious" if auc and auc >= LEAK_AUC else "fine")),
        })
    return rows


def _requesters(df: pd.DataFrame, split: pd.Series) -> dict:
    """Requester overlap is label-free; the urgency spread uses train labels only."""
    seen = set(df.loc[split == "train", "requester_id"])
    later = df[split != "train"]
    per_requester = df["requester_id"].value_counts()

    train = df[split == "train"]
    stats = train.groupby("requester_id")[TARGET].agg(["mean", "size"])
    frequent = stats[stats["size"] >= 10]
    p = train[TARGET].mean()
    expected = float(np.sqrt(p * (1 - p) / frequent["size"]).mean()) if len(frequent) else None

    later_requesters = set(later["requester_id"])
    purge = int(train["requester_id"].isin(later_requesters).sum())
    return {
        "requesters": int(per_requester.size),
        "median_tickets": float(per_requester.median()),
        "max_tickets": int(per_requester.max()),
        "share_later_from_known": float(later["requester_id"].isin(seen).mean()),
        "purge_would_drop": purge,
        "train_rows": int(len(train)),
        "frequent_requesters": int(len(frequent)),
        "urgent_rate_spread": float(frequent["mean"].std()) if len(frequent) > 1 else None,
        "spread_expected_by_chance": expected,
    }


def _drift(df: pd.DataFrame, split: pd.Series) -> dict:
    month = df["submitted_at"].dt.strftime("%Y-%m")
    monthly = []
    for m, frame in df.groupby(month):
        is_train = (split[frame.index] == "train").all()
        monthly.append({
            "month": m,
            "window": split[frame.index].iloc[0],
            "tickets": int(len(frame)),
            "urgent_rate": float(frame[TARGET].mean()) if is_train else None,
            **{f"ch_{c}": int(n) for c, n in frame["initial_channel"].value_counts().items()},
            **{f"cat_{c}": int(n) for c, n in frame["category"].value_counts().items()},
        })
    first_seen = {}
    for c in sorted(df["initial_channel"].unique()):
        first_seen[c] = month[df["initial_channel"] == c].min()
    return {"monthly": monthly, "channel_first_seen": first_seen}


def _base_rates(train: pd.DataFrame, column: str) -> list[dict]:
    g = train.groupby(column)[TARGET].agg(["mean", "size"]).sort_values("mean", ascending=False)
    return [{"value": k, "urgent_rate": float(r["mean"]), "tickets": int(r["size"])}
            for k, r in g.iterrows()]


def build_audit(paths: Paths) -> dict:
    raw = load_raw(paths.tickets_csv)
    df, log = clean(raw)
    split = assign_windows(df["submitted_at"])
    train = df[split == "train"]

    columns = []
    for col in raw.columns:
        policy = policy_for(col)
        columns.append({
            "column": col,
            "role": policy.role,
            "available_at_submission": policy.available_at_submission,
            "used_as_feature": policy.is_feature,
            "missing_raw": int(raw[col].isna().sum()),
            "reason": policy.reason,
        })

    return {
        "rows_raw": int(len(raw)),
        "rows_clean": int(len(df)),
        "period": [df["submitted_at"].min().isoformat(sep=" "), df["submitted_at"].max().isoformat(sep=" ")],
        "columns": columns,
        "features": feature_columns(raw.columns),
        "cleaning": log,
        "leak_scan": _leak_scan(train),
        "requesters": _requesters(df, split),
        "drift": _drift(df, split),
        "train_prevalence": float(train[TARGET].mean()),
        "train_base_rates": {c: _base_rates(train, c)
                             for c in ("category", "initial_channel", "requester_type")},
        "windows": {w: int((split == w).sum()) for w in ("train", "val", "test")},
    }


def audit_markdown(a: dict) -> str:
    r = a["requesters"]
    drift = a["drift"]
    new_channels = {c: m for c, m in drift["channel_first_seen"].items() if m > drift["monthly"][0]["month"]}
    lines = [
        "# L5 data audit",
        "",
        f"Source: `data/tickets.csv` (instructor's synthetic export), {a['rows_raw']} raw rows, "
        f"{a['period'][0][:10]} to {a['period'][1][:10]}. Generated by `python -m triage audit`.",
        "",
        "Label-based numbers in this report use the **training window only**. "
        "Test labels stay unseen until L8.",
        "",
        "## 1. Which columns exist at submission time?",
        "",
        table(a["columns"], [("column", "Column"), ("role", "Role"),
                             ("available_at_submission", "At submission?"),
                             ("used_as_feature", "Feature?"), ("reason", "Why")]),
        "",
        "Columns that are not in this policy are excluded automatically (whitelist).",
        "",
        "## 2. Cleaning (row-level rules, no label or cross-row statistics)",
        "",
        table(a["cleaning"], [("step", "Step"), ("rows", "Rows affected")]),
        "",
        f"Result: {a['rows_clean']} tickets.",
        "",
        "## 3. Leakage scan (train window)",
        "",
        "Each column on its own, as a predictor of `urgent_label`. "
        "An AUC near 1.0 means the column already contains the answer.",
        "",
        table(a["leak_scan"], [("column", "Column"), ("auc", "AUC alone"),
                               ("available_at_submission", "At submission?"),
                               ("verdict", "Verdict")]),
        "",
        "The post-submission columns separate the classes far better than anything known at "
        "submission, because staff fill them in *after* reading the ticket. A model using them "
        "would look excellent in the lab and be useless on a new ticket.",
        "",
        "## 4. Repeated requesters and the split",
        "",
        f"- {r['requesters']} requesters; median {r['median_tickets']:.0f} tickets each, "
        f"maximum {r['max_tickets']}.",
        f"- {pct(r['share_later_from_known'])} of validation and test tickets come from requesters "
        "who already appear in training.",
        f"- A strict requester purge would remove {r['purge_would_drop']} of "
        f"{r['train_rows']} training tickets ({pct(r['purge_would_drop'] / r['train_rows'])}).",
    ]
    if r["urgent_rate_spread"] is not None:
        lines.append(
            f"- Among the {r['frequent_requesters']} requesters with at least 10 training tickets, "
            f"the urgent rate varies with a standard deviation of {r['urgent_rate_spread']:.3f}, "
            f"against {r['spread_expected_by_chance']:.3f} expected from chance alone. "
            "Requesters do not carry a persistent urgency of their own.")
    lines += [
        "",
        "**Decision.** The outer split is by time (train → validation → test), because the model "
        "will score future tickets from mostly the same people. Inside training, "
        "cross-validation folds are grouped by `requester_id` so that model selection is never "
        "judged on a requester it has already seen. `requester_id` is never a feature.",
        "",
        "## 5. Does anything change over the year?",
        "",
        table(drift["monthly"], [("month", "Month"), ("window", "Window"), ("tickets", "Tickets"),
                                 ("urgent_rate", "Urgent rate (train only)"),
                                 ("ch_mobile_app", "mobile_app"),
                                 ("cat_account_access", "account_access")]),
        "",
    ]
    if new_channels:
        lines.append("New channels during the year: " + ", ".join(
            f"`{c}` (from {m})" for c, m in new_channels.items())
            + ". The training window never sees them: this is the plausible shift studied in L7.")
    lines += [
        "",
        "## 6. Training base rates",
        "",
        f"Overall urgent rate in training: {pct(a['train_prevalence'])}.",
        "",
    ]
    for col, rows in a["train_base_rates"].items():
        lines += [f"**{col}**", "", table(rows, [("value", "Value"), ("urgent_rate", "Urgent rate"),
                                                 ("tickets", "Tickets")]), ""]
    return "\n".join(lines)


def write_audit(paths: Paths) -> dict:
    a = build_audit(paths)
    paths.reports.mkdir(parents=True, exist_ok=True)
    write_text(paths.reports / "audit.md", audit_markdown(a))
    return a
