# L7 error analysis

The 12 most confident mistakes on validation at threshold 0.10: urgent tickets with the lowest scores (missed) and non-urgent tickets with the highest scores (false alarms).

*Effect* is how much the urgency score drops when that piece of evidence is removed (occlusion). The hypotheses are generated as a starting point: **the team must confirm or correct each one** in the *Team note* line.

## 1. Missed urgent ticket (FN) · `T-002284` · score 0.002

2026-06-20 15:45:41 · billing · walk_in · label 1

> Walk-in: I need a copy of the March invoice.

Strongest cues: "submitted_at = 2026-06-20 15:45" -0.00; "Walk-in: I need a copy of the March invoice." +0.00; "category = billing" -0.00; "initial_channel = walk_in" -0.00

**Hypothesis.** Nothing in the text signals impact or a deadline that the model has learned to recognise. The panel probably judged context that the ticket does not contain.

**Team note.** _to be completed_

## 2. Missed urgent ticket (FN) · `T-002136` · score 0.004

2026-06-10 16:56:29 · hardware · walk_in · label 1

> walk-in: the keyboard has several dead keys.

Strongest cues: "walk-in: the keyboard has several dead keys." +0.00; "category = hardware" -0.00; "submitted_at = 2026-06-10 16:56" -0.00; "initial_channel = walk_in" -0.00

**Hypothesis.** Nothing in the text signals impact or a deadline that the model has learned to recognise. The panel probably judged context that the ticket does not contain.

**Team note.** _to be completed_

## 3. Missed urgent ticket (FN) · `T-001993` · score 0.005

2026-05-28 21:49:35 · general_inquiry · walk_in · label 1

> Walk-in: where can I find the user guide. This is not urgent, whenever you have time.

Strongest cues: "This is not urgent, whenever you have time." -0.01; "submitted_at = 2026-05-28 21:49" -0.00; "Walk-in: where can I find the user guide." +0.00; "category = general_inquiry" +0.00

**Hypothesis.** Nothing in the text signals impact or a deadline that the model has learned to recognise. The panel probably judged context that the ticket does not contain.

**Team note.** _to be completed_

## 4. Missed urgent ticket (FN) · `T-002234` · score 0.006

2026-06-17 21:59:58 · billing · web_form · label 1

> Please update our billing address. Best regards.

Strongest cues: "Please update our billing address." +0.00; "submitted_at = 2026-06-17 21:59" -0.00; "category = billing" -0.00; "initial_channel = web_form" -0.00

**Hypothesis.** Nothing in the text signals impact or a deadline that the model has learned to recognise. The panel probably judged context that the ticket does not contain.

**Team note.** _to be completed_

## 5. Missed urgent ticket (FN) · `T-002219` · score 0.009

2026-06-16 20:17:38 · hardware · chat · label 1

> Good morning, Top priority please! The projector in room 3 has no image. I tried clearing the cache. Thank you.

Strongest cues: "submitted_at = 2026-06-16 20:17" -0.01; "initial_channel = chat" -0.00; "category = hardware" -0.00; "I tried clearing the cache." +0.00

**Hypothesis.** Nothing in the text signals impact or a deadline that the model has learned to recognise. The panel probably judged context that the ticket does not contain.

**Team note.** _to be completed_

## 6. Missed urgent ticket (FN) · `T-002390` · score 0.011

2026-06-26 12:33:40 · hardware · mobile_app · label 1

> The keyboard has several dead keys. I am not sure which team handles this.

Strongest cues: "I am not sure which team handles this." +0.00; "category = hardware" -0.00; "submitted_at = 2026-06-26 12:33" -0.00; "The keyboard has several dead keys." +0.00

**Hypothesis.** Nothing in the text signals impact or a deadline that the model has learned to recognise. The panel probably judged context that the ticket does not contain.

**Team note.** _to be completed_

## 7. False alarm (FP) · `T-002103` · score 0.877

2026-06-09 13:30:47 · software · phone · label 0

> Caller reports: please install the PDF editor. The entire office is down. The deadline is today.

Strongest cues: "The deadline is today." +0.26; "The entire office is down." +0.19; "Caller reports: please install the PDF editor." +0.16; "initial_channel = phone" +0.07

**Hypothesis.** Flagged mainly because of "The deadline is today." (+0.26). Tickets with this sentence are urgent in 45% of 31 training cases, so some false alarms on it are expected.

**Team note.** _to be completed_

## 8. False alarm (FP) · `T-002108` · score 0.872

2026-06-09 14:32:45 · account_access · email · label 0

> Good morning, The new portal sends me in a loop back to the sign-in page. The client presentation is in one hour. All users at our site are affected. A colleague suggested I open a ticket. I am using the standard company laptop.

Strongest cues: "All users at our site are affected." +0.47; "The client presentation is in one hour." +0.14; "category = account_access" +0.07; "submitted_at = 2026-06-09 14:32" -0.03

**Hypothesis.** Flagged mainly because of "All users at our site are affected." (+0.47). Tickets with this sentence are urgent in 77% of 13 training cases, so some false alarms on it are expected.

**Team note.** _to be completed_

## 9. False alarm (FP) · `T-002420` · score 0.869

2026-06-29 15:10:29 · account_access · mobile_app · label 0

> Hello support, The new sign-in asks for a code I never receive. I am stuck outside all our tools. Thank you.

Strongest cues: "I am stuck outside all our tools." +0.61; "Hello support, The new sign-in asks for a code I never receive." +0.13; "category = account_access" +0.07; "Thank you." +0.04

**Hypothesis.** Flagged mainly because of "I am stuck outside all our tools." (+0.61). Tickets with this sentence are urgent in 80% of 5 training cases, so some false alarms on it are expected.

**Team note.** _to be completed_

## 10. False alarm (FP) · `T-002339` · score 0.723

2026-06-23 15:29:07 · account_access · email · label 0

> Hi, The new sign-in asks for a code I never receive. It worked fine last week. I am stuck outside all our tools.

Strongest cues: "I am stuck outside all our tools." +0.59; "category = account_access" +0.11; "Hi, The new sign-in asks for a code I never receive." +0.06; "submitted_at = 2026-06-23 15:29" -0.05

**Hypothesis.** Flagged mainly because of "I am stuck outside all our tools." (+0.59). Tickets with this sentence are urgent in 80% of 5 training cases, so some false alarms on it are expected.

**Team note.** _to be completed_

## 11. False alarm (FP) · `T-002195` · score 0.685

2026-06-15 14:49:28 · account_access · web_form · label 0

> Good morning, After the switch to single sign-on my account is not recognised. I can't do anything on my machine. Thank you.

Strongest cues: "I can't do anything on my machine." +0.56; "Thank you." +0.28; "category = account_access" +0.12; "submitted_at = 2026-06-15 14:49" -0.05

**Hypothesis.** Flagged mainly because of "I can't do anything on my machine." (+0.56). Tickets with this sentence are urgent in 35% of 52 training cases, so some false alarms on it are expected.

**Team note.** _to be completed_

## 12. False alarm (FP) · `T-001921` · score 0.677

2026-05-20 07:33:58 · account_access · phone · label 0

> Caller reports: I need access to the shared finance folder. I cannot work at all until this is fixed.

Strongest cues: "I cannot work at all until this is fixed." +0.55; "initial_channel = phone" +0.13; "category = account_access" +0.12; "submitted_at = 2026-05-20 07:33" -0.07

**Hypothesis.** Flagged mainly because of "I cannot work at all until this is fixed." (+0.55). Tickets with this sentence are urgent in 46% of 41 training cases, so some false alarms on it are expected.

**Team note.** _to be completed_
