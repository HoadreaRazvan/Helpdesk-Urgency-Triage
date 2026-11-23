# Decision note

## Decision

- **Model:** Model A · Logistic regression (`logreg_C10_tone`, C=10.0, + tone features), TF-IDF on the description plus category, channel, length, attachments and time of day.
- **Threshold:** 0.10. A ticket whose score is at or above it is flagged for urgent review.
- **Costs:** a missed urgent ticket counts 5, a false alarm counts 1.
- **Frozen** in `artifacts/frozen_config.json` before the test window is opened.

## What staff do with the flag

Flagged tickets are read first within the day's queue. The reader confirms the urgency and escalates, or dismisses the flag and leaves the ticket in its normal place. Nothing happens automatically: no ticket is closed, refused, delayed or re-routed by the model, and a ticket without the flag is handled exactly as today.

## Why these costs

A missed urgent ticket waits in the normal queue while a person, and often a team ("my whole team has the same problem", "customers are calling us"), cannot work. A false alarm costs a few minutes: someone reads the ticket earlier than its turn and moves on. We value a missed urgent ticket at about 5 false alarms. This is a product decision for the client to confirm; the sensitivity table below shows what other ratios would mean.

| FN : FP | Threshold | Recall | Precision | Flagged |
|---|---|---|---|---|
| 2 | 0.630 | 0.264 | 0.756 | 0.068 |
| 5 | 0.100 | 0.705 | 0.318 | 0.433 |
| 10 | 0.020 | 0.922 | 0.214 | 0.842 |
| 20 | 0.010 | 0.961 | 0.203 | 0.927 |

A ratio of 10 : 1 would flag 84% of all tickets, and a flag on most tickets stops meaning anything. A ratio of 2 : 1 would catch only 26% of urgent tickets.

## Why this threshold

Thresholds from 0.01 to 0.99 were swept on the **validation** window only. On 660 tickets the raw cost curve is jagged: a dip can come from four or five tickets. We pick the minimum of the curve averaged over ±0.02, so the decision does not hinge on that noise.

At 0.10: recall 0.71, precision 0.32, 43.3% of tickets flagged, about 4.9 flags on a day of 11.4 tickets.

## Why this model

- Model A, `logreg_C10_tone`: validation cost 58.3 per 100 tickets, average precision 0.512.
- Model B, `forest_leaf2`: validation cost 64.1 per 100 tickets, average precision 0.439.
- Keyword rule: cost 66.7 per 100 tickets, recall 0.50.

Rule fixed in advance: Best CV average precision per family; the tree ensemble replaces logistic regression only if it lowers validation cost by more than 3%. Model A is both cheaper and simpler, so the margin never came into play: every weight can be read, and each flag can be explained sentence by sentence.

Text carries most of the signal: without it, the same logistic regression (C=1) drops from a CV average precision of 0.49 to 0.36. What matters most is impact (people cannot work) and time pressure (a deadline today).

## The word "urgent" is not the signal; the tone is

In training (15.9% urgent overall), the same word means opposite things depending on how it is written:

| Style | Phrase in the ticket | Tickets | Urgent |
|---|---|---|---|
| calm request | Please treat as urgent. | 19 | 1.000 |
| calm request | This is urgent. | 8 | 1.000 |
| calm request | ASAP please. | 12 | 1.000 |
| shouting | URGENT!!! | 32 | 0.062 |
| shouting | URGENT!! | 27 | 0.222 |
| shouting | ASAP!!! | 33 | 0.152 |
| shouting | Very urgent. | 39 | 0.077 |
| shouting | Top priority please! | 32 | 0.125 |
| negation | This is not urgent, whenever you have time. | 22 | 0.000 |
| negation | Nothing urgent, just letting you know. | 21 | 0.095 |
| negation | Low priority. | 30 | 0.033 |

The naive "urgent / ASAP" rule matches all three styles, which is why it catches only 26% of urgent tickets. Word pairs (TF-IDF bigrams such as "treat as" and "very urgent") let the model tell them apart. Explicit tone features (exclamation marks, share of capitals) changed CV average precision by +0.005 (fold-to-fold spread ±0.07), so the word pairs already carry most of it. The gain is within noise, but the rule fixed in advance takes the best CV score, so the selected model includes them.

## Split and features (from the L5 audit)

- Time-based split: train Sep 2025 – Apr 2026, validation May – Jun 2026, test Jul – Aug 2026. CV folds inside training are grouped by requester. A strict requester purge would delete 88% of training and is not needed: requesters show no persistent urgency of their own.
- Excluded as post-submission: `assigned_priority`, `handling_team`, `resolution_hours`. With them, a model reaches a CV AUC of 0.985: the leakage demo in the experiment table.
- Excluded by policy: `requester_type`. Urgency should depend on the problem, not on who reports it. It is used only to check that no group is served worse.

## Transparency

Before the split code existed, a first exploration of the CSV looked at urgent rates over the whole year, test months included. Every label-based choice in the code uses the training or validation window only. The keyword rule was written by hand from domain reasoning (impact words such as “cannot work”, “can't work”, “unable to work” and time-pressure words such as “today”, “tonight”, “tomorrow”). If that early look influenced it, the effect is to make the baseline *harder* to beat, not easier.
