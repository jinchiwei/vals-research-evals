# PTB-XL ECG reports: data for the labelling task

All files are read-only and derived from PTB-XL 1.0.3 (Wagner et al., 2020; PhysioNet,
https://doi.org/10.13026/kfzx-aw45), licensed CC BY 4.0 (`LICENSE.txt`). Changes made for this task:
records were selected and given new random IDs, report whitespace was collapsed to single spaces, and
the SCP-ECG statements were aggregated to the 5 diagnostic superclasses. No ECG signals are included.

## Files

| File | Rows | Columns |
|---|---|---|
| `dev_reports.csv` | 2,000 development reports, with labels | `record_id`, `report`, `NORM`, `MI`, `STTC`, `CD`, `HYP` (0/1 each) |
| `hidden_reports.csv` | 500 reports to label, **without labels** | `record_id`, `report` |
| `diagnostic_statements.csv` | the 44 diagnostic SCP-ECG statements | `scp_code`, `description`, `category`, `superclass`, `subclass` |

CSV files are UTF-8 with a header row; reports may contain commas and are quoted where needed.

## The reports

Each report is the free-text interpretation a cardiologist wrote for a 12-lead ECG (Physikalisch-
Technische Bundesanstalt, Berlin, 1989-1996). Most are German, many English, a few Swedish. Some contain
abbreviations, lead lists and typing errors. A few end with `Edit:` followed by a second cardiologist's
note; the labels reflect the final coded statements. Device-generated reports are not included.

## How the labels were made

PTB-XL converted each report into standardized SCP-ECG statements, each with a likelihood (0-100) taken
from hedging words in the report (for example "cannot rule out", "possible", "probable"). A validating
cardiologist could also change statements. Each diagnostic statement belongs to one superclass
(`diagnostic_statements.csv`), and a record's label is the set of superclasses of its diagnostic
statements:

- **NORM**: normal ECG
- **MI**: myocardial infarction (any location or age), and subendocardial injury in named leads
- **STTC**: ST/T changes (ischaemic ST-T changes, non-specific ST or T changes, long QT, digitalis,
  electrolyte or drug effects, ST-T changes compatible with aneurysm)
- **CD**: conduction disturbance (bundle branch and fascicular blocks, AV blocks, WPW, non-specific intraventricular conduction delay)
- **HYP**: hypertrophy (ventricular hypertrophy and atrial enlargement or overload)

**A statement counts whatever its likelihood**: a hedged statement ("possible LVH", "Infarkt nicht
auszuschließen") is a positive label in this task, as in the standard PTB-XL benchmark rule. Rhythm and
form statements (sinus rhythm, atrial fibrillation, axis, premature beats, low voltage and so on) are
not diagnostic statements and do not produce a label by themselves. Every record in this task has at
least one superclass, and a record may have several.
