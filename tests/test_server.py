"""The web interface: API contract, input validation, static files and the one-shot vault."""
import json
import shutil
import threading
import urllib.error
import urllib.request

import pytest

from triage import pipeline
from triage.config import PROJECT_ROOT, TEST_CONFIRMATION, Paths
from triage.server import make_server
from triage.split import freeze_split

from .test_pipeline import FAST


@pytest.fixture(scope="module")
def base_url(tmp_path_factory):
    root = tmp_path_factory.mktemp("server")
    (root / "data").mkdir()
    shutil.copy(PROJECT_ROOT / "data" / "tickets.csv", root / "data" / "tickets.csv")
    paths = Paths(root=root)
    freeze_split(paths)
    mp = pytest.MonkeyPatch()
    mp.setattr(pipeline, "EXPERIMENTS", FAST)
    pipeline.run_development(paths, log=lambda *a, **k: None)
    server = make_server(paths, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    mp.undo()


def call(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return res.status, res.read(), res.headers.get("Content-Type", "")
    except urllib.error.HTTPError as err:
        return err.code, err.read(), err.headers.get("Content-Type", "")


TICKET = {"description": "My whole team is blocked. The deadline is today.", "category": "network",
          "initial_channel": "phone", "attachments_count": 0, "submitted_at": "2026-03-03 09:30"}


def test_page_and_assets(base_url):
    status, body, kind = call(f"{base_url}/")
    assert status == 200 and kind.startswith("text/html") and b"Triage Control Room" in body
    status, _, kind = call(f"{base_url}/js/main.js")
    assert status == 200 and kind.startswith("text/javascript")


def test_static_files_cannot_escape_the_web_folder(base_url):
    for path in ("/../triage/config.py", "/..%2Fdata%2Ftickets.csv", "/reports/../data/tickets.csv"):
        assert call(f"{base_url}{path}")[0] == 404


def test_dashboard_has_validation_only(base_url):
    status, body, _ = call(f"{base_url}/api/dashboard")
    d = json.loads(body)
    assert status == 200
    assert len(d["tickets"]) == d["meta"]["windows"]["val"]["rows"]
    assert d["test"]["used"] is False
    assert {t["t"][:7] for t in d["tickets"]} <= {"2026-05", "2026-06"}


def test_predict_explains_each_sentence(base_url):
    status, body, _ = call(f"{base_url}/api/predict", TICKET)
    r = json.loads(body)
    assert status == 200
    assert 0 <= r["score"] <= 1 and isinstance(r["flagged"], bool)
    assert [s["text"] for s in r["sentences"]] == ["My whole team is blocked.", "The deadline is today."]
    assert {f["field"] for f in r["fields"]} >= {"category", "initial_channel", "submitted_at"}


@pytest.mark.parametrize("change", [
    {"category": "nope"}, {"initial_channel": "fax"}, {"description": ""},
    {"description": "x" * 2001}, {"attachments_count": -1}, {"submitted_at": "not a date"},
])
def test_predict_rejects_bad_input(base_url, change):
    assert call(f"{base_url}/api/predict", {**TICKET, **change})[0] == 400


def test_only_known_reports_are_served(base_url):
    assert call(f"{base_url}/reports/model_card.md")[0] == 200
    assert call(f"{base_url}/reports/validation_results.md")[0] == 404


def test_vault_opens_exactly_once(base_url):
    assert call(f"{base_url}/api/test/unseal", {"confirmation": "ok"})[0] == 400
    status, body, _ = call(f"{base_url}/api/test/unseal", {"confirmation": TEST_CONFIRMATION})
    out = json.loads(body)
    assert status == 200 and out["test"]["used"] is True
    assert out["results"]["tp"] + out["results"]["fn"] + out["results"]["fp"] + out["results"]["tn"] == out["results"]["tickets"]
    assert call(f"{base_url}/api/test/unseal", {"confirmation": TEST_CONFIRMATION})[0] == 400
    dashboard = json.loads(call(f"{base_url}/api/dashboard")[1])
    assert dashboard["test"]["used"] is True and dashboard["test"]["results"]
