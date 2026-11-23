"""Command line: ``python -m triage <command>``. Run the commands in lab order."""
from __future__ import annotations

import argparse
import sys

from .config import Paths

METRIC_COLUMNS = [("name", "Model"), ("recall", "Recall"), ("precision", "Precision"),
                  ("f1", "F1"), ("accuracy", "Accuracy"), ("flag_rate", "Flagged"),
                  ("tp", "TP"), ("fn", "FN"), ("fp", "FP"), ("tn", "TN"),
                  ("cost_per_100", "Cost / 100 tickets")]


def cmd_audit(paths: Paths, args) -> None:
    from .audit import write_audit

    a = write_audit(paths)
    print(f"Audited {a['rows_raw']} raw rows -> {a['rows_clean']} clean tickets.")
    print("Features allowed at submission time:", ", ".join(a["features"]))
    for row in a["leak_scan"]:
        auc = f"{row['auc']:.3f}" if row["auc"] is not None else "n/a"
        print(f"  {row['column']:<20} AUC alone {auc}  -> {row['verdict']}")
    print(f"Report: {paths.reports / 'audit.md'}")


def cmd_split(paths: Paths, args) -> None:
    from .split import freeze_split

    existed = paths.split_manifest.exists()
    m = freeze_split(paths, force=args.force)
    state = "Existing frozen split" if existed and not args.force else "Froze split"
    print(f"{state}: {paths.split_manifest}")
    for w, s in m["windows"].items():
        extra = f", {s['urgent']} urgent" if "urgent" in s else ", labels sealed"
        print(f"  {w:<5} {s['rows']:>5} tickets  {s['first'][:10]} .. {s['last'][:10]}{extra}")


def cmd_baselines(paths: Paths, args) -> None:
    from .baselines import evaluate_baselines
    from .markdown import table, write_text
    from .split import load_development

    rows = evaluate_baselines(load_development(paths))
    text = "\n".join([
        "# Baselines on the validation window",
        "",
        "Fitted on train (Sep 2025 – Apr 2026), evaluated on validation (May – Jun 2026).",
        "",
        table(rows, METRIC_COLUMNS),
        "",
    ])
    paths.reports.mkdir(parents=True, exist_ok=True)
    write_text(paths.reports / "baselines.md", text)
    print(text)


def cmd_run(paths: Paths, args) -> None:
    from .pipeline import run_development
    from .split import freeze_split

    freeze_split(paths)  # no-op when the split is already frozen
    r = run_development(paths)
    v = r["validation"]
    print(f"\nFrozen: {r['model']['id']} at threshold {r['threshold']:.2f} -> {paths.frozen_config}")
    print(f"Validation: recall {v['recall']:.2f}, precision {v['precision']:.2f}, "
          f"{v['flag_rate']:.0%} flagged, cost {v['cost_per_100']:.1f} per 100 tickets")
    print(f"Reports: {paths.reports}")


def cmd_test(paths: Paths, args) -> None:
    from .config import TEST_CONFIRMATION
    from .final import run_final_test, sealed_test_status

    status = sealed_test_status(paths)
    if status["used"]:
        print(f"The test set was already used on {status['lock']['opened_at']}.")
        if status["results"]:
            t = status["results"]
            print(f"Test: recall {t['recall']:.2f}, precision {t['precision']:.2f}, "
                  f"cost {t['cost_per_100']:.1f} per 100 tickets")
        return
    if args.confirm is None:
        print("The test set is sealed and can be opened only once, with frozen settings.")
        print(f'To open it: python -m triage test --confirm "{TEST_CONFIRMATION}"')
        return
    t = run_final_test(paths, args.confirm)
    print(f"Test ({t['tickets']} tickets): recall {t['recall']:.2f}, precision {t['precision']:.2f}, "
          f"F1 {t['f1']:.2f}, cost {t['cost_per_100']:.1f} per 100 tickets")
    print(f"TP {t['tp']}  FN {t['fn']}  FP {t['fp']}  TN {t['tn']}")
    print(f"Results: {paths.test_results}  ·  model card updated")


COMMANDS = {
    "audit": (cmd_audit, "L5: audit columns, cleaning, leakage, requesters and drift"),
    "split": (cmd_split, "L5: freeze the time-based train / validation / test split"),
    "baselines": (cmd_baselines, "L5: evaluate the two baselines on validation"),
    "run": (cmd_run, "L6-L7: experiments, threshold, calibration, errors, shifts; freeze settings"),
    "test": (cmd_test, "L8: open the sealed test set once (needs --confirm)"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m triage", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in COMMANDS.items():
        p = sub.add_parser(name, help=help_text)
        if name == "split":
            p.add_argument("--force", action="store_true",
                           help="re-freeze the split (refused once the test set was used)")
        if name == "test":
            p.add_argument("--confirm", metavar="SENTENCE",
                           help="the exact confirmation sentence, to prove this is deliberate")
    args = parser.parse_args(argv)
    try:
        COMMANDS[args.command][0](Paths(), args)
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0
