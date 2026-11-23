"""Time-based split, frozen in a manifest before any modelling.

The model will score *future* tickets, so it is trained on the past and judged
on the months that follow. The test window is sealed: its IDs are stored only
as a fingerprint, and no function in this module returns its rows. Only
``triage.final`` opens it, once, in L8.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import TEST_START, VAL_START, Paths
from .data import TARGET, file_sha256, load_tickets
from .markdown import write_text

DEVELOPMENT = ("train", "val")


class SplitError(RuntimeError):
    pass


def assign_windows(submitted_at: pd.Series) -> pd.Series:
    test = submitted_at >= pd.Timestamp(TEST_START)
    val = submitted_at >= pd.Timestamp(VAL_START)
    return pd.Series(np.where(test, "test", np.where(val, "val", "train")),
                     index=submitted_at.index, name="split")


def ids_digest(ids) -> str:
    return hashlib.sha256("\n".join(sorted(map(str, ids))).encode()).hexdigest()


def _window_summary(frame: pd.DataFrame, with_labels: bool) -> dict:
    summary = {
        "rows": int(len(frame)),
        "first": frame["submitted_at"].min().isoformat(sep=" "),
        "last": frame["submitted_at"].max().isoformat(sep=" "),
        "requesters": int(frame["requester_id"].nunique()),
        "ids_sha256": ids_digest(frame["ticket_id"]),
    }
    if with_labels:
        summary["urgent"] = int(frame[TARGET].sum())
    return summary


def freeze_split(paths: Paths, force: bool = False) -> dict:
    """Write the split manifest. Refuses to change it once the test set was used."""
    if paths.test_lock.exists():
        raise SplitError("The test set has already been used: the split is final.")
    if paths.split_manifest.exists() and not force:
        return read_manifest(paths)

    df, _ = load_tickets(paths.tickets_csv)
    split = assign_windows(df["submitted_at"])
    manifest = {
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_file": paths.tickets_csv.relative_to(paths.root).as_posix(),
        "data_sha256": file_sha256(paths.tickets_csv),
        "rule": {
            "train": f"submitted_at < {VAL_START}",
            "val": f"{VAL_START} <= submitted_at < {TEST_START}",
            "test": f"submitted_at >= {TEST_START} (sealed until L8)",
        },
        "grouping": "Cross-validation folds inside train are grouped by requester_id.",
        # Labels are summarised for train and validation only: the test stays unseen.
        "windows": {w: _window_summary(df[split == w], with_labels=w != "test")
                    for w in ("train", "val", "test")},
        "ids": {w: df.loc[split == w, "ticket_id"].tolist() for w in DEVELOPMENT},
    }
    paths.split_manifest.parent.mkdir(parents=True, exist_ok=True)
    write_text(paths.split_manifest, json.dumps(manifest, indent=2))
    return manifest


def read_manifest(paths: Paths) -> dict:
    if not paths.split_manifest.exists():
        raise SplitError("No frozen split yet. Run: python -m triage split")
    return json.loads(paths.split_manifest.read_text(encoding="utf-8"))


def verify_data_unchanged(paths: Paths, manifest: dict) -> None:
    if file_sha256(paths.tickets_csv) != manifest["data_sha256"]:
        raise SplitError(
            "data/tickets.csv changed after the split was frozen. Restore the original file "
            "or, before L8 only, re-freeze with: python -m triage split --force")


def load_development(paths: Paths) -> pd.DataFrame:
    """Cleaned train + validation tickets with a ``split`` column. Never the test rows."""
    manifest = read_manifest(paths)
    verify_data_unchanged(paths, manifest)
    df, _ = load_tickets(paths.tickets_csv)
    df["split"] = assign_windows(df["submitted_at"])
    dev = df[df["split"].isin(DEVELOPMENT)].reset_index(drop=True)
    for w in DEVELOPMENT:
        if ids_digest(dev.loc[dev["split"] == w, "ticket_id"]) != manifest["windows"][w]["ids_sha256"]:
            raise SplitError(f"The {w} window no longer matches the frozen manifest.")
    return dev
