# Mutation-prediction protocol

How `pcnsl/prediction_eval.py` compares arms on held-out mutation status. Written
before any prediction on patient rows. Status on 2026-11-14: the harness runs on
synthetic rows; **no arm has been run on patient data and no frontier-model result exists.**

## What is fixed in advance

| Item | Value |
|---|---|
| Seed | 20261114 |
| Folds | 5, patient-stratified, per gene |
| Gene eligibility | at least 5 patients with a reported qualifying alteration and at least 5 without, decided from label counts before any model runs |
| Features | one prespecified feature group per run (`all` by default, `clinical` as the signal control), identical for every arm |
| Metrics | AUROC, average precision, Brier score |
| Score direction | higher probability means "qualifying alteration reported"; never flipped |
| Selection | no hyperparameter search, no feature, gene or model selection on held-out results |

Changing any of these makes a new protocol version. It is not a rerun.

**Endpoint.** Label 1 means a qualifying alteration was reported for the gene. Label 0
means none was reported. Label 0 does not establish that the gene is unaltered,
and no report or request calls it that.

## Splits

`make_folds(dataset, gene)` orders patients within each class by SHA-256 of
`(seed, gene, patient key)` and deals them round-robin into five folds. The folds
depend only on those three things, so they are the same on every host, Python
version and row order, and no library is involved. Every fold has both classes in
train and test; class counts per fold differ by at most one.

Folds are per gene, because one shared split cannot keep both classes in every
fold for every gene. All arms for a gene use the same folds; each arm result
carries a `split_fingerprint` and `feature_fingerprint` to show it.

The folds depend on the case identifiers. `prediction_data.load_dataset` must
return the same anonymous identifiers on every call, or the folds change.

## Held-out labels

An arm receives a `Fold`: training rows with labels and test rows without. The
type has no field for test labels, and `build_fold` reads labels at training
indices only. The scorer in `run_evaluation` is the only code that reads held-out
labels, after the arm has returned its probabilities.

Cases get fold-local tokens (`train-001`, `test-001`) in a hash order that does
not depend on the label. Original case identifiers never reach an arm.

Tests check this directly: flipping every held-out label leaves each arm's inputs
and each request byte-identical.

## Preprocessing

Values are rounded once to six significant digits so every arm sees the same
numbers. Missing values stay missing. All 64 genomically observed patients are
kept; nothing is dropped for missing features.

Imputation and scaling are fitted inside each training fold (`fit_preprocessor`)
and applied to that fold's test rows. Test rows never contribute to a median,
mean or scale. A column with no training values becomes zero for that fold.

## Arms

| Arm | What it does | When it cannot run |
|---|---|---|
| `training_prevalence` | training-fold positive fraction for every test case | always runs |
| `logistic_regression` | L2, C=1, lbfgs, train-fold median imputation and scaling | `unavailable` if numpy or scikit-learn is missing |
| `tabpfn` | the real `tabpfn.TabPFNClassifier`, package defaults, fixed seed, missing values passed as NaN | `unavailable` if tabpfn, the checkpoint or a needed parameter is missing |
| `direct_llm` | one request per fold to a caller-supplied client | `unavailable` with no client |
| `ReplayArm` | scores stored responses, such as files from an agent run, with the same folds and parser | n/a |

No arm is ever replaced by another model. A missing arm has `status: unavailable`,
a reason, and no scores.

**TabPFN** is offline by default. It needs an explicit local checkpoint
(`--tabpfn-model-path`), sets `HF_HUB_OFFLINE=1` before tabpfn is imported, and
records the checkpoint's SHA-256 and the installed version. Library errors are
recorded as a fixed code such as `tabpfn_fit_failed:TabPFNLicenseError`, never the
library's message, which can carry URLs or tokens.

**Direct LLM.** `build_public_payload` returns the request and, separately, the
evaluator's key. The request holds a task statement, the gene, the label
definition, sanitized feature names, labelled training rows and unlabelled test
rows. `assert_payload_sanitized` refuses any other field, any non-numeric value,
any token that is not fold-local and any cohort identifier. Feature descriptors
preserve spaces in anatomical regions and parenthesized units, up to 128 characters.
Paths, markup, control characters and long digit strings are replaced with
`feature_NNN`, and the count is reported. The public-release extractor separately
enforces its fixed metric allowlist. All 439 released feature names retain their
meaning; this was corrected before any frontier prediction call.

The harness opens no network connection. The caller supplies the client and is
responsible for sending rows only to an endpoint approved for these data; the
command line refuses `--llm-command` with `--root` unless
`--llm-endpoint-approved` is given.

`payload_preflight` reports exact request sizes per fold before anything is
sent. With `max_request_chars` set, an oversized request is refused, not
truncated. Features are never dropped to make a request fit; a smaller feature
group is a new prespecified run.

## Response parser

`parse_predictions(response, expected_case_ids)` accepts exactly

```json
{"predictions": [{"case": "test-001", "probability": 0.42}]}
```

bare or inside one code fence. Every expected case must appear once. A
probability must be a JSON number from 0 to 1. Prose, extra or missing cases,
duplicate cases or keys, strings, booleans, `NaN`, `Infinity`, percentages and
out-of-range values are all rejected. Nothing is clipped, rescaled or repaired.

A fold that fails to parse is recorded with a fixed reason code. The arm then has
`status: parse_failure` and no pooled score for that gene. Retries are off unless
`max_attempts` is raised before the run, and the value is reported.

## Scores

Per arm and gene the report gives pooled out-of-fold AUROC, average precision and
Brier score, per-fold values, a patient-level bootstrap interval, and paired
AUROC differences between arms on the same resamples. `summary` is the unweighted
mean across genes.

An arm run on a prespecified subset of folds (for example fold 0 for the model
pilot) has `status: partial` and per-fold scores only. Compare it with the other
arms' entries for the same fold, not with their pooled scores.

Three things to keep in mind when reading the numbers, all measured on synthetic
rows with no signal (64 rows, 12 positives, 12 noise features):

- **Training prevalence scores below 0.5 on pooled AUROC by construction** (0.439
  here). A fold with more test positives has a lower training prevalence. Its
  per-fold AUROC is exactly 0.5; judge that arm by Brier score.
- **One gene's AUROC is noisy.** Across 40 no-signal datasets, logistic
  regression's pooled AUROC had mean 0.49, SD 0.13, range 0.16 to 0.71.
- **The bootstrap interval is not a significance test.** It excluded 0.5 in 7 of
  those 40 no-signal datasets. It describes resampling of one set of fitted
  folds. A label-permutation null is the right comparison and is not implemented.

So poor performance by every arm does not show the labels are bad, and one arm
beating another on one gene does not show a capability gap.

## Running it

```bash
# Anywhere: tests and a synthetic smoke run (standard library only; scikit-learn tests skip if absent)
python3 -m unittest tests.test_prediction_eval -v
python3 -m pcnsl.prediction_eval --synthetic --out /tmp/smoke.json

# Data host only: request sizes first, then baselines
python3 -m pcnsl.prediction_eval --root RELEASE_ROOT --preflight --genes MYD88 CD79B --out preflight.json
python3 -m pcnsl.prediction_eval --root RELEASE_ROOT --genes MYD88 CD79B \
  --tabpfn-model-path CHECKPOINT --out baselines-all.json
python3 -m pcnsl.prediction_eval --root RELEASE_ROOT --genes MYD88 CD79B --feature-groups clinical \
  --tabpfn-model-path CHECKPOINT --out baselines-clinical.json
```

The report is aggregate only: no case identifiers, rows or per-patient
probabilities. Output files are never overwritten.

From Python:

```python
from pcnsl import prediction_eval as pe
folds = pe.make_folds(dataset, "MYD88")
payload, key = pe.build_public_payload(dataset, "MYD88", folds[0]["train"], folds[0]["test"], feature_group="all")
p = pe.parse_predictions(response_text, [row["case"] for row in payload["test"]])
scores = pe.evaluate_probabilities([dataset["labels"]["MYD88"][i] for i in key], p)
report = pe.run_baselines(dataset, genes=["MYD88", "CD79B"],
                          arms=["training_prevalence", "logistic_regression", pe.TabPFNArm(model_path=checkpoint)],
                          extra_arms=[pe.DirectLLMArm(client=client, model_label="...", only_folds=[0])])
```

`iter_folds(dataset, ...)` yields the same folds for building agent tasks.

## Verified so far, and not

Verified on teal on 2026-11-14 with synthetic rows only:

- 44 tests pass with scikit-learn 1.9.1 present; 38 pass and 6 skip on bare Python 3.13.
- The logistic-regression arm reproduces an independent scikit-learn pipeline on
  the same folds to three decimals, pooled and per fold.
- The planted-signal synthetic gene scores 0.80 pooled AUROC with logistic regression.

Not verified:

- **Real TabPFN has not produced a score.** With tabpfn 10.0.0 and no checkpoint
  the real classifier was constructed and `fit` was reached, then stopped with
  `TabPFNLicenseError` (its default weights need licence acceptance). The adapter's
  checkpoint, seed and hash handling is tested against a stand-in class only.
- No request has been sent to any model. The LLM arm is tested with scripted
  stand-ins.
- Nothing has run against `prediction_data.load_dataset` or patient rows.
- Request size for 400+ features is unmeasured; run the preflight on the data host.
