"""The model ladder (slide 5): Model A, logistic regression; Model B, tree ensembles.

Preprocessing lives *inside* each scikit-learn Pipeline, so during
cross-validation the TF-IDF vocabulary, the one-hot categories and the
scaler are learned from the four training folds only, never from the
fold being scored.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import COST_FN, COST_FP, CV_FOLDS, SEED
from .evaluate import evaluate_flags, score_metrics
from .features import CATEGORICAL, FLAGS, NUMERIC, TEXT, TONE

FAMILY_NAMES = {
    "logreg": "Model A · Logistic regression",
    "forest": "Model B · Random forest",
    "boosting": "Model B · Gradient boosting",
}
# A model with calibrated probabilities minimises expected cost at this threshold.
# CV uses it so that every fold is scored at the same, cost-derived cut-off.
BAYES_THRESHOLD = COST_FP / (COST_FP + COST_FN)


@dataclass(frozen=True)
class Experiment:
    id: str
    family: str
    params: dict = field(default_factory=dict)
    use_text: bool = True
    use_tone: bool = False
    note: str = ""

    @property
    def name(self) -> str:
        return FAMILY_NAMES[self.family]

    @property
    def is_tree(self) -> bool:
        return self.family in ("forest", "boosting")

    def describe(self) -> str:
        parts = [f"{k}={v}" for k, v in self.params.items()]
        if not self.use_text:
            parts.append("no text")
        if self.use_tone:
            parts.append("+ tone features")
        return ", ".join(parts)


EXPERIMENTS: tuple[Experiment, ...] = (
    Experiment("logreg_C0.3", "logreg", {"C": 0.3}),
    Experiment("logreg_C1", "logreg", {"C": 1.0}),
    Experiment("logreg_C3", "logreg", {"C": 3.0}),
    Experiment("logreg_C10", "logreg", {"C": 10.0}),
    Experiment("logreg_C10_tone", "logreg", {"C": 10.0}, use_tone=True,
               note="Adds exclamation marks and capital-letter share: does shouting carry signal?"),
    Experiment("logreg_C1_balanced", "logreg", {"C": 1.0, "class_weight": "balanced"},
               note="Re-weights the classes: scores stop reading as probabilities."),
    Experiment("logreg_C1_no_text", "logreg", {"C": 1.0}, use_text=False,
               note="Ablation: form fields only, no ticket text."),
    Experiment("forest_leaf2", "forest",
               {"n_estimators": 400, "min_samples_leaf": 2, "max_features": "sqrt"}),
    Experiment("forest_leaf8", "forest",
               {"n_estimators": 400, "min_samples_leaf": 8, "max_features": "sqrt"}),
    Experiment("boosting_lr0.05", "boosting",
               {"learning_rate": 0.05, "max_iter": 300, "max_leaf_nodes": 15,
                "l2_regularization": 1.0}),
    Experiment("boosting_lr0.1_depth3", "boosting",
               {"learning_rate": 0.1, "max_iter": 200, "max_depth": 3}),
)


def experiment(exp_id: str) -> Experiment:
    return next(e for e in EXPERIMENTS if e.id == exp_id)


def preprocessor(use_text: bool = True, dense: bool = False, use_tone: bool = False) -> ColumnTransformer:
    transformers = [
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ("num", StandardScaler(), NUMERIC + (TONE if use_tone else [])),
        ("flags", "passthrough", FLAGS),
    ]
    if use_text:
        tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True,
                                max_features=400 if dense else None)
        transformers.insert(0, ("text", tfidf, TEXT))
    return ColumnTransformer(transformers, sparse_threshold=0.0 if dense else 0.3)


def build(exp: Experiment) -> Pipeline:
    if exp.family == "logreg":
        model = LogisticRegression(max_iter=5000, **exp.params)
    elif exp.family == "forest":
        model = RandomForestClassifier(random_state=SEED, n_jobs=-1, **exp.params)
    elif exp.family == "boosting":
        model = HistGradientBoostingClassifier(random_state=SEED, **exp.params)
    else:
        raise ValueError(exp.family)
    # Gradient boosting needs a dense matrix, so its vocabulary is capped.
    return Pipeline([("prep", preprocessor(exp.use_text, dense=exp.family == "boosting",
                                           use_tone=exp.use_tone)),
                     ("model", model)])


def cv_folds(y: pd.Series, groups: pd.Series):
    """Stratified folds that never split one requester across training and scoring."""
    cv = StratifiedGroupKFold(n_splits=CV_FOLDS, shuffle=True, random_state=SEED)
    return list(cv.split(np.zeros(len(y)), y, groups))


def cross_validate(make_model, X: pd.DataFrame, y: pd.Series, folds) -> dict:
    per_fold = []
    for train_idx, score_idx in folds:
        model = make_model().fit(X.iloc[train_idx], y.iloc[train_idx])
        p = model.predict_proba(X.iloc[score_idx])[:, 1]
        y_fold = y.iloc[score_idx]
        flags = evaluate_flags(y_fold, p >= BAYES_THRESHOLD)
        per_fold.append({**score_metrics(y_fold, p), "cost_per_100": flags["cost_per_100"],
                         "recall": flags["recall"], "precision": flags["precision"]})
    frame = pd.DataFrame(per_fold)
    return {**{f"cv_{k}": float(v) for k, v in frame.mean().items()},
            **{f"cv_{k}_std": float(v) for k, v in frame.std(ddof=1).items()}}
