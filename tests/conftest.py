import shutil

import pytest

from triage.config import PROJECT_ROOT, Paths


@pytest.fixture
def workspace(tmp_path) -> Paths:
    """A throw-away project root with a copy of the dataset, so tests never touch real artifacts."""
    (tmp_path / "data").mkdir()
    shutil.copy(PROJECT_ROOT / "data" / "tickets.csv", tmp_path / "data" / "tickets.csv")
    return Paths(root=tmp_path)
