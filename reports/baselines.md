# Baselines on the validation window

Fitted on train (Sep 2025 – Apr 2026), evaluated on validation (May – Jun 2026).

| Model | Recall | Precision | F1 | Accuracy | Flagged | TP | FN | FP | TN | Cost / 100 tickets |
|---|---|---|---|---|---|---|---|---|---|---|
| Baseline 1 · Majority class | 0.000 | 0.000 | 0.000 | 0.805 | 0.000 | 0 | 129 | 0 | 531 | 97.727 |
| Baseline 2 · Keyword rule (impact + time pressure) | 0.504 | 0.351 | 0.414 | 0.721 | 0.280 | 65 | 64 | 120 | 411 | 66.667 |
| Naive rule · 'urgent' / 'ASAP' words | 0.264 | 0.327 | 0.292 | 0.750 | 0.158 | 34 | 95 | 70 | 461 | 82.576 |
