"""Local web interface: ``python -m triage serve``.

Standard library only (no web framework to install). It listens on
127.0.0.1, so the interface is reachable from this computer only.
"""
from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

import pandas as pd

from .config import PROJECT_ROOT, Paths
from .dashboard import build_dashboard
from .data import CATEGORIES, KNOWN_CHANNELS, UNKNOWN_CHANNEL
from .explain import explain
from .final import FinalTestError, run_final_test
from .pipeline import load_model

WEB_ROOT = PROJECT_ROOT / "web"
MAX_TEXT = 2000
MAX_BODY = 64 * 1024
REPORTS = {"model_card", "decision_note", "experiments", "validation_report", "error_analysis",
           "audit", "baselines"}


class BadRequest(ValueError):
    pass


class App:
    """State shared by all requests: the frozen model, its threshold and the dashboard."""

    def __init__(self, paths: Paths):
        self.paths = paths
        self.lock = threading.Lock()
        self.reload()

    def reload(self) -> None:
        self.model = load_model(self.paths)
        self.dashboard = build_dashboard(self.paths)
        self.threshold = self.dashboard["meta"]["threshold"]
        self.dashboard_json = json.dumps(self.dashboard).encode("utf-8")

    def predict(self, body: dict) -> dict:
        ticket = parse_ticket(body)
        result = explain(self.model, ticket)
        return {**result, "threshold": self.threshold, "flagged": result["score"] >= self.threshold,
                "advisory": "A suggestion to read this ticket first. Staff decide."}

    def unseal(self, body: dict) -> dict:
        with self.lock:
            results = run_final_test(self.paths, str(body.get("confirmation", "")))
            self.reload()
        return {"results": results, "test": self.dashboard["test"]}


def parse_ticket(body: dict) -> dict:
    text = str(body.get("description", "")).strip()
    if not text:
        raise BadRequest("The description is empty.")
    if len(text) > MAX_TEXT:
        raise BadRequest(f"The description is longer than {MAX_TEXT} characters.")
    category = str(body.get("category", ""))
    if category not in CATEGORIES:
        raise BadRequest(f"Unknown category: {category}")
    channel = str(body.get("initial_channel", ""))
    if channel not in (*KNOWN_CHANNELS, UNKNOWN_CHANNEL):
        raise BadRequest(f"Unknown channel: {channel}")
    try:
        attachments = int(body.get("attachments_count", 0))
        submitted = pd.Timestamp(str(body.get("submitted_at", "")))
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"Invalid field: {exc}") from exc
    if not 0 <= attachments <= 20 or pd.isna(submitted):
        raise BadRequest("attachments_count must be 0–20 and submitted_at a valid date.")
    return {"category": category, "initial_channel": channel, "description": text,
            "attachments_count": attachments, "submitted_at": submitted}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "TriageLab/1.0"

        def log_message(self, fmt, *args):  # keep the console quiet
            pass

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise BadRequest("Request too large.")
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError as exc:
                raise BadRequest("Invalid JSON.") from exc
            if not isinstance(data, dict):
                raise BadRequest("Expected a JSON object.")
            return data

        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            if path == "/api/dashboard":
                return self._send(HTTPStatus.OK, app.dashboard_json, "application/json; charset=utf-8")
            if path.startswith("/reports/") and path.endswith(".md"):
                name = path[len("/reports/"):-3]
                file = app.paths.reports / f"{name}.md"
                if name in REPORTS and file.exists():
                    return self._send(HTTPStatus.OK, file.read_bytes(), "text/plain; charset=utf-8")
                return self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown report."})
            return self._static(path)

        def do_POST(self):
            path = urlparse(self.path).path
            try:
                if path == "/api/predict":
                    return self._json(HTTPStatus.OK, app.predict(self._body()))
                if path == "/api/test/unseal":
                    return self._json(HTTPStatus.OK, app.unseal(self._body()))
                return self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint."})
            except (BadRequest, FinalTestError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        def _static(self, path: str):
            relative = "index.html" if path in ("", "/") else path.lstrip("/")
            file = (WEB_ROOT / relative).resolve()
            if not file.is_relative_to(WEB_ROOT.resolve()) or not file.is_file():
                return self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            kind = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            if file.suffix == ".js":
                kind = "text/javascript"
            if kind.startswith("text/") or kind == "text/javascript":
                kind += "; charset=utf-8"
            return self._send(HTTPStatus.OK, file.read_bytes(), kind)

    return Handler


def ensure_trained(paths: Paths, log=print) -> None:
    if paths.model_file.exists() and (paths.reports / "validation_results.json").exists():
        return
    from .pipeline import run_development
    from .split import freeze_split

    log("No trained model yet: running the L6–L7 pipeline once (about half a minute)...")
    freeze_split(paths)
    run_development(paths, log=log)


def make_server(paths: Paths, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    ensure_trained(paths)
    return ThreadingHTTPServer((host, port), make_handler(App(paths)))


def serve(paths: Paths, port: int = 8000, open_browser: bool = True) -> None:
    server = make_server(paths, port=port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Triage control room: {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
