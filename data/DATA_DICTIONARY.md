# Support desk tickets — data dictionary

**Project 2 · Responsible service triage model**

## Provenance and permitted use

- **Source:** fully synthetic, written by the instructor with a reproducible generator. No real people, organisations or tickets are involved, and any resemblance is coincidental.
- **Permitted use:** coursework for this laboratory only: analysis, modelling and your portfolio. You may show figures and examples from it in your demo and model card.
- **Labels:** `urgent_label` was assigned by the (fictional) support desk’s review panel. It is based on what the ticket says and on its context at the moment of submission. Treat these labels as approved, but not perfect: like real labels, a small share are inconsistent.

## File

`tickets.csv`: about 3,000 rows, one per ticket. It covers one year of tickets, from September 2025 to August 2026, sorted by submission time.

## Columns

| Column | Type | Meaning | Notes |
|---|---|---|---|
| `ticket_id` | string | Ticket identifier, e.g. `T-000123` | Identifier only. |
| `submitted_at` | datetime | When the ticket was submitted (`YYYY-MM-DD HH:MM:SS`) | |
| `requester_id` | string | Pseudonymous ID of the person who opened the ticket | One requester may open many tickets. |
| `requester_type` | category | `employee`, `contractor` or `external_customer` | |
| `category` | category | Category the requester chose on the form | 8 categories. |
| `initial_channel` | category | How the ticket arrived: `web_form`, `email`, `phone`, `chat`, `walk_in`, `mobile_app` | For phone and walk-in tickets, staff type a short summary. |
| `description` | text | The ticket text as submitted | English. |
| `description_length` | integer | Number of characters in `description` | |
| `attachments_count` | integer | Number of files attached at submission | |
| `assigned_priority` | category | Priority P1–P4 set by staff | |
| `handling_team` | category | Team that handled the ticket: `tier1`, `tier2`, `escalation` | |
| `resolution_hours` | float | Hours from submission to resolution | Empty if the ticket was still open when the data was exported. |
| `urgent_label` | 0/1 | **Target.** 1 = the ticket should have been reviewed urgently | About 1 in 6 tickets are urgent. |

## Before you model: your audit questions

The data was exported from a working system. It has not been cleaned for you. As a team, answer these in L5:

1. Prediction time: which columns would exist **at the moment a ticket is submitted**, and which only later? Use only the first group as features.
2. Are there duplicates, missing values or inconsistent spellings? How will you handle each one, using only the training data?
3. Do some requesters appear many times? What does that mean for your split?
4. The model will be used on **future** tickets. Which split reflects that?
5. Does anything change over the year: categories, channels, the share of urgent tickets?

## Data you must not use

You must not add identifiable data from real tickets, from the university or from anywhere else. You may propose a public tabular dataset as an alternative. You can use it only after the instructor approves it, and you must record its source and licence.
