# Responsible Service Triage

An **advisory "urgent review" flag** for a support desk: Basics of Artificial Intelligence, Project 2 of 4 (labs L5–L8).

When a ticket arrives, the model suggests whether staff should look at it first. **It never refuses, closes or delays a request. A person always decides.** The goal is not the highest score. It is an honest evaluation that a real client could trust.

## Quick start

```bash
python -m pip install -r requirements.txt

python -m triage audit       # L5 · columns, cleaning, leakage, requesters, drift -> reports/audit.md
python -m triage split       # L5 · freeze the time-based split -> data/split_manifest.json
python -m triage baselines   # L5 · two baselines on validation -> reports/baselines.md

python -m pytest             # acceptance checks
```

## The data

`data/tickets.csv` is the instructor's synthetic export (3,012 rows, September 2025 – August 2026), described in [`data/DATA_DICTIONARY.md`](data/DATA_DICTIONARY.md). It is fully synthetic and permitted for coursework and portfolio use. No real tickets are involved.

The export was deliberately left uncleaned. Every cleaning rule works row by row and never uses the label, so it is safe to apply before the split:

| Problem found | Fix |
|---|---|
| 12 duplicated rows | dropped |
| 38 inconsistent category spellings (`ACCOUNT_ACCESS`, ` software`, `data request`) | normalised to 8 categories |
| 60 missing channels | 12 recovered from the staff prefix (`Caller reports:` = phone, `Walk-in:` = walk-in), 48 set to `unknown` |
| 30 missing `description_length` | recomputed from the text, which matches on every other row |

## Non-negotiables and how the code enforces them

| Rule | Enforcement |
|---|---|
| **Submission-time information only** | A whitelist column policy (`triage/data.py`). `assigned_priority`, `handling_team` and `resolution_hours` are set after triage and are excluded. On their own they reach AUC 0.93 / 0.73 / 0.94, which is too good to be true. Undocumented columns are excluded by default. |
| **Test set used once** | The split is frozen in `data/split_manifest.json` with SHA-256 fingerprints. Test IDs are stored only as a hash, and no development function can return test rows. |
| **Approved data only** | Only the instructor's file. Its fingerprint is checked before every run. |
| **Advisory only** | The output is a suggestion to re-order the queue, never an action. |

## Split

| Window | Months | Tickets |
|---|---|---|
| Train | Sep 2025 – Apr 2026 | 1,784 |
| Validation | May – Jun 2026 | 660 |
| Test (sealed) | Jul – Aug 2026 | 556 |

The model will score **future** tickets, so the split follows time. 95% of later tickets come from requesters already seen in training, and removing them would delete 88% of the training data. Their urgency rate varies no more than chance predicts, so requesters carry no urgency of their own. Inside training, cross-validation folds are **grouped by requester**. The full argument is in [`reports/audit.md`](reports/audit.md).

## Project layout

```
data/        instructor's CSV, data dictionary, frozen split manifest
triage/      the Python package (python -m triage ...)
reports/     generated, human-readable deliverables
tests/       acceptance checks (pytest)
docs/        Romanian explanation of the project brief
```
