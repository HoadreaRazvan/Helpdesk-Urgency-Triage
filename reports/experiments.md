# L6 experiment table

Every row was trained on the training window only (1784 tickets), with 5-fold cross-validation **grouped by requester**. Preprocessing (TF-IDF, one-hot, scaling) sits inside the pipeline, so it is refitted on the four training folds of every round.

- **CV AP**: average precision, the area under the precision–recall curve. It is threshold-free and honest under class imbalance. Higher is better.
- **CV cost / 100**: cost per 100 tickets when each fold is cut at the cost-derived threshold 0.167 (FN = 5, FP = 1). Lower is better.
- **Brier**: mean squared error of the scores as probabilities. Lower is better.

| Experiment | Family | Settings | CV AP | CV AUC | Brier | CV cost / 100 | Note |
|---|---|---|---|---|---|---|---|
| `logreg_C0.3` | Model A · Logistic regression | C=0.3 | 0.457 ± 0.102 | 0.755 | 0.114 | 48.373 |  |
| `logreg_C1` | Model A · Logistic regression | C=1.0 | 0.486 ± 0.093 | 0.773 | 0.109 | 47.024 |  |
| `logreg_C3` | Model A · Logistic regression | C=3.0 | 0.501 ± 0.080 | 0.775 | 0.107 | 44.608 |  |
| `logreg_C10` | Model A · Logistic regression | C=10.0 | 0.507 ± 0.074 | 0.770 | 0.109 | 46.403 |  |
| `logreg_C10_tone` ✔ | Model A · Logistic regression | C=10.0, + tone features | 0.512 ± 0.075 | 0.769 | 0.108 | 46.066 | Adds exclamation marks and capital-letter share: does shouting carry signal? |
| `logreg_C1_balanced` | Model A · Logistic regression | C=1.0, class_weight=balanced | 0.473 ± 0.093 | 0.770 | 0.167 | 68.278 | Re-weights the classes: scores stop reading as probabilities. |
| `logreg_C1_no_text` | Model A · Logistic regression | C=1.0, no text | 0.364 ± 0.079 | 0.695 | 0.123 | 58.254 | Ablation: form fields only, no ticket text. |
| `forest_leaf2` (finalist) | Model B · Random forest | n_estimators=400, min_samples_leaf=2, max_features=sqrt | 0.457 ± 0.076 | 0.755 | 0.113 | 49.711 |  |
| `forest_leaf8` | Model B · Random forest | n_estimators=400, min_samples_leaf=8, max_features=sqrt | 0.429 ± 0.058 | 0.762 | 0.116 | 49.384 |  |
| `boosting_lr0.05` | Model B · Gradient boosting | learning_rate=0.05, max_iter=300, max_leaf_nodes=15, l2_regularization=1.0 | 0.404 ± 0.058 | 0.725 | 0.122 | 53.916 |  |
| `boosting_lr0.1_depth3` | Model B · Gradient boosting | learning_rate=0.1, max_iter=200, max_depth=3 | 0.432 ± 0.058 | 0.743 | 0.115 | 52.125 |  |
| `LEAKY_priority_team_resolution` ✘ excluded | Leakage demo · NOT ALLOWED | C=1.0 + assigned_priority, handling_team, resolution_hours | 0.941 ± 0.022 | 0.985 | 0.030 | 9.309 | Uses columns that only exist after triage. Too good to be true; never deployed. |

Selection rule (fixed before validation): Best CV average precision per family; the tree ensemble replaces logistic regression only if it lowers validation cost by more than 3%.

Machine-readable version: `reports/experiments.csv`.
