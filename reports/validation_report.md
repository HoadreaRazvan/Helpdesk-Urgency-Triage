# L7 validation report

Validation window: 2026-05-01 to 2026-06-30, 660 tickets, 129 urgent (19.5%).

## 1. The model ladder

| Model | Recall | Precision | F1 | Accuracy | Flagged | TP | FN | FP | TN | Cost / 100 |
|---|---|---|---|---|---|---|---|---|---|---|
| Baseline 1 · Majority class | 0.000 | 0.000 | 0.000 | 0.805 | 0.000 | 0 | 129 | 0 | 531 | 97.727 |
| Baseline 2 · Keyword rule (impact + time pressure) | 0.504 | 0.351 | 0.414 | 0.721 | 0.280 | 65 | 64 | 120 | 411 | 66.667 |
| Model A · Logistic regression (logreg_C10_tone, t=0.10) ✔ selected | 0.705 | 0.318 | 0.439 | 0.647 | 0.433 | 91 | 38 | 195 | 336 | 58.333 |
| Model B · Random forest (forest_leaf2, t=0.07) | 0.822 | 0.256 | 0.390 | 0.498 | 0.627 | 106 | 23 | 308 | 223 | 64.091 |
| Naive rule · 'urgent' / 'ASAP' words | 0.264 | 0.327 | 0.292 | 0.750 | 0.158 | 34 | 95 | 70 | 461 | 82.576 |

The majority baseline is right 80% of the time and catches no urgent ticket at all: accuracy hides exactly what the client cares about. The models are compared on cost, recall and precision instead.

## 2. Threshold

Costs declared before modelling: missed urgent ticket (FN) = 5, false alarm (FP) = 1. Chosen threshold: **0.10**, the minimum of the cost curve smoothed over ±0.02.

| Threshold | Recall | Precision | Flagged | FN | FP | Cost | Smoothed |  |
|---|---|---|---|---|---|---|---|---|
| 0.030 | 0.891 | 0.227 | 0.768 | 14 | 392 | 462.000 | 465.000 |  |
| 0.050 | 0.814 | 0.254 | 0.626 | 24 | 308 | 428.000 | 429.600 |  |
| 0.070 | 0.767 | 0.277 | 0.541 | 30 | 258 | 408.000 | 402.600 |  |
| 0.090 | 0.736 | 0.312 | 0.461 | 34 | 209 | 379.000 | 388.800 |  |
| 0.100 | 0.705 | 0.318 | 0.433 | 38 | 195 | 385.000 | 384.600 | ◀ chosen |
| 0.120 | 0.667 | 0.333 | 0.391 | 43 | 172 | 387.000 | 393.200 |  |
| 0.150 | 0.605 | 0.348 | 0.339 | 51 | 146 | 401.000 | 400.800 |  |
| 0.200 | 0.566 | 0.410 | 0.270 | 56 | 105 | 385.000 | 391.600 |  |
| 0.300 | 0.442 | 0.463 | 0.186 | 72 | 66 | 426.000 | 429.800 |  |
| 0.400 | 0.341 | 0.518 | 0.129 | 85 | 41 | 466.000 | 463.600 |  |
| 0.500 | 0.318 | 0.603 | 0.103 | 88 | 27 | 467.000 | 466.200 |  |

Sensitivity: the threshold that the same rule would pick for other cost ratios.

| FN : FP | Threshold | Recall | Precision | Flagged |
|---|---|---|---|---|
| 2 | 0.630 | 0.264 | 0.756 | 0.068 |
| 5 | 0.100 | 0.705 | 0.318 | 0.433 |
| 10 | 0.020 | 0.922 | 0.214 | 0.842 |
| 20 | 0.010 | 0.961 | 0.203 | 0.927 |

## 3. Calibration

Expected calibration error 0.068, Brier score 0.134. Mean score 0.172 against an observed urgent rate of 0.195.

| Score from | to | Tickets | Mean score | Actually urgent |
|---|---|---|---|---|
| 0.000 | 0.100 | 374 | 0.041 | 0.102 |
| 0.100 | 0.200 | 108 | 0.144 | 0.167 |
| 0.200 | 0.300 | 55 | 0.241 | 0.291 |
| 0.300 | 0.400 | 38 | 0.352 | 0.342 |
| 0.400 | 0.500 | 17 | 0.439 | 0.176 |
| 0.500 | 0.600 | 17 | 0.549 | 0.353 |
| 0.600 | 0.700 | 18 | 0.649 | 0.333 |
| 0.700 | 0.800 | 10 | 0.734 | 0.900 |
| 0.800 | 0.900 | 13 | 0.853 | 0.769 |
| 0.900 | 1.000 | 10 | 0.946 | 1.000 |

Validation has more urgent tickets than training (19.5% against 15.9%), so the scores are shifted accordingly. The threshold was chosen on validation, which already takes this offset into account. Show the score to staff as a ranking signal, not as an exact probability.

## 4. What the flag changes in the queue

On an average day (11.4 tickets), the model flags 4.9. An urgent ticket has on average **8.7** tickets ahead of it in first-come-first-served order, and **6.4** when flagged tickets are read first. 31.8% of urgent tickets are among the first three read each day, against 20.2% without the flag.

## 5. Plausible shifts

| Scenario | Kind | Recall | Precision | Flagged | Cost / 100 | Note |
|---|---|---|---|---|---|---|
| Validation as observed | observed | 0.705 | 0.318 | 0.433 | 58.333 | Reference point. |
| Every ticket arrives through an unseen channel | simulated | 0.698 | 0.295 | 0.462 | 62.121 | Like mobile_app, which first appeared in May. The model must fall back on the text. |
| Every requester adds "URGENT!!!" | simulated | 0.612 | 0.321 | 0.373 | 63.182 | Shouting is rarely urgent in training. A robust model should barely move. |
| Every requester adds a neutral "Thank you." | simulated | 0.767 | 0.284 | 0.527 | 60.455 | Control for the row above: the same extra length, no urgency word. |
| A quarter of non-urgent requesters copy an impact phrase | simulated | 0.705 | 0.261 | 0.529 | 67.879 | They append "My whole team has the same problem." to get faster service. Labels stay non-urgent. |
| Observed: 2026-05 | observed | 0.702 | 0.371 | 0.403 | 57.014 | 221 tickets over 28 days. |
| Observed: 2026-06 | observed | 0.707 | 0.294 | 0.449 | 58.998 | 439 tickets over 30 days. |
| Observed: mobile_app tickets only | observed | 0.429 | 0.136 | 0.407 | 72.222 | The real unseen channel. Small sample, so read with care. |

## 6. Subgroups and time slices

Recall and precision are reported only for slices with at least 30 tickets and 5 urgent ones. `requester_type` is not a model input; it is checked here to see whether one group of people is served worse.

| Slice | Value | Tickets | Urgent | Recall | Precision | Flagged |
|---|---|---|---|---|---|---|
| requester_type | contractor | 80 | 11 | 0.818 | 0.250 | 0.450 |
| requester_type | employee | 399 | 79 | 0.684 | 0.318 | 0.426 |
| requester_type | external_customer | 181 | 39 | 0.718 | 0.350 | 0.442 |
| initial_channel | chat | 82 | 19 | 0.684 | 0.433 | 0.366 |
| initial_channel | email | 183 | 26 | 0.577 | 0.214 | 0.383 |
| initial_channel | mobile_app | 54 | 7 | 0.429 | 0.136 | 0.407 |
| initial_channel | phone | 90 | 29 | 0.862 | 0.410 | 0.678 |
| initial_channel | unknown | 12 | 2 | – | – | 0.417 |
| initial_channel | walk_in | 38 | 5 | 0.400 | 0.111 | 0.474 |
| initial_channel | web_form | 201 | 41 | 0.780 | 0.400 | 0.398 |
| month | 2026-05 | 221 | 47 | 0.702 | 0.371 | 0.403 |
| month | 2026-06 | 439 | 82 | 0.707 | 0.294 | 0.449 |

## 7. Errors

12 mistakes are inspected one by one in [error_analysis.md](error_analysis.md).
