"""Every setting that can change a result lives in this file.

Keeping them together means a reviewer can audit all decisions in one place,
and nothing is tuned silently somewhere else in the code.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED = 42

# --- Time-based split -------------------------------------------------------
# Calendar-month boundaries, so the split is easy to explain and to reproduce.
#   train      : 2025-09-01 .. 2026-04-30  (8 months)
#   validation : 2026-05-01 .. 2026-06-30  (2 months)
#   test       : 2026-07-01 .. 2026-08-31  (2 months, frozen, used once in L8)
VAL_START = "2026-05-01"
TEST_START = "2026-07-01"

# --- Cost of mistakes (declared before any model was trained) ---------------
# A missed urgent ticket waits in the normal queue while a person (often a whole
# team) is blocked; a false alarm costs a staff member a few minutes of reading.
# Justification and sensitivity analysis: reports/decision_note.md.
COST_FN = 5.0
COST_FP = 1.0

# --- Modelling ----------------------------------------------------------------
CV_FOLDS = 5
# Pre-registered selection rule: the tree ensemble replaces logistic regression
# only if it lowers the validation cost by more than this fraction. Otherwise
# the simpler, explainable model wins.
COMPLEXITY_MARGIN = 0.03

# --- The test set is used once ------------------------------------------------
TEST_CONFIRMATION = "I understand the test set is used once"


@dataclass(frozen=True)
class Paths:
    """All file locations, relative to one project root (tests use a temp root)."""

    root: Path = PROJECT_ROOT

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def tickets_csv(self) -> Path:
        return self.data_dir / "tickets.csv"

    @property
    def split_manifest(self) -> Path:
        return self.data_dir / "split_manifest.json"

    @property
    def artifacts(self) -> Path:
        return self.root / "artifacts"

    @property
    def model_file(self) -> Path:
        return self.artifacts / "model.joblib"

    @property
    def frozen_config(self) -> Path:
        return self.artifacts / "frozen_config.json"

    @property
    def dashboard(self) -> Path:
        return self.artifacts / "dashboard.json"

    @property
    def test_lock(self) -> Path:
        return self.artifacts / "TEST_SET_USED.lock"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def test_results(self) -> Path:
        return self.reports / "test_results.json"
