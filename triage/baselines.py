"""The two baselines every model has to beat, plus a deliberately naive rule.

* Majority class: always "not urgent". High accuracy, catches nothing.
* Keyword rule: a transparent, hand-written rule on the ticket text. It flags
  tickets that describe *impact* (people cannot work) or *time pressure*.
* Shouting rule: flags tickets that say "urgent" or "ASAP". It is not a
  required baseline. It shows that the word alone is a poor signal: it
  matches a calm "Please treat as urgent." (almost always urgent), a shouted
  "URGENT!!!" (rarely urgent) and a "not urgent" alike.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin

from .data import TARGET
from .evaluate import evaluate_flags

IMPACT_PHRASES = (
    "cannot work", "can't work", "unable to work", "completely blocked", "stops me from",
    "can't do anything", "nothing works", "whole team", "everyone in", "colleagues",
    "nobody can", "customers are calling",
)
DEADLINE_PHRASES = (
    "today", "tonight", "tomorrow", "in one hour", "end of day", "deadline", "go live",
)
SHOUT_PHRASES = ("urgent", "asap", "top priority")


def _pattern(phrases) -> re.Pattern:
    return re.compile(r"\b(" + "|".join(re.escape(p) for p in phrases) + r")\b", re.IGNORECASE)


class MajorityClass(ClassifierMixin, BaseEstimator):
    """Always predicts the most frequent training class."""

    def fit(self, X, y):
        y = np.asarray(y)
        self.classes_ = np.array([0, 1])
        self.prior_ = float(y.mean())
        self.majority_ = int(self.prior_ >= 0.5)
        return self

    def predict(self, X):
        return np.full(len(X), self.majority_)

    def predict_proba(self, X):
        p = np.full(len(X), self.prior_)
        return np.column_stack([1 - p, p])


class PhraseRule(ClassifierMixin, BaseEstimator):
    """Flags a ticket when its description contains any of the given phrases."""

    def __init__(self, phrases=()):
        self.phrases = phrases

    def fit(self, X, y=None):  # nothing to learn: the rule is written by hand
        self.classes_ = np.array([0, 1])
        self.pattern_ = _pattern(self.phrases)
        return self

    def matches(self, X: pd.DataFrame) -> pd.Series:
        return X["description"].map(lambda t: sorted({m.lower() for m in self.pattern_.findall(t)}))

    def predict(self, X):
        return X["description"].map(lambda t: bool(self.pattern_.search(t))).to_numpy().astype(int)

    def predict_proba(self, X):
        p = self.predict(X).astype(float)
        return np.column_stack([1 - p, p])


BASELINES = {
    "majority": ("Baseline 1 · Majority class", lambda: MajorityClass()),
    "keyword_rule": ("Baseline 2 · Keyword rule (impact + time pressure)",
                     lambda: PhraseRule(IMPACT_PHRASES + DEADLINE_PHRASES)),
    "shouting_rule": ("Naive rule · 'urgent' / 'ASAP' words", lambda: PhraseRule(SHOUT_PHRASES)),
}


def evaluate_baselines(dev: pd.DataFrame, on: str = "val") -> list[dict]:
    """Fit each baseline on train and evaluate its yes/no flags on ``on``."""
    train, target = dev[dev["split"] == "train"], dev[dev["split"] == on]
    rows = []
    for key, (name, make) in BASELINES.items():
        model = make().fit(train, train[TARGET])
        rows.append({"id": key, "name": name,
                     **evaluate_flags(target[TARGET], model.predict(target))})
    return rows
