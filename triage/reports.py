"""Human-readable deliverables, regenerated from the stored results.

experiments.md / .csv   L6  experiment table
validation_report.md    L7  ladder, threshold, calibration, queue, shifts, subgroups
error_analysis.md       L7  the most confident mistakes, with hypotheses
decision_note.md        L7  why this model, this threshold, these costs
model_card.md           L8  intended use, prohibited use, performance, limits
"""
from __future__ import annotations

import csv
import io
import json

from .baselines import DEADLINE_PHRASES, IMPACT_PHRASES
from .config import TEST_CONFIRMATION, Paths
from .markdown import pct, table, write_text

LADDER_COLUMNS = [("name", "Model"), ("recall", "Recall"), ("precision", "Precision"), ("f1", "F1"),
                  ("accuracy", "Accuracy"), ("flag_rate", "Flagged"), ("tp", "TP"), ("fn", "FN"),
                  ("fp", "FP"), ("tn", "TN"), ("cost_per_100", "Cost / 100")]
EXPERIMENT_CSV = ["id", "name", "family", "params", "allowed", "selected", "finalist",
                  "cv_average_precision", "cv_average_precision_std", "cv_roc_auc", "cv_brier",
                  "cv_cost_per_100", "cv_recall", "cv_precision", "val_threshold",
                  "val_cost_per_100", "val_average_precision", "val_roc_auc", "note"]


def prevalence(r: dict, window: str) -> float:
    w = r["windows"][window]
    return w["urgent"] / w["rows"]


def _experiment(r: dict, exp_id: str) -> dict:
    return next(e for e in r["experiments"] if e["id"] == exp_id)


def weak_channels(r: dict, margin: float = 0.1) -> list[str]:
    overall = r["finalists"][r["selection"]["chosen"]]["recall"]
    return [s["value"] for s in r["validation"]["slices"]
            if s["slice"] == "initial_channel" and s["enough_data"] and s["recall"] < overall - margin]


def _load(paths: Paths) -> tuple[dict, dict | None]:
    val = json.loads((paths.reports / "validation_results.json").read_text(encoding="utf-8"))
    test = (json.loads(paths.test_results.read_text(encoding="utf-8"))
            if paths.test_results.exists() else None)
    return val, test


def ladder(r: dict) -> list[dict]:
    v = r["validation"]
    rows = [b for b in v["baselines"] if b["id"] != "shouting_rule"]
    for role in ("A", "B"):
        f = r["finalists"][role]
        mark = " ✔ selected" if r["selection"]["chosen"] == role else ""
        rows.append({**f, "name": f"{f['name']} ({f['id']}, t={f['threshold']:.2f}){mark}"})
    rows.append(next(b for b in v["baselines"] if b["id"] == "shouting_rule"))
    return rows


# --------------------------------------------------------------------------- L6
def experiments_md(r: dict) -> str:
    rows = []
    for e in r["experiments"]:
        tag = " ✔" if e.get("selected") else (" (finalist)" if e.get("finalist") else "")
        tag = " ✘ excluded" if not e["allowed"] else tag
        rows.append({**e, "label": f"`{e['id']}`{tag}",
                     "ap": f"{e['cv_average_precision']:.3f} ± {e['cv_average_precision_std']:.3f}"})
    return "\n".join([
        "# L6 experiment table",
        "",
        f"Every row was trained on the training window only ({r['windows']['train']['rows']} tickets), "
        "with 5-fold cross-validation **grouped by requester**. Preprocessing (TF-IDF, one-hot, "
        "scaling) sits inside the pipeline, so it is refitted on the four training folds of every round.",
        "",
        "- **CV AP**: average precision, the area under the precision–recall curve. It is threshold-free "
        "and honest under class imbalance. Higher is better.",
        "- **CV cost / 100**: cost per 100 tickets when each fold is cut at the cost-derived threshold "
        f"{r['costs']['fp'] / (r['costs']['fp'] + r['costs']['fn']):.3f} (FN = {r['costs']['fn']:g}, "
        f"FP = {r['costs']['fp']:g}). Lower is better.",
        "- **Brier**: mean squared error of the scores as probabilities. Lower is better.",
        "",
        table(rows, [("label", "Experiment"), ("name", "Family"), ("params", "Settings"),
                     ("ap", "CV AP"), ("cv_roc_auc", "CV AUC"), ("cv_brier", "Brier"),
                     ("cv_cost_per_100", "CV cost / 100"), ("note", "Note")]),
        "",
        f"Selection rule (fixed before validation): {r['selection']['rule']}",
        "",
        "Machine-readable version: `reports/experiments.csv`.",
        "",
    ])


def experiments_csv(r: dict) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EXPERIMENT_CSV, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for e in r["experiments"]:
        writer.writerow({k: (round(v, 5) if isinstance(v, float) else v) for k, v in e.items()})
    return buf.getvalue()


# --------------------------------------------------------------------------- L7
def validation_md(r: dict) -> str:
    v = r["validation"]
    q = v["queue"]
    cal = v["calibration"]
    sweep_rows = [s for s in v["sweep"] if s["threshold"] in
                  (0.03, 0.05, 0.07, 0.09, 0.1, 0.12, 0.15, 0.2, 0.3, 0.4, 0.5)
                  or s["threshold"] == r["threshold"]]
    for s in sweep_rows:
        s["mark"] = "◀ chosen" if s["threshold"] == r["threshold"] else ""
    slice_rows = [s for s in v["slices"] if s["slice"] in ("requester_type", "initial_channel", "month")]
    return "\n".join([
        "# L7 validation report",
        "",
        f"Validation window: {r['windows']['val']['first'][:10]} to {r['windows']['val']['last'][:10]}, "
        f"{r['windows']['val']['rows']} tickets, {r['windows']['val']['urgent']} urgent "
        f"({pct(r['windows']['val']['urgent'] / r['windows']['val']['rows'])}).",
        "",
        "## 1. The model ladder",
        "",
        table(ladder(r), LADDER_COLUMNS),
        "",
        f"The majority baseline is right {pct(v['baselines'][0]['accuracy'], 0)} of the time and catches "
        "no urgent ticket at all: accuracy hides exactly what the client cares about. The models are "
        "compared on cost, recall and precision instead.",
        "",
        "## 2. Threshold",
        "",
        f"Costs declared before modelling: missed urgent ticket (FN) = {r['costs']['fn']:g}, false alarm "
        f"(FP) = {r['costs']['fp']:g}. Chosen threshold: **{r['threshold']:.2f}**, the minimum of the cost "
        "curve smoothed over ±0.02.",
        "",
        table(sweep_rows, [("threshold", "Threshold"), ("recall", "Recall"), ("precision", "Precision"),
                           ("flag_rate", "Flagged"), ("fn", "FN"), ("fp", "FP"), ("cost", "Cost"),
                           ("smoothed_cost", "Smoothed"), ("mark", "")]),
        "",
        "Sensitivity: the threshold that the same rule would pick for other cost ratios.",
        "",
        table(v["sensitivity"], [("cost_ratio", "FN : FP"), ("threshold", "Threshold"),
                                 ("recall", "Recall"), ("precision", "Precision"),
                                 ("flag_rate", "Flagged")]),
        "",
        "## 3. Calibration",
        "",
        f"Expected calibration error {cal['ece']:.3f}, Brier score {cal['brier']:.3f}. Mean score "
        f"{cal['mean_score']:.3f} against an observed urgent rate of {cal['urgent_rate']:.3f}.",
        "",
        table(cal["bins"], [("low", "Score from"), ("high", "to"), ("count", "Tickets"),
                            ("mean_score", "Mean score"), ("urgent_rate", "Actually urgent")]),
        "",
        f"Validation has {'more' if prevalence(r, 'val') > prevalence(r, 'train') else 'fewer'} urgent "
        f"tickets than training ({pct(prevalence(r, 'val'))} against {pct(prevalence(r, 'train'))}), "
        "so the scores are shifted accordingly. The threshold was chosen on validation, which already "
        "takes this offset into account. Show the score to staff as a ranking signal, not as an exact "
        "probability.",
        "",
        "## 4. What the flag changes in the queue",
        "",
        f"On an average day ({q['tickets_per_day']:.1f} tickets), the model flags {q['flags_per_day']:.1f}. "
        f"An urgent ticket has on average **{q['urgent_ahead_fifo']:.1f}** tickets ahead of it in "
        f"first-come-first-served order, and **{q['urgent_ahead_flagged']:.1f}** when flagged tickets are "
        f"read first. {pct(q['urgent_in_top3_flagged'])} of urgent tickets are among the first three "
        f"read each day, against {pct(q['urgent_in_top3_fifo'])} without the flag.",
        "",
        "## 5. Plausible shifts",
        "",
        table(v["shifts"], [("name", "Scenario"), ("kind", "Kind"), ("recall", "Recall"),
                            ("precision", "Precision"), ("flag_rate", "Flagged"),
                            ("cost_per_100", "Cost / 100"), ("note", "Note")]),
        "",
        "## 6. Subgroups and time slices",
        "",
        "Recall and precision are reported only for slices with at least 30 tickets and 5 urgent ones. "
        "`requester_type` is not a model input; it is checked here to see whether one group of people "
        "is served worse.",
        "",
        table(slice_rows, [("slice", "Slice"), ("value", "Value"), ("tickets", "Tickets"),
                           ("urgent", "Urgent"), ("recall", "Recall"), ("precision", "Precision"),
                           ("flag_rate", "Flagged")]),
        "",
        "## 7. Errors",
        "",
        f"{len(v['errors'])} mistakes are inspected one by one in [error_analysis.md](error_analysis.md).",
        "",
    ])


def errors_md(r: dict) -> str:
    v = r["validation"]
    lines = [
        "# L7 error analysis",
        "",
        f"The {len(v['errors'])} most confident mistakes on validation at threshold {r['threshold']:.2f}: "
        "urgent tickets with the lowest scores (missed) and non-urgent tickets with the highest scores "
        "(false alarms).",
        "",
        "*Effect* is how much the urgency score drops when that piece of evidence is removed "
        "(occlusion). The hypotheses are generated as a starting point: **the team must confirm or "
        "correct each one** in the *Team note* line.",
        "",
    ]
    for i, e in enumerate(v["errors"], 1):
        kind = "Missed urgent ticket (FN)" if e["kind"] == "missed" else "False alarm (FP)"
        cues = sorted(e["sentences"] + [{"text": f"{f['field']} = {f['value']}", "effect": f["effect"]}
                                        for f in e["fields"]], key=lambda c: -abs(c["effect"]))[:4]
        lines += [
            f"## {i}. {kind} · `{e['ticket_id']}` · score {e['score']:.3f}",
            "",
            f"{e['submitted_at']} · {e['category']} · {e['initial_channel']} · label {e['label']}",
            "",
            f"> {e['description']}",
            "",
            "Strongest cues: " + "; ".join(f"\"{c['text']}\" {c['effect']:+.2f}" for c in cues),
            "",
            f"**Hypothesis.** {e['hypothesis']}",
            "",
            "**Team note.** _to be completed_",
            "",
        ]
    return "\n".join(lines)


def decision_md(r: dict) -> str:
    v = r["validation"]
    a, b = r["finalists"]["A"], r["finalists"]["B"]
    rule = next(x for x in v["baselines"] if x["id"] == "keyword_rule")
    q = v["queue"]
    chosen = r["finalists"][r["selection"]["chosen"]]
    sens_lo, sens_hi = v["sensitivity"][0], v["sensitivity"][-2]
    with_text = _experiment(r, "logreg_C1")["cv_average_precision"]
    no_text = _experiment(r, "logreg_C1_no_text")["cv_average_precision"]
    plain, tone = _experiment(r, "logreg_C10"), _experiment(r, "logreg_C10_tone")
    shout = next(x for x in v["baselines"] if x["id"] == "shouting_rule")
    leak = next(e for e in r["experiments"] if not e["allowed"])
    return "\n".join([
        "# Decision note",
        "",
        "## Decision",
        "",
        f"- **Model:** {r['model']['name']} (`{r['model']['id']}`, {r['model']['params']}), "
        "TF-IDF on the description plus category, channel, length, attachments and time of day.",
        f"- **Threshold:** {r['threshold']:.2f}. A ticket whose score is at or above it is flagged "
        "for urgent review.",
        f"- **Costs:** a missed urgent ticket counts {r['costs']['fn']:g}, a false alarm counts "
        f"{r['costs']['fp']:g}.",
        "- **Frozen** in `artifacts/frozen_config.json` before the test window is opened.",
        "",
        "## What staff do with the flag",
        "",
        "Flagged tickets are read first within the day's queue. The reader confirms the urgency and "
        "escalates, or dismisses the flag and leaves the ticket in its normal place. Nothing happens "
        "automatically: no ticket is closed, refused, delayed or re-routed by the model, and a ticket "
        "without the flag is handled exactly as today.",
        "",
        "## Why these costs",
        "",
        "A missed urgent ticket waits in the normal queue while a person, and often a team "
        "(\"my whole team has the same problem\", \"customers are calling us\"), cannot work. A false "
        "alarm costs a few minutes: someone reads the ticket earlier than its turn and moves on. We "
        f"value a missed urgent ticket at about {r['costs']['fn']:g} false alarms. This is a product "
        "decision for the client to confirm; the sensitivity table below shows what other ratios "
        "would mean.",
        "",
        table(v["sensitivity"], [("cost_ratio", "FN : FP"), ("threshold", "Threshold"),
                                 ("recall", "Recall"), ("precision", "Precision"),
                                 ("flag_rate", "Flagged")]),
        "",
        f"A ratio of {sens_hi['cost_ratio']} : 1 would flag {pct(sens_hi['flag_rate'], 0)} of all "
        "tickets, and a flag on most tickets stops meaning anything. A ratio of "
        f"{sens_lo['cost_ratio']} : 1 would catch only {pct(sens_lo['recall'], 0)} of urgent tickets.",
        "",
        "## Why this threshold",
        "",
        "Thresholds from 0.01 to 0.99 were swept on the **validation** window only. On 660 tickets "
        "the raw cost curve is jagged: a dip can come from four or five tickets. We pick the minimum "
        "of the curve averaged over ±0.02, so the decision does not hinge on that noise.",
        "",
        f"At {r['threshold']:.2f}: recall {chosen['recall']:.2f}, precision {chosen['precision']:.2f}, "
        f"{pct(chosen['flag_rate'])} of tickets flagged, about {q['flags_per_day']:.1f} flags on a "
        f"day of {q['tickets_per_day']:.1f} tickets.",
        "",
        "## Why this model",
        "",
        f"- Model A, `{a['id']}`: validation cost {a['cost_per_100']:.1f} per 100 tickets, "
        f"average precision {a['average_precision']:.3f}.",
        f"- Model B, `{b['id']}`: validation cost {b['cost_per_100']:.1f} per 100 tickets, "
        f"average precision {b['average_precision']:.3f}.",
        f"- Keyword rule: cost {rule['cost_per_100']:.1f} per 100 tickets, recall {rule['recall']:.2f}.",
        "",
        f"Rule fixed in advance: {r['selection']['rule']} "
        + ("Model A is both cheaper and simpler, so the margin never came into play"
           if b["cost_per_100"] >= a["cost_per_100"] else
           "The tree ensemble is cheaper, but not by enough to give up interpretability"
           if r["selection"]["chosen"] == "A" else
           "The tree ensemble cleared that bar")
        + ("." if r["selection"]["chosen"] == "B" else
           ": every weight can be read, and each flag can be explained sentence by sentence."),
        "",
        "Text carries most of the signal: without it, the same logistic regression (C=1) drops from a "
        f"CV average precision of {with_text:.2f} to {no_text:.2f}. What matters most is impact "
        "(people cannot work) and time pressure (a deadline today).",
        "",
        "## The word \"urgent\" is not the signal; the tone is",
        "",
        f"In training ({pct(prevalence(r, 'train'))} urgent overall), the same word means opposite things "
        "depending on how it is written:",
        "",
        table(r["tone"], [("style", "Style"), ("phrase", "Phrase in the ticket"), ("tickets", "Tickets"),
                          ("urgent_rate", "Urgent")]),
        "",
        "The naive \"urgent / ASAP\" rule matches all three styles, which is why it catches only "
        f"{pct(shout['recall'], 0)} of urgent tickets. Word pairs (TF-IDF bigrams such as \"treat as\" "
        "and \"very urgent\") let the model tell them apart. Explicit tone features (exclamation marks, "
        f"share of capitals) changed CV average precision by {tone['cv_average_precision'] - plain['cv_average_precision']:+.3f} "
        f"(fold-to-fold spread ±{plain['cv_average_precision_std']:.2f}), so the word pairs already carry "
        "most of it."
        + (" The gain is within noise, but the rule fixed in advance takes the best CV score, so the "
           "selected model includes them." if r["model"]["id"] == tone["id"] else ""),
        "",
        "## Split and features (from the L5 audit)",
        "",
        "- Time-based split: train Sep 2025 – Apr 2026, validation May – Jun 2026, test Jul – Aug 2026. "
        "CV folds inside training are grouped by requester. A strict requester purge would delete 88% "
        "of training and is not needed: requesters show no persistent urgency of their own.",
        "- Excluded as post-submission: `assigned_priority`, `handling_team`, `resolution_hours`. With "
        f"them, a model reaches a CV AUC of {leak['cv_roc_auc']:.3f}: the leakage demo in the "
        "experiment table.",
        "- Excluded by policy: `requester_type`. Urgency should depend on the problem, not on who "
        "reports it. It is used only to check that no group is served worse.",
        "",
        "## Transparency",
        "",
        "Before the split code existed, a first exploration of the CSV looked at urgent rates over the "
        "whole year, test months included. Every label-based choice in the code uses the training or "
        "validation window only. The keyword rule was written by hand from domain reasoning (impact "
        f"words such as {', '.join(f'“{p}”' for p in IMPACT_PHRASES[:3])} and time-pressure words "
        f"such as {', '.join(f'“{p}”' for p in DEADLINE_PHRASES[:3])}). If that early look influenced it, "
        "the effect is to make the baseline *harder* to beat, not easier.",
        "",
        "The code that opens the test set is exercised by the automated tests on throw-away copies of "
        "the project, and it was run once more on a copy to check the web interface's vault. Every "
        "one of those runs came after the model, threshold and costs were frozen, and nothing was "
        "changed afterwards. The official opening in L8 reproduces the same numbers, because the "
        "frozen model is deterministic.",
        "",
    ])


# --------------------------------------------------------------------------- L8
def model_card_md(r: dict, test: dict | None) -> str:
    v = r["validation"]
    chosen = r["finalists"][r["selection"]["chosen"]]
    shifts = {s["id"]: s for s in v["shifts"]}
    weak = weak_channels(r)
    if test is None:
        test_section = [
            "**Not run yet.** The test window (Jul – Aug 2026, "
            f"{r['windows']['test']['rows']} tickets) is sealed. It is opened once, in L8, with "
            f"`python -m triage test --confirm \"{TEST_CONFIRMATION}\"` or the vault in the web app. "
            "This card is regenerated with the results.",
        ]
    else:
        rows = [{**b} for b in test["baselines"] if b["id"] != "shouting_rule"]
        rows.append({**test, "name": f"{r['model']['name']} (t={test['threshold']:.2f})"})
        test_section = [
            f"Opened once on {test['opened_at'][:10]} with the frozen settings. {test['tickets']} tickets, "
            f"{test['period'][0][:10]} to {test['period'][1][:10]}.",
            "",
            table(rows, LADDER_COLUMNS),
            "",
            f"Average precision {test['average_precision']:.3f}, ROC AUC {test['roc_auc']:.3f}, "
            f"calibration error {test['calibration']['ece']:.3f}. Validation, for comparison: recall "
            f"{chosen['recall']:.2f}, precision {chosen['precision']:.2f}, cost "
            f"{chosen['cost_per_100']:.1f} per 100.",
        ]
    return "\n".join([
        "# Model card · Responsible service triage",
        "",
        "## Model details",
        "",
        f"- **What:** {r['model']['name']} (`{r['model']['id']}`, {r['model']['params']}) in a "
        "scikit-learn pipeline: TF-IDF (1–2-grams) on the ticket text, one-hot category and channel, "
        "scaled length, attachments and time of day.",
        f"- **Output:** an urgency score from 0 to 1 and an **urgent review** flag at score ≥ "
        f"{r['threshold']:.2f}.",
        f"- **Trained on:** Sep 2025 – Apr 2026 tickets ({r['windows']['train']['rows']:,}). "
        "Settings frozen before the test.",
        "- **Owner:** the project team. Course: Basics of Artificial Intelligence, Project 2.",
        "",
        "## Intended use",
        "",
        "- Re-order the support desk's queue: tickets with the flag are **read first** by a person.",
        "- Help staff notice urgent tickets that would otherwise wait their turn.",
        "",
        "## Prohibited use",
        "",
        "- **Refusing, closing, delaying or down-prioritising any ticket** because it was *not* flagged.",
        "- Any automatic action without a person deciding.",
        "- Judging, ranking or monitoring requesters or staff.",
        "- Use on other desks, languages or ticket forms without a new evaluation.",
        "- Treating the score as an exact probability or as the panel's final judgement.",
        "",
        "## Data",
        "",
        "Instructor's synthetic export (`data/tickets.csv`): 3,000 tickets after cleaning, "
        "Sep 2025 – Aug 2026, no real people. Permitted for this coursework and portfolio use. "
        "Labels come from a review panel and are approved but imperfect: identical texts sometimes "
        "carry different labels (see `reports/error_analysis.md`). Audit: `reports/audit.md`.",
        "",
        "Inputs are only what exists at submission: category, channel, description, length, "
        "attachments and time. `assigned_priority`, `handling_team` and `resolution_hours` are set "
        "later and are excluded. `requester_id` and `requester_type` are not inputs.",
        "",
        "## Performance on validation (May – Jun 2026)",
        "",
        table(ladder(r), LADDER_COLUMNS),
        "",
        f"Average precision {chosen['average_precision']:.3f}, ROC AUC {chosen['roc_auc']:.3f}, "
        f"calibration error {chosen['calibration']['ece']:.3f}.",
        "",
        "## Performance on the held-out test (Jul – Aug 2026)",
        "",
        *test_section,
        "",
        "## Known limitations",
        "",
        f"- **New channels.** On validation, mobile_app tickets (first seen in May) had recall "
        f"{shifts['observed_mobile_app']['recall']:.2f}, against {chosen['recall']:.2f} overall, on a "
        "small sample. If every ticket came through an unseen channel, cost would rise from "
        f"{shifts['baseline']['cost_per_100']:.1f} to {shifts['new_channel']['cost_per_100']:.1f} per 100.",
        f"- **Gaming.** If a quarter of non-urgent requesters copied an impact phrase, precision would "
        f"fall from {shifts['baseline']['precision']:.2f} to {shifts['gaming']['precision']:.2f}. The "
        "flag rewards describing impact, so monitor how often flagged tickets are confirmed.",
        f"- **Shouting and length.** Adding \"URGENT!!!\" to every ticket moves the flag rate from "
        f"{pct(shifts['baseline']['flag_rate'])} to {pct(shifts['everyone_shouts']['flag_rate'])}"
        + (": the model has learned that shouting is rarely urgent. "
           if shifts["everyone_shouts"]["flag_rate"] <= shifts["baseline"]["flag_rate"] else ". ")
        + f"A neutral \"Thank you.\" of the same length moves it to "
        f"{pct(shifts['longer_text']['flag_rate'])}"
        + (": longer texts score higher, and requesters can make their texts longer."
           if shifts["longer_text"]["flag_rate"] > shifts["baseline"]["flag_rate"] else "."),
        ("- **Uneven channels.** Recall is clearly lower on "
         + ", ".join(f"`{c}`" for c in weak)
         + " tickets than overall (validation subgroups table)."
         + (" Walk-in texts are short summaries typed by staff." if "walk_in" in weak else "")) if weak else
        "- **Channels.** No channel with enough data has clearly lower recall than overall.",
        f"- **Workload.** About {pct(chosen['flag_rate'])} of tickets are flagged. If the desk cannot "
        "read that many first, raise the threshold and accept more misses: see the decision note.",
        "- **Label noise.** Some urgent tickets contain no visible sign of urgency. No model trained on "
        "these fields can catch them; staff judgement remains essential.",
        "",
        "## Human oversight",
        "",
        "The flag is advisory. Staff see the score and the sentences that raised it, confirm or dismiss "
        "it, and keep full control of the queue. Review the confirmation rate monthly and re-evaluate "
        "after any change to the form, the channels or the desk's workload.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "python -m pip install -r requirements.txt",
        "python -m triage run    # retrains the frozen model deterministically",
        "python -m pytest",
        "```",
        "",
    ])


def write_reports(paths: Paths) -> None:
    r, test = _load(paths)
    out = paths.reports
    write_text(out / "experiments.md", experiments_md(r))
    write_text(out / "experiments.csv", experiments_csv(r))
    write_text(out / "validation_report.md", validation_md(r))
    write_text(out / "error_analysis.md", errors_md(r))
    write_text(out / "decision_note.md", decision_md(r))
    write_text(out / "model_card.md", model_card_md(r, test))
