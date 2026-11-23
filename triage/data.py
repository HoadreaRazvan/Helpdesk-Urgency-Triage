"""Loading, column policy and cleaning of the instructor's ticket export.

Every cleaning rule here works row by row and never looks at the label or at
statistics of other rows. That is what makes it safe to apply before the
split: no information can travel from the test period into training.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

TARGET = "urgent_label"


@dataclass(frozen=True)
class ColumnPolicy:
    role: str  # identifier | timestamp | group | feature | policy_excluded | post_submission | target
    available_at_submission: bool
    reason: str

    @property
    def is_feature(self) -> bool:
        return self.role == "feature" and self.available_at_submission


# The answer to L5 audit question 1: which columns exist when a ticket is submitted?
COLUMN_POLICY: dict[str, ColumnPolicy] = {
    "ticket_id": ColumnPolicy(
        "identifier", True, "Identifier only; it carries no information about urgency."),
    "submitted_at": ColumnPolicy(
        "timestamp", True,
        "Orders tickets and defines the time-based split. Hour and weekday are derived from it."),
    "requester_id": ColumnPolicy(
        "group", True,
        "Pseudonymous person ID. Used only to keep a requester inside one CV fold, never as a feature."),
    "requester_type": ColumnPolicy(
        "policy_excluded", True,
        "Known at submission, but urgency should depend on the problem, not on who reports it. "
        "Kept only for the subgroup check."),
    "category": ColumnPolicy("feature", True, "Chosen by the requester on the form."),
    "initial_channel": ColumnPolicy("feature", True, "How the ticket arrived."),
    "description": ColumnPolicy("feature", True, "The ticket text exactly as submitted."),
    "description_length": ColumnPolicy("feature", True, "Characters in the description."),
    "attachments_count": ColumnPolicy("feature", True, "Files attached at submission."),
    "assigned_priority": ColumnPolicy(
        "post_submission", False,
        "Set by staff during triage: it is the decision the model is meant to support."),
    "handling_team": ColumnPolicy(
        "post_submission", False, "Assigned after triage, sometimes after escalation."),
    "resolution_hours": ColumnPolicy(
        "post_submission", False, "Only known once the ticket is closed (empty for open tickets)."),
    TARGET: ColumnPolicy("target", True, "Approved label from the review panel (1 = urgent)."),
}

CATEGORIES = (
    "account_access", "billing", "data_request", "email_calendar",
    "general_inquiry", "hardware", "network", "software",
)
KNOWN_CHANNELS = ("web_form", "email", "phone", "chat", "walk_in", "mobile_app")
UNKNOWN_CHANNEL = "unknown"
# Staff type a short summary for phone and walk-in tickets, always with this prefix.
CHANNEL_PREFIXES = {"caller reports:": "phone", "walk-in:": "walk_in"}


def policy_for(column: str) -> ColumnPolicy:
    """Columns missing from the policy are excluded by default (whitelist, not blacklist)."""
    return COLUMN_POLICY.get(column, ColumnPolicy(
        "undocumented", False, "Not in the data dictionary, so excluded until someone audits it."))


def feature_columns(columns) -> list[str]:
    return [c for c in columns if policy_for(c).is_feature]


def file_sha256(path: Path) -> str:
    """Fingerprint of a file's content, independent of Windows/Unix line endings."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_raw(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def normalise_category(values: pd.Series) -> pd.Series:
    """' Account access', 'ACCOUNT_ACCESS', 'account access' -> 'account_access'."""
    return (values.astype("string").str.strip().str.lower()
            .str.replace(r"[\s\-]+", "_", regex=True))


def channel_from_prefix(description: str) -> str | None:
    text = description.strip().lower()
    for prefix, channel in CHANNEL_PREFIXES.items():
        if text.startswith(prefix):
            return channel
    return None


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Return the cleaned tickets and a log of every change, for the audit report."""
    log: list[dict] = []
    df = raw.copy()

    n = len(df)
    df = df.drop_duplicates()
    log.append({"step": "Dropped exact duplicate rows (same ticket exported twice)",
                "rows": n - len(df)})
    if df["ticket_id"].duplicated().any():
        raise ValueError("Conflicting rows share a ticket_id; resolve them by hand first.")

    before = df["category"].astype("string")
    df["category"] = normalise_category(before)
    log.append({"step": "Normalised category spelling (case, spaces, underscores)",
                "rows": int((before != df["category"]).sum())})
    unknown = sorted(set(df["category"]) - set(CATEGORIES))
    if unknown:
        raise ValueError(f"Unknown categories after normalisation: {unknown}")

    missing = df["initial_channel"].isna()
    recovered = df.loc[missing, "description"].map(channel_from_prefix)
    df.loc[recovered.dropna().index, "initial_channel"] = recovered.dropna()
    log.append({"step": "Recovered missing channel from the staff prefix "
                        "('Caller reports:' = phone, 'Walk-in:' = walk_in)",
                "rows": int(recovered.notna().sum())})
    still_missing = df["initial_channel"].isna()
    df.loc[still_missing, "initial_channel"] = UNKNOWN_CHANNEL
    log.append({"step": f"Marked remaining missing channels as '{UNKNOWN_CHANNEL}'",
                "rows": int(still_missing.sum())})

    computed = df["description"].str.len()
    present = df["description_length"].notna()
    if (computed[present] != df.loc[present, "description_length"]).any():
        raise ValueError("description_length disagrees with the description text.")
    log.append({"step": "Recomputed missing description_length from the text "
                        "(it matches the text on every row where it is present)",
                "rows": int((~present).sum())})
    df["description_length"] = computed.astype(int)

    df["submitted_at"] = pd.to_datetime(df["submitted_at"], format="%Y-%m-%d %H:%M:%S")
    df = df.sort_values(["submitted_at", "ticket_id"], kind="stable").reset_index(drop=True)
    df[TARGET] = df[TARGET].astype(int)
    if not set(df[TARGET].unique()) <= {0, 1}:
        raise ValueError("urgent_label must be 0 or 1.")
    return df, log


def load_tickets(path: Path) -> tuple[pd.DataFrame, list[dict]]:
    return clean(load_raw(path))
