"""L7 analyses on the validation window: errors, shifts, subgroups, queue effect, leakage demo."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import SEED
from .data import TARGET
from .evaluate import evaluate_flags, score_metrics
from .explain import explain, split_sentences
from .features import make_X
from .models import cross_validate, preprocessor

# Subgroup numbers are only reported when there is enough data to mean something.
MIN_SLICE_TICKETS = 30
MIN_SLICE_URGENT = 5


def predict(model, df: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(make_X(df))[:, 1]


# --------------------------------------------------------------------------- errors
def sentence_rates(train: pd.DataFrame) -> dict[str, tuple[int, float]]:
    """How often each sentence appears in training, and how often those tickets are urgent."""
    rows = [(s.lower(), y) for text, y in zip(train["description"], train[TARGET])
            for s in set(split_sentences(text))]
    frame = pd.DataFrame(rows, columns=["sentence", "y"])
    g = frame.groupby("sentence")["y"].agg(["size", "mean"])
    return {s: (int(r["size"]), float(r["mean"])) for s, r in g.iterrows()}


def _hypothesis(kind: str, ticket: pd.Series, exp: dict, rates: dict, train_texts: dict) -> str:
    top = max(exp["sentences"], key=lambda s: s["effect"], default=None)
    parts = []
    if kind == "missed":
        if top is None or top["effect"] < 0.03:
            parts.append("Nothing in the text signals impact or a deadline that the model has learned to "
                         "recognise. The panel probably judged context that the ticket does not contain.")
        else:
            n, rate = rates.get(top["text"].lower(), (0, None))
            seen = f" (urgent in {rate:.0%} of {n} training tickets)" if rate is not None and n >= 5 else ""
            parts.append(f"The strongest cue, \"{top['text']}\"{seen}, added only "
                         f"{top['effect']:+.2f}: not enough to cross the threshold.")
        channel = next(f for f in exp["fields"] if f["field"] == "initial_channel")
        if channel["effect"] < -0.02:
            parts.append(f"Arriving by {channel['value']} lowered the score ({channel['effect']:+.2f}).")
    else:
        if top is not None:
            n, rate = rates.get(top["text"].lower(), (0, None))
            seen = (f" Tickets with this sentence are urgent in {rate:.0%} of {n} training cases, "
                    "so some false alarms on it are expected.") if rate is not None and n >= 5 else ""
            parts.append(f"Flagged mainly because of \"{top['text']}\" ({top['effect']:+.2f}).{seen}")
    if train_texts.get(ticket["description"].strip().lower()) == 1 - int(ticket[TARGET]):
        parts.append("An identical text carries the opposite label in training: possible label inconsistency.")
    return " ".join(parts)


def inspect_errors(model, train: pd.DataFrame, val: pd.DataFrame, scores: np.ndarray,
                   threshold: float, per_kind: int = 6) -> list[dict]:
    """The most confident mistakes of each kind, with a first hypothesis for the team to check."""
    rates = sentence_rates(train)
    train_texts = (train.assign(t=train["description"].str.strip().str.lower())
                   .groupby("t")[TARGET].agg(lambda s: int(s.mode().iloc[0])).to_dict())
    frame = val.assign(score=scores)
    missed = frame[(frame[TARGET] == 1) & (frame["score"] < threshold)].nsmallest(per_kind, "score")
    false_alarms = frame[(frame[TARGET] == 0) & (frame["score"] >= threshold)].nlargest(per_kind, "score")
    out = []
    for kind, rows in (("missed", missed), ("false_alarm", false_alarms)):
        for _, t in rows.iterrows():
            exp = explain(model, t.to_dict())
            out.append({
                "kind": kind,
                "ticket_id": t["ticket_id"],
                "submitted_at": t["submitted_at"].isoformat(sep=" "),
                "category": t["category"],
                "initial_channel": t["initial_channel"],
                "description": t["description"],
                "score": float(t["score"]),
                "label": int(t[TARGET]),
                "sentences": exp["sentences"],
                "fields": exp["fields"],
                "hypothesis": _hypothesis(kind, t, exp, rates, train_texts),
            })
    return out


# --------------------------------------------------------------------------- tone
# How a request is phrased, matched case-insensitively in the ticket text.
TONE_PHRASES = (
    ("calm request", "Please treat as urgent.", r"please treat as urgent\."),
    ("calm request", "This is urgent.", r"\bthis is urgent\."),
    ("calm request", "ASAP please.", r"\basap please\."),
    ("shouting", "URGENT!!!", r"\burgent!!!"),
    ("shouting", "URGENT!!", r"\burgent!!(?!!)"),
    ("shouting", "ASAP!!!", r"\basap!!!"),
    ("shouting", "Very urgent.", r"\bvery urgent\."),
    ("shouting", "Top priority please!", r"top priority please!"),
    ("negation", "This is not urgent, whenever you have time.", r"this is not urgent, whenever"),
    ("negation", "Nothing urgent, just letting you know.", r"\bnothing urgent\b"),
    ("negation", "Low priority.", r"\blow priority\."),
)


def tone_table(train: pd.DataFrame) -> list[dict]:
    """Urgent rate of training tickets containing each phrasing of "urgent"."""
    rows = []
    for style, phrase, pattern in TONE_PHRASES:
        mask = train["description"].str.contains(pattern, case=False, regex=True)
        rows.append({"style": style, "phrase": phrase, "tickets": int(mask.sum()),
                     "urgent_rate": float(train.loc[mask, TARGET].mean()) if mask.any() else None})
    return rows


# --------------------------------------------------------------------------- shifts
def _with_text(df: pd.DataFrame, text: pd.Series) -> pd.DataFrame:
    return df.assign(description=text, description_length=text.str.len())


def shift_scenarios(model, val: pd.DataFrame, threshold: float) -> list[dict]:
    rng = np.random.default_rng(SEED)
    gaming = rng.random(len(val)) < 0.25
    phrase = " My whole team has the same problem."
    gamed = val["description"].where(~(gaming & (val[TARGET] == 0).to_numpy()), val["description"] + phrase)

    simulated = [
        ("baseline", "Validation as observed", "Reference point.", val),
        ("new_channel", "Every ticket arrives through an unseen channel",
         "Like mobile_app, which first appeared in May. The model must fall back on the text.",
         val.assign(initial_channel="mobile_app")),
        ("everyone_shouts", "Every requester adds \"URGENT!!!\"",
         "Shouting is rarely urgent in training. A robust model should barely move.",
         _with_text(val, val["description"] + " URGENT!!!")),
        ("longer_text", "Every requester adds a neutral \"Thank you.\"",
         "Control for the row above: the same extra length, no urgency word.",
         _with_text(val, val["description"] + " Thank you.")),
        ("gaming", "A quarter of non-urgent requesters copy an impact phrase",
         f"They append \"{phrase.strip()}\" to get faster service. Labels stay non-urgent.",
         _with_text(val, gamed)),
    ]
    rows = []
    for key, name, note, frame in simulated:
        p = predict(model, frame)
        rows.append({"id": key, "name": name, "note": note, "kind": "simulated" if key != "baseline" else "observed",
                     **evaluate_flags(frame[TARGET], p >= threshold)})

    month = val["submitted_at"].dt.strftime("%Y-%m")
    p_val = predict(model, val)
    for m in sorted(month.unique()):
        mask = (month == m).to_numpy()
        days = val.loc[mask, "submitted_at"].dt.normalize().nunique()
        rows.append({"id": f"month_{m}", "name": f"Observed: {m}",
                     "note": f"{mask.sum()} tickets over {days} days.",
                     "kind": "observed", **evaluate_flags(val.loc[mask, TARGET], p_val[mask] >= threshold)})
    mobile = (val["initial_channel"] == "mobile_app").to_numpy()
    if mobile.any():
        rows.append({"id": "observed_mobile_app", "name": "Observed: mobile_app tickets only",
                     "note": "The real unseen channel. Small sample, so read with care.",
                     "kind": "observed", **evaluate_flags(val.loc[mobile, TARGET], p_val[mobile] >= threshold)})
    return rows


# --------------------------------------------------------------------------- subgroups
def slices(df: pd.DataFrame, scores: np.ndarray, threshold: float,
           columns=("requester_type", "initial_channel", "category")) -> list[dict]:
    rows = []
    frame = df.assign(_score=scores, month=df["submitted_at"].dt.strftime("%Y-%m"))
    for col in (*columns, "month"):
        for value, g in frame.groupby(col):
            enough = len(g) >= MIN_SLICE_TICKETS and g[TARGET].sum() >= MIN_SLICE_URGENT
            m = evaluate_flags(g[TARGET], g["_score"] >= threshold)
            rows.append({"slice": col, "value": value, "tickets": int(len(g)),
                         "urgent": int(g[TARGET].sum()), "enough_data": bool(enough),
                         "recall": m["recall"] if enough else None,
                         "precision": m["precision"] if enough else None,
                         "flag_rate": m["flag_rate"]})
    return rows


# --------------------------------------------------------------------------- queue effect
def queue_effect(df: pd.DataFrame, flags: np.ndarray) -> dict:
    """How many tickets are ahead of an urgent ticket in its day's queue: FIFO vs flagged first."""
    frame = df[["submitted_at", TARGET]].assign(flag=np.asarray(flags).astype(bool),
                                                day=df["submitted_at"].dt.normalize())
    fifo, flagged, sizes = [], [], []
    for _, day in frame.groupby("day"):
        day = day.sort_values("submitted_at")
        order_fifo = np.arange(len(day))
        priority = day.assign(pos=order_fifo).sort_values(["flag", "pos"], ascending=[False, True])
        rank_flagged = pd.Series(np.arange(len(day)), index=priority.index).reindex(day.index).to_numpy()
        urgent = day[TARGET].to_numpy() == 1
        fifo += list(order_fifo[urgent])
        flagged += list(rank_flagged[urgent])
        sizes.append(len(day))
    fifo, flagged = np.array(fifo, dtype=float), np.array(flagged, dtype=float)
    return {
        "days": len(sizes),
        "tickets_per_day": float(np.mean(sizes)),
        "flags_per_day": float(frame.groupby("day")["flag"].sum().mean()),
        "urgent_ahead_fifo": float(fifo.mean()) if len(fifo) else 0.0,
        "urgent_ahead_flagged": float(flagged.mean()) if len(flagged) else 0.0,
        "urgent_first_in_line_fifo": float((fifo == 0).mean()) if len(fifo) else 0.0,
        "urgent_in_top3_flagged": float((flagged < 3).mean()) if len(flagged) else 0.0,
        "urgent_in_top3_fifo": float((fifo < 3).mean()) if len(fifo) else 0.0,
    }


# --------------------------------------------------------------------------- leakage demo
LEAKY = ["assigned_priority", "handling_team", "resolution_hours"]


def leakage_demo(train: pd.DataFrame, val: pd.DataFrame, folds) -> dict:
    """What the excluded columns would do. Shown for teaching, never saved or used."""
    def frame(df):
        # Deliberately bypasses the policy check in make_X to add post-submission columns.
        return pd.concat([make_X(df), df[LEAKY]], axis=1)

    def build():
        base = preprocessor(use_text=True)
        prep = ColumnTransformer(base.transformers + [
            ("leak_cat", OneHotEncoder(handle_unknown="ignore"), ["assigned_priority", "handling_team"]),
            ("leak_num", Pipeline([("impute", SimpleImputer(strategy="median")),
                                   ("scale", StandardScaler())]), ["resolution_hours"]),
        ], sparse_threshold=0.3)
        return Pipeline([("prep", prep), ("model", LogisticRegression(C=1.0, max_iter=5000))])

    X_train, X_val = frame(train), frame(val)
    cv = cross_validate(build, X_train, train[TARGET], folds)
    model = build().fit(X_train, train[TARGET])
    val_scores = score_metrics(val[TARGET], model.predict_proba(X_val)[:, 1])
    return {"id": "LEAKY_priority_team_resolution", "name": "Leakage demo · NOT ALLOWED",
            "family": "logreg", "params": "C=1.0 + assigned_priority, handling_team, resolution_hours",
            "allowed": False,
            "note": "Uses columns that only exist after triage. Too good to be true; never deployed.",
            **cv, "val_average_precision": val_scores["average_precision"],
            "val_roc_auc": val_scores["roc_auc"]}
