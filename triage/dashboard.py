"""Everything the web interface shows, assembled from the frozen results.

The per-ticket scores come from the validation window only. The test window
appears only after it has been opened through ``triage.final``.
"""
from __future__ import annotations

import json

from .analysis import predict
from .audit import build_audit
from .config import TEST_CONFIRMATION, Paths
from .data import CATEGORIES, KNOWN_CHANNELS, TARGET, UNKNOWN_CHANNEL
from .final import sealed_test_status
from .pipeline import load_model
from .split import load_development

# Example tickets for the composer, written in the style of the dataset.
PRESETS = [
    {"name": "Team blocked", "category": "network", "initial_channel": "phone",
     "attachments_count": 0, "time": "09:40", "weekday": 1,
     "description": "Caller reports: the VPN drops every few minutes. My whole team has the same "
                    "problem. The client presentation is in one hour."},
    {"name": "Calm but urgent", "category": "account_access", "initial_channel": "web_form",
     "attachments_count": 0, "time": "08:15", "weekday": 0,
     "description": "Hello support, I can't sign in to my account since this morning. "
                    "Please treat as urgent. Thanks."},
    {"name": "Shouting", "category": "software", "initial_channel": "email",
     "attachments_count": 1, "time": "14:05", "weekday": 3,
     "description": "URGENT!!! The export button does nothing. I attached a screenshot. ASAP!!!"},
    {"name": "Routine", "category": "data_request", "initial_channel": "email",
     "attachments_count": 0, "time": "11:20", "weekday": 2,
     "description": "Hi team, Could you share the monthly statistics? Any time this month is fine. "
                    "Thanks in advance."},
    {"name": "New channel", "category": "software", "initial_channel": "mobile_app",
     "attachments_count": 0, "time": "19:30", "weekday": 4,
     "description": "The spreadsheet app crashes when I open large files. I am unable to work."},
]


def build_dashboard(paths: Paths) -> dict:
    results = json.loads((paths.reports / "validation_results.json").read_text(encoding="utf-8"))
    frozen = json.loads(paths.frozen_config.read_text(encoding="utf-8"))
    audit = build_audit(paths)
    model = load_model(paths)

    dev = load_development(paths)
    val = dev[dev["split"] == "val"].reset_index(drop=True)
    scores = predict(model, val)
    tickets = [{"id": t.ticket_id, "t": t.submitted_at.isoformat(sep=" ")[:16], "cat": t.category,
                "ch": t.initial_channel, "text": t.description, "s": round(float(s), 5),
                "y": int(getattr(t, TARGET))}
               for t, s in zip(val.itertuples(index=False), scores)]

    v = results["validation"]
    return {
        "meta": {
            "model": results["model"], "threshold": results["threshold"], "costs": results["costs"],
            "frozen_at": frozen["frozen_at"], "versions": frozen["versions"],
            "windows": results["windows"], "selection": results["selection"],
            "confirmation": TEST_CONFIRMATION,
        },
        "validation": {k: v[k] for k in (
            "tp", "fn", "fp", "tn", "n", "recall", "precision", "f1", "accuracy", "flag_rate",
            "cost_per_100", "average_precision", "roc_auc", "brier", "baselines", "sweep",
            "calibration", "sensitivity", "queue", "slices", "shifts", "errors")},
        "finalists": results["finalists"],
        "experiments": results["experiments"],
        "tone": results["tone"],
        "tickets": tickets,
        "audit": {k: audit[k] for k in (
            "rows_raw", "rows_clean", "period", "columns", "features", "cleaning", "leak_scan",
            "requesters", "drift", "train_prevalence", "windows")},
        "test": sealed_test_status(paths),
        "presets": PRESETS,
        "options": {"categories": list(CATEGORIES),
                    "channels": [*KNOWN_CHANNELS, UNKNOWN_CHANNEL]},
    }
