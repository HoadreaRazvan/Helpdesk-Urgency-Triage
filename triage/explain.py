"""Why did the model score this ticket the way it did?

Model-agnostic "occlusion": take one piece of evidence away (a sentence of
the description, the category, the channel, ...), score the ticket again and
measure how much the urgency score moves. It works for any model in the
ladder and the answer is easy to read: "this sentence added +0.21".
"""
from __future__ import annotations

import re

import pandas as pd

from .features import make_X

SENTENCE = re.compile(r"(?<=[.!?])\s+")
NEUTRAL = "__none__"  # unseen value: one-hot encodes as "no information"
REFERENCE_TIME = pd.Timestamp("2026-03-03 10:00:00")  # a Tuesday, mid-morning

TICKET_FIELDS = ("category", "initial_channel", "description", "attachments_count", "submitted_at")


def split_sentences(text: str) -> list[str]:
    return [s for s in (p.strip() for p in SENTENCE.split(text.strip())) if s]


def ticket_frame(tickets: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(tickets, columns=list(TICKET_FIELDS))
    df["submitted_at"] = pd.to_datetime(df["submitted_at"])
    df["description_length"] = df["description"].str.len()
    return df


def score(model, tickets: list[dict]):
    return model.predict_proba(make_X(ticket_frame(tickets)))[:, 1]


def explain(model, ticket: dict) -> dict:
    base = {k: ticket[k] for k in TICKET_FIELDS}
    sentences = split_sentences(base["description"])
    variants = [base]
    for i in range(len(sentences)):
        variants.append({**base, "description": " ".join(sentences[:i] + sentences[i + 1:])})
    field_variants = [
        ("category", base["category"], {**base, "category": NEUTRAL}),
        ("initial_channel", base["initial_channel"], {**base, "initial_channel": NEUTRAL}),
        ("submitted_at", str(pd.Timestamp(base["submitted_at"]))[:16],
         {**base, "submitted_at": REFERENCE_TIME}),
    ]
    if int(base["attachments_count"]) > 0:
        field_variants.append(("attachments_count", int(base["attachments_count"]),
                               {**base, "attachments_count": 0}))
    variants += [v for _, _, v in field_variants]

    p = score(model, variants)
    s0 = float(p[0])
    n = len(sentences)
    return {
        "score": s0,
        "sentences": [{"text": s, "effect": s0 - float(p[1 + i])} for i, s in enumerate(sentences)],
        "fields": [{"field": f, "value": v, "effect": s0 - float(p[1 + n + j])}
                   for j, (f, v, _) in enumerate(field_variants)],
    }
