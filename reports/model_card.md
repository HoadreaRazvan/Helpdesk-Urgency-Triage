# Model card · Responsible service triage

## Model details

- **What:** Model A · Logistic regression (`logreg_C10_tone`, C=10.0, + tone features) in a scikit-learn pipeline: TF-IDF (1–2-grams) on the ticket text, one-hot category and channel, scaled length, attachments and time of day.
- **Output:** an urgency score from 0 to 1 and an **urgent review** flag at score ≥ 0.10.
- **Trained on:** Sep 2025 – Apr 2026 tickets (1,784). Settings frozen before the test.
- **Owner:** the project team. Course: Basics of Artificial Intelligence, Project 2.

## Intended use

- Re-order the support desk's queue: tickets with the flag are **read first** by a person.
- Help staff notice urgent tickets that would otherwise wait their turn.

## Prohibited use

- **Refusing, closing, delaying or down-prioritising any ticket** because it was *not* flagged.
- Any automatic action without a person deciding.
- Judging, ranking or monitoring requesters or staff.
- Use on other desks, languages or ticket forms without a new evaluation.
- Treating the score as an exact probability or as the panel's final judgement.

## Data

Instructor's synthetic export (`data/tickets.csv`): 3,000 tickets after cleaning, Sep 2025 – Aug 2026, no real people. Permitted for this coursework and portfolio use. Labels come from a review panel and are approved but imperfect: identical texts sometimes carry different labels (see `reports/error_analysis.md`). Audit: `reports/audit.md`.

Inputs are only what exists at submission: category, channel, description, length, attachments and time. `assigned_priority`, `handling_team` and `resolution_hours` are set later and are excluded. `requester_id` and `requester_type` are not inputs.

## Performance on validation (May – Jun 2026)

| Model | Recall | Precision | F1 | Accuracy | Flagged | TP | FN | FP | TN | Cost / 100 |
|---|---|---|---|---|---|---|---|---|---|---|
| Baseline 1 · Majority class | 0.000 | 0.000 | 0.000 | 0.805 | 0.000 | 0 | 129 | 0 | 531 | 97.727 |
| Baseline 2 · Keyword rule (impact + time pressure) | 0.504 | 0.351 | 0.414 | 0.721 | 0.280 | 65 | 64 | 120 | 411 | 66.667 |
| Model A · Logistic regression (logreg_C10_tone, t=0.10) ✔ selected | 0.705 | 0.318 | 0.439 | 0.647 | 0.433 | 91 | 38 | 195 | 336 | 58.333 |
| Model B · Random forest (forest_leaf2, t=0.07) | 0.822 | 0.256 | 0.390 | 0.498 | 0.627 | 106 | 23 | 308 | 223 | 64.091 |
| Naive rule · 'urgent' / 'ASAP' words | 0.264 | 0.327 | 0.292 | 0.750 | 0.158 | 34 | 95 | 70 | 461 | 82.576 |

Average precision 0.512, ROC AUC 0.727, calibration error 0.068.

## Performance on the held-out test (Jul – Aug 2026)

**Not run yet.** The test window (Jul – Aug 2026, 556 tickets) is sealed. It is opened once, in L8, with `python -m triage test --confirm "I understand the test set is used once"` or the vault in the web app. This card is regenerated with the results.

## Known limitations

- **New channels.** On validation, mobile_app tickets (first seen in May) had recall 0.43, against 0.71 overall, on a small sample. If every ticket came through an unseen channel, cost would rise from 58.3 to 62.1 per 100.
- **Gaming.** If a quarter of non-urgent requesters copied an impact phrase, precision would fall from 0.32 to 0.26. The flag rewards describing impact, so monitor how often flagged tickets are confirmed.
- **Shouting and length.** Adding "URGENT!!!" to every ticket moves the flag rate from 43.3% to 37.3%: the model has learned that shouting is rarely urgent. A neutral "Thank you." of the same length moves it to 52.7%: longer texts score higher, and requesters can make their texts longer.
- **Uneven channels.** Recall is clearly lower on `email`, `mobile_app`, `walk_in` tickets than overall (validation subgroups table). Walk-in texts are short summaries typed by staff.
- **Workload.** About 43.3% of tickets are flagged. If the desk cannot read that many first, raise the threshold and accept more misses: see the decision note.
- **Label noise.** Some urgent tickets contain no visible sign of urgency. No model trained on these fields can catch them; staff judgement remains essential.

## Human oversight

The flag is advisory. Staff see the score and the sentences that raised it, confirm or dismiss it, and keep full control of the queue. Review the confirmation rate monthly and re-evaluate after any change to the form, the channels or the desk's workload.

## Reproduce

```bash
python -m pip install -r requirements.txt
python -m triage run    # retrains the frozen model deterministically
python -m pytest
```
