# Label free-text ECG reports with diagnostic superclasses (PTB-XL)

## Session limit and what is graded (read first)

- **Your session lasts at most 45 minutes** (2700 seconds) of wall-clock time.
  When the limit is reached the session is stopped, whether or not you have finished.
- **What is graded is `/workspace/output/labels.json` as it is when the session ends.** Nothing is
  finished, fixed or rerun for you afterwards. If the file is missing or invalid at that moment, the
  score is 0.
- We recommend writing a complete, valid `labels.json` early and improving it afterwards.

## The task

A cardiology research registry wants structured diagnoses from the free-text interpretations that
cardiologists wrote for 12-lead ECGs, so that it can build cohorts without re-reading every report.
Your job is to assign each report the **diagnostic superclasses** it states, using the coding
convention of the PTB-XL dataset.

You get 2,000 development reports **with** their labels and 500 reports **without** labels
(`/workspace/data/hidden_reports.csv`). Label the 500 reports. Start with
`/workspace/data/README.md`: it describes the reports (mostly German, some English and Swedish), the
five superclasses (NORM, MI, STTC, CD, HYP), the statement-to-superclass mapping
(`diagnostic_statements.csv`) and the rule that hedged statements count as present.

How you produce the labels is up to you: reading the reports, writing code, or both.

## Required output

Write `/workspace/output/labels.json`: one JSON object mapping **every** `record_id` in
`hidden_reports.csv` (and nothing else) to a list of superclass names, for example

    {"r0123abcd": ["MI", "STTC"], "r4567ef01": ["NORM"]}

- Names must be exactly `NORM`, `MI`, `STTC`, `CD`, `HYP`, each at most once per record; order does not
  matter. An empty list is allowed (it means no superclass), although every record in this task has at
  least one.
- Standard JSON only (no comments, no NaN). The file must be a regular file under 5 MB.
- Only `/workspace/output/` is carried to the grader. Other files there are ignored.

## Environment

- Python: `/opt/benchmark-venv/bin/python3` (packages: numpy==2.1.3, scipy==1.14.1, pandas==2.2.3, scikit-learn==1.5.2). No package installation.
- Network access in this sandbox is limited to the model API (api.anthropic.com).
- 2 CPUs and 4096 MB RAM.

## How you are scored

A separate grader compares your labels with the hidden labels. The clinical gate has two parts, and
both must be met:

1. Cohen's kappa of at least 0.60 in **each** of the five superclasses;
2. macro-averaged F1 over the five superclasses of at least 0.80.

The headline score is 1 if `labels.json` is present and valid and both parts are met; otherwise it is
0, with no partial credit. Macro F1 is also reported as a quality score and compared with a text
classifier trained on the development reports, on the same 500 reports.
