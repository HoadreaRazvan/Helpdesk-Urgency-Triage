"""Model inputs, built only from columns that exist when a ticket is submitted.

``make_X`` is the single gateway between the data and every model. It checks
each source column against the audited policy, so a post-submission column
cannot slip into a model even by accident.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import policy_for

# model input -> raw column it is computed from
SOURCES = {
    "category": "category",
    "initial_channel": "initial_channel",
    "description": "description",
    "log_length": "description_length",
    "attachments": "attachments_count",
    "hour_sin": "submitted_at",
    "hour_cos": "submitted_at",
    "is_weekend": "submitted_at",
    "after_hours": "submitted_at",
    "exclamations": "description",
    "caps_ratio": "description",
}
TEXT = "description"
CATEGORICAL = ["category", "initial_channel"]
NUMERIC = ["log_length", "attachments", "hour_sin", "hour_cos"]
FLAGS = ["is_weekend", "after_hours"]
# Tone of the text: TF-IDF drops punctuation and case, so "URGENT!!!" and "Urgent." look the same.
TONE = ["exclamations", "caps_ratio"]

BUSINESS_HOURS = (8, 18)


class LeakageError(RuntimeError):
    pass


def check_sources() -> None:
    for model_input, column in SOURCES.items():
        policy = policy_for(column)
        if not policy.available_at_submission or policy.role not in ("feature", "timestamp"):
            raise LeakageError(f"{model_input} would be built from '{column}' ({policy.role}).")


def make_X(df: pd.DataFrame) -> pd.DataFrame:
    check_sources()
    ts = pd.to_datetime(df["submitted_at"])
    hour = ts.dt.hour + ts.dt.minute / 60
    weekend = ts.dt.dayofweek >= 5
    after = weekend | (hour < BUSINESS_HOURS[0]) | (hour >= BUSINESS_HOURS[1])
    text = df["description"].astype(str)
    letters = text.str.count(r"[A-Za-z]").clip(lower=1)
    return pd.DataFrame({
        "category": df["category"].astype(str).to_numpy(),
        "initial_channel": df["initial_channel"].astype(str).to_numpy(),
        "description": df["description"].astype(str).to_numpy(),
        "log_length": np.log1p(df["description_length"].to_numpy(dtype=float)),
        "attachments": df["attachments_count"].to_numpy(dtype=float),
        "hour_sin": np.sin(2 * np.pi * hour / 24).to_numpy(),
        "hour_cos": np.cos(2 * np.pi * hour / 24).to_numpy(),
        "is_weekend": weekend.to_numpy(dtype=float),
        "after_hours": after.to_numpy(dtype=float),
        "exclamations": np.log1p(text.str.count("!").to_numpy(dtype=float)),
        "caps_ratio": (text.str.count(r"[A-Z]") / letters).to_numpy(dtype=float),
    }, index=df.index)
