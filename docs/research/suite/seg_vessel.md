# seg_vessel: retinal vessel segmentation (CHASE_DB1), second human observer as the bar

Worker: Claude Opus 5.5 (`claude-opus-5-5`), 2026-11-15, on teal, workstream V of round 3
(`round3-prereg.md`). Family code: `suite/families/seg_vessel/`. Tests: `tests/suite/test_seg_vessel.py`.
Data (outside Git): `/home/jkwei/data/vals-suite/seg_vessel/`.

## 0. Fixed before any comparator or agent run (written 2026-11-15 01:06 EST)

Nothing in this section was changed after a comparator or agent result was seen.

- **Reference.** First human observer (`*_1stHO.png`), as in Fraz et al. 2012 and the CHASE_DB1
  literature.
- **Split.** By child. Children 01–14 permuted with `numpy.random.default_rng(20261114)`; first 10
  development (20 images, with both observers' labels), last 4 hidden (8 images). Both eyes of a child
  stay on the same side. Case IDs drawn with `default_rng(20261115)`. The split and its SHA-256 are in
  `DATA_ROOT/split.json`, written once by `prepare_data.py`, which refuses to overwrite it.
- **Per-image clinical bar.** A hidden image is acceptable if the pipeline's mask, compared with the
  first observer, has **Dice ≥ the second observer's Dice on that image and clDice ≥ the second
  observer's clDice on that image**. In words: the pipeline agrees with the first observer at least
  as well as a second trained human did, on overlap and on centreline (connectivity) overlap. The
  two numbers per hidden image are computed with the grader's own functions and stored only on the
  verifier side (`reference/bar.json`). No slack is added. Metrics are over the whole 999 × 960 image
  (CHASE_DB1 ships no field-of-view mask).
- **clDice.** Hard clDice of Shit et al. (CVPR 2021, arXiv:2003.07311, eq. 1–3): topology precision
  |S(P) ∩ L| / |S(P)| and sensitivity |S(L) ∩ P| / |S(L)|, harmonic mean; S = `skimage` 2D skeletonize.
- **Reward.** Suite contract. `clinically_acceptable` = fraction of the 8 hidden images acceptable;
  `reward` = that fraction if every image ran, was valid and was on time, else 0; `quality` = mean Dice.
- **Family bar (scoring rule).** The family is scored only if the specialist (U-Net, below) is
  acceptable on **at least 4 of the 8 hidden images**. If it passes fewer, the family is excluded from
  scoring and kept as a worked example, as pharyngitis was. The Frangi comparator is reported, not
  required to pass.
- **Gap verdict.** DESIGN.md per-case rule as operationalised in `hosted-agents2.md`: S = hidden
  images the specialist passes; paired bootstrap of pass (and Dice) differences, agent minus
  specialist, on S (`suite.core.metrics.paired_bootstrap_difference`, mean, 2000 resamples, seed
  20261114, 95 % percentile interval). Gap shown if the agent fails at least one image in S and the
  pass-difference interval lies entirely below 0.
- **Per-image time limit: 60 s** wall clock on 4 CPUs, 8 GB, no GPU, measured by the grader. Source:
  a workflow choice, not a literature number; a fundus screening read is interactive, and 60 s is far
  more than a small CNN or a filter bank needs on one 999 × 960 image on CPU. It must be at least 5 × the
  specialist's measured CPU time (checked in section 5; if it were not, this would be recorded as a
  change, before any agent run).
- **Agent session: 3600 s.** Image: the suite's scientific Python plus CPU-only PyTorch 2.15.0, no
  pretrained weights (as seg_spleen build tier).
- **Comparators.** Specialist: a small U-Net trained on the 20 development images only (GPU allowed for
  training), run on hidden images on CPU through the grader. Simple: Frangi vesselness with a threshold
  fitted on development images only. Reference point: the second observer itself (by construction it
  sits exactly on the bar: it is acceptable on every image, with zero margin).

## 1. Literature check (short; sources)

| Item | Value | Source |
|---|---|---|
| Inter-observer agreement on CHASE_DB1 | Second observer vs first: sensitivity 0.7705, specificity 0.9778, accuracy 0.9561 (FOV-masked convention) | Secondary: arXiv:1812.07110 table, citing Fraz et al. 2012 (primary not read). Our own computation on the official files (whole image, no FOV): **Dice 0.777 (0.739–0.827), clDice 0.835**, sensitivity 0.768, specificity 0.985, accuracy 0.970 (all 28 images). The MedOtter mirror README independently reports Dice 0.777 (0.739–0.827). |
| Deep-learning results on CHASE_DB1 (usual 20/8 split, first 20 images train) | F1 (= Dice): LadderNet 0.8031, IterNet 0.8073, SA-UNet 0.8153 | Paper-reported, via the hyper.ai SOTA aggregator; primary papers not re-read. These are above the second observer's 0.777, so a learned model can plausibly reach the bar; a hand-tuned filter usually cannot. |
| Frangi | Multiscale Hessian vesselness | Frangi AF et al., MICCAI 1998. No CHASE_DB1 Frangi F1 was verified; our own fit is in section 4. |
| clDice | Centreline Dice, topology precision/sensitivity on skeletons | Shit S et al., CVPR 2021, arXiv:2003.07311. |

`metrics-review.md` has no vessel-specific entry; Dice plus a connectivity measure is the usual pairing
for tubular structures (clDice paper).

## 2. Data (verified)

- Official page: https://researchinnovation.kingston.ac.uk/en/datasets/chasedb1-retinal-vessel-reference-dataset-4/
  shows "CHASEDB1 File: application/zip, 2.4 MB ... Licence: Creative Commons: Attribution 4.0"
  (read with the gstack headless browser 2026-11-15; screenshot kept with the data).
- The file itself is behind a Cloudflare "Verify you are human" check. The worker did not click it or
  spoof a browser. **Jin downloaded `CHASEDB1.zip` in a browser on 2026-11-15** and copied it to teal:
  2,513,926 bytes, SHA-256 `bb750b73633492d700e56d91578ee3cdb7e4dbd08279e7465583e9efd26790b6`, 84 entries.
  This is the source of record. A Hugging Face mirror pulled earlier (MedOtter/CHASE_DB1, revision
  `c8051462`) is byte-identical file by file (84/84 SHA-256 matches); it was not used to build anything.
- `data_check.json`: 28 images (children 01–14, left and right eye), all 999 × 960 RGB JPEG; both
  observers' 1-bit masks for all 28; mean vessel fraction 6.93 % (1stHO) vs 6.64 % (2ndHO). (The Kingston
  page says 1280 × 960 for the camera; the released images are 999 × 960.)
- `SOURCE.md`, `LICENSE-CC-BY-4.0.txt`, `official_files.sha256` and the screenshot are in the data folder.

## 3. Split and per-image bar (as fixed in section 0)

Split SHA-256 `0a290c86902e6c34c313541e3d24edd4fb33b8d8d871f10244feab55cb4c26fa`. Development children
01, 02, 03, 04, 06, 08, 09, 10, 12, 14 (20 images; shown to the agent as children A–J); hidden children
05, 07, 11, 13 (8 images). Second observer vs first on the hidden images (= the bar):

| Hidden case | Source | Bar: Dice ≥ | Bar: clDice ≥ |
|---|---|---|---|
| hid_6429 | Image_05L | 0.7545 | 0.8464 |
| hid_7747 | Image_05R | 0.7814 | 0.8663 |
| hid_9702 | Image_07L | 0.7721 | 0.8126 |
| hid_3693 | Image_07R | 0.7513 | 0.8189 |
| hid_4179 | Image_11L | 0.8268 | 0.8668 |
| hid_7089 | Image_11R | 0.8080 | 0.8762 |
| hid_8323 | Image_13L | 0.7883 | 0.8357 |
| hid_1625 | Image_13R | 0.7810 | 0.8185 |

Development images: second-observer Dice 0.739–0.817 (mean 0.774), clDice 0.760–0.888 (mean 0.832);
these ranges are stated in the agent's instruction, with per-image values in `dev/cases.csv`.

## 4. Comparators

All runs through `suite.core.runner` (grader clock, `run.sh` contract), 4 threads, cores 0–3 pinned with
`taskset`, on teal (WSL2); per-image grades by the family grader. `run_comparators.py`; outputs in
`DATA_ROOT/specialist/`.

**Specialist: small U-Net** (`specialist/train.py`, `specialist/pipeline/`). 4 levels, base width 16,
1.94 M parameters (the module docstring says ~0.5 M; it is wrong, and was left as pushed so the repo and
the hosted task stay byte-identical), BatchNorm, BCE + soft Dice, AdamW/OneCycle, 4,000 iterations of 16
random 256 × 256 patches with flips, rotations and intensity jitter. Trained on 8 development children
(16 images); the other 2 development children (12, 14) chose the checkpoint (iteration 2,750) and the
threshold (0.45) by mean of Dice and clDice. Hidden images were never read in training. RTX 3060 (shared;
about 600 MB used by others at the start), 375 s. Inference on CPU, full image, no test-time augmentation:
**3.1–3.5 s per image** on 4 threads, so the 60 s limit is 17 × the specialist's time (≥ 5 ×, as required).

**Simple comparator: Frangi** (`classical/`). CLAHE on the green channel, `skimage.filters.frangi`
(σ 1–4, dark ridges), a red-channel field-of-view mask, threshold and minimum component size fitted on
the 20 development images by mean of Dice and clDice. First grid (threshold 0.04–0.40) put the best at its
lower edge (0.06), so the grid was extended down (0.01–0.12, minimum size 0/100/300) before any hidden run;
best 0.04 and 300 px (development Dice 0.464, clDice 0.381). About 2 s per image.

Hidden images (8):

| System | Acceptable | Mean Dice | Mean clDice | Wall s per image |
|---|---|---|---|---|
| Second observer (reference point) | 8/8 (by construction, zero margin) | 0.783 | 0.843 | – |
| **U-Net specialist** | **6/8** | **0.837** | **0.855** | 3.1–3.5 |
| Frangi | 0/8 | 0.471 | 0.375 | 2.0–2.1 |

Development images (20; the U-Net trained on 16 of them): U-Net 18/20 acceptable, Dice 0.854, clDice
0.865; Frangi 0/20, 0.464, 0.381; second observer 20/20, 0.774, 0.832.

U-Net per hidden image (Dice / clDice; margin to bar):

| Case | Dice | clDice | Dice margin | clDice margin | Acceptable |
|---|---|---|---|---|---|
| hid_6429 | 0.8565 | 0.8832 | +0.102 | +0.037 | yes |
| hid_7747 | 0.8678 | 0.8711 | +0.086 | +0.005 | yes |
| hid_9702 | 0.8524 | 0.8480 | +0.080 | +0.035 | yes |
| hid_3693 | 0.8553 | 0.8350 | +0.104 | +0.016 | yes |
| hid_4179 | 0.8328 | 0.8657 | +0.006 | −0.001 | no (clDice) |
| hid_7089 | 0.8314 | 0.8796 | +0.023 | +0.003 | yes |
| hid_8323 | 0.8123 | 0.8496 | +0.024 | +0.014 | yes |
| hid_1625 | 0.7907 | 0.8099 | +0.010 | −0.009 | no (clDice) |

**Family rule:** the specialist passes 6 of 8 (≥ 4), so **the family is scored**. The bar binds on clDice
more than on Dice: the U-Net beats the second observer's Dice on all 8 images, and the two failures are
clDice shortfalls of 0.001 and 0.009 (missed thin vessels). With S = the 6 images the specialist passes, the
gap rule needs an agent to fail at least one of them with a pass-difference interval entirely below 0.

## 5. Task export

- Exporter: `suite.core.export.export_task` with absolute paths (`exp/seg_vessel/export_vessel.py`, a
  driver like `scripts/export_suite_tasks.py`; that script's family list was not edited). No `suite/core`
  change was needed.
- `dist/suite-tasks-vessel-v1/seg_vessel/seg-vessel-build-0001/`. Agent side: `environment/data/` =
  README, 20 development cases (`image.jpg`, `label_1stHO.png`, `label_2ndHO.png`), `dev/cases.csv`, CC BY 4.0
  licence, `ATTRIBUTION.md` (2.0 MB). Verifier: 8 hidden inputs, 1stHO labels and `bar.json`, stored
  U-Net masks and CPU runtimes, vendored core and family grader (1.0 MB). `solution/` = the U-Net
  specialist pipeline (7.8 MB weights trained on development images only), `oracle_expected_reward` 0.75.
- Image: `python:3.12-slim`, `/opt/benchmark-venv` with numpy 2.1.3, scipy 1.14.1, nibabel 5.3.2,
  SimpleITK 2.4.0, scikit-image 0.24.0, scikit-learn 1.5.2, Pillow 11.0.0, pandas 2.2.3, torch 2.15.0+cpu.
  4 CPUs, 8 GB, agent session 3600 s, verifier timeout 1020 s, agent network `api.anthropic.com` only,
  separate no-network verifier.
- Checks: `check_no_leak` (in the exporter) passed. Extra leak check against every hidden image, hidden
  1stHO and 2ndHO file (by SHA-256 and digest text), the hidden second-observer masks and the hidden bar
  values (4 decimals in any text file): **no hit** in `environment/`, `solution/` or `instruction.md`;
  no hidden source name appears. Second-observer masks of hidden images are not in the export at all.
  `scripts/validate_exports.py`: "Validated and packed 1 tasks". Pinned Tracker `TaskConfig`: no problems,
  separate verifier, allowlist `api.anthropic.com`.
- Local run of the exported `tests/grade.py` on `solution/pipeline` (family env on PATH): reward
  **0.75**, ran/valid/within_time 1, quality 0.837, vs_specialist 1.0, median 2.76 s per image; identical
  per-image values to the specialist run.
- Tests: `tests/suite/test_seg_vessel.py`, 23 tests on synthetic vessel trees (Dice/clDice definitions,
  hand-computed clDice, width-insensitivity of clDice, the PIL 1-bit crash case, bar equality, valid
  encodings, bad masks, symlinked mask, core grading end to end: perfect, empty, timeout, one invalid
  image). Full `tests/suite`: **275 passed, 1 skipped** (the existing openpyxl skip).
- One grader bug found and fixed before export: PIL mode-1 images become numpy bool arrays holding
  0/255 bytes, which segfaults `skimage` skeletonize; the grader now converts mode 1 to L and canonicalises
  booleans before skeletonizing. The bar values were computed from canonical arrays and reproduce exactly.

## 6. Hosted: push and oracle

```
.venv-valkyrie/bin/valkyrie dataset push suite/vessel-v1 dist/suite-tasks-vessel-v1 --tag v1 --concurrency 2
  ✓ Uploaded seg-vessel-build-0001 (10,574,417 bytes)
  ✓ Published suite/vessel-v1@1: 1 task(s), 1 uploaded. Tags: latest, v1.
.venv-valkyrie/bin/valkyrie run start --agent oracle --dataset suite/vessel-v1@v1 --provider modal --concurrency 1 -l seg-vessel-oracle1
```

The first oracle start was refused ("Your organization has 10 active runs and may run at most 10 at
once"); it was retried every 90 s and started at 01:25 EST. No one else's run was stopped.

Oracle run **`7d02411d-dd46-437a-bcc6-9d72b33a5323`**: FINISHED, verifier mode `separate`, exit 0.
Rewards **reward 0.75**, ran 1, valid 1, within_time 1, clinically_acceptable 0.75, quality 0.837396,
vs_specialist 1.0, equal to `oracle_expected_reward` 0.75. Per-image pass/fail identical to the local
run (fails hid_1625 and hid_4179 on clDice); quality differs from the local 0.837395 in the sixth decimal
(CPU numerics). Hosted CPU time 1.8–2.1 s per image (limit 60 s). Image build 57 s, evaluation 55 s.
Evidence: `exp/seg_vessel/hosted/oracle/`.

## 7. Hosted agent runs (one attempt per model; nothing rerun)

```
.venv-valkyrie/bin/valkyrie run start --agent claude_code_noweb-v1.0.0 --dataset suite/vessel-v1@v1 --provider modal \
  --model anthropic/claude-opus-5-5 -s ANTHROPIC_API_KEY anthropic-api-key --concurrency 1 -l seg-vessel-agents1-opus
(same with anthropic/claude-sonnet-5-5, label seg-vessel-agents1-sonnet)
```

Started after the oracle was confirmed (01:30 EST, after retrying for an org slot). Default effort, $8 cap,
session 3600 s. No infrastructure failure; both ended on their own.

| Run | Run id | Model | reward | ran / valid / in time | Acceptable | Mean Dice | Mean clDice | Pipeline s/image (hosted) | Session used | Turns | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Opus | `123e97b9-acda-4504-96cb-3c46e935a277` | claude-opus-5-5 | **0.625** | 1/1/1 | 5/8 | 0.827 | 0.854 | 5.4–5.6 | 2260 s (63 %) | 19 | $0.696 |
| Sonnet | `8c5fa3ce-06cd-42a6-885b-42522e3ae7a2` | claude-sonnet-5-5 | **0.500** | 1/1/1 | 4/8 | 0.824 | 0.841 | 2.6–2.9 | 2152 s (60 %) | 32 | $0.315 |
| Specialist U-Net | stored outputs | – | (0.75 if on time) | – | 6/8 | 0.837 | 0.855 | 1.8–2.1 (oracle run) | – | – | – |
| Second observer | – | – | – | – | 8/8 (on the bar) | 0.783 | 0.843 | – | – | – | – |
| Frangi | – | – | – | – | 0/8 | 0.471 | 0.375 | – | – | – | – |

vs_specialist: Opus 0.987, Sonnet 0.984. Total API cost **$1.01**. Zero web search or fetch requests in
both. Raw values are from a local regrade of each carried `/workspace/output/pipeline` with the task's own
`tests/grade.py`, the pipeline in the pilot's no-network bubblewrap shim with the family env bound at
`/opt/benchmark-venv` (`exp/seg_vessel/analyse.py`); all seven reward keys match the hosted values
exactly for both runs (the regrade env has torch 2.15.0+cu132 run on CPU, not the `+cpu` wheel).

### Per hidden image (Dice / clDice; bar = second observer; ✓ = acceptable)

| Case | Bar | Specialist | Opus | Sonnet |
|---|---|---|---|---|
| hid_6429 | 0.755 / 0.846 | 0.857 / 0.883 ✓ | 0.859 / 0.892 ✓ | 0.850 / 0.882 ✓ |
| hid_7747 | 0.781 / 0.866 | 0.868 / 0.871 ✓ | 0.859 / 0.868 ✓ | 0.854 / 0.859 ✗ clDice |
| hid_9702 | 0.772 / 0.813 | 0.852 / 0.848 ✓ | 0.841 / 0.842 ✓ | 0.828 / 0.818 ✓ |
| hid_3693 | 0.751 / 0.819 | 0.855 / 0.835 ✓ | 0.846 / 0.834 ✓ | 0.839 / 0.820 ✓ |
| hid_4179 | 0.827 / 0.867 | 0.833 / 0.866 ✗ clDice | 0.806 / 0.855 ✗ both | 0.821 / 0.855 ✗ both |
| hid_7089 | 0.808 / 0.876 | 0.831 / 0.880 ✓ | 0.809 / 0.869 ✗ clDice | 0.818 / 0.861 ✗ clDice |
| hid_8323 | 0.788 / 0.836 | 0.812 / 0.850 ✓ | 0.809 / 0.855 ✓ | 0.808 / 0.843 ✓ |
| hid_1625 | 0.781 / 0.8185 | 0.791 / 0.810 ✗ clDice | 0.785 / 0.8185 ✗ clDice (0.818499 vs 0.818523) | 0.778 / 0.787 ✗ both |

Figure-ready CSV (one row per image × system: Dice, clDice, bars, margins, acceptable, seconds):
`exp/seg_vessel/seg_vessel_per_image.csv`.

### Gap verdicts (rule in section 0)

S = the 6 images the specialist passes (hid_3693, 6429, 7089, 7747, 8323, 9702).

| Attempt | Agent passes in S | Pass diff (95 % CI) | Dice diff on S (95 % CI) | clDice diff on S (95 % CI) | Verdict |
|---|---|---|---|---|---|
| Opus | 5/6 (fails hid_7089 on clDice by 0.007) | −0.17 (−0.50 to 0.00) | −0.009 (−0.015 to −0.003) | −0.001 (−0.006 to +0.004) | **no gap shown** |
| Sonnet | 4/6 (fails hid_7089, hid_7747 on clDice by 0.016 and 0.008) | −0.33 (−0.67 to 0.00) | −0.013 (−0.019 to −0.009) | −0.014 (−0.022 to −0.007) | **no gap shown** (interval touches 0) |

Both agents sit just below a 30-minute specialist on Dice (by about 0.01) and well above the second human
observer on Dice; with 6 images in S the pass-difference interval cannot exclude 0 unless an agent fails at
least 3 of them. Every failure is a clDice (thin-vessel completeness) shortfall of under 0.02.

### What the agents did (from the traces)

- **Opus** (19 turns): wrote a classical fallback first (`baseline.py`), then a small U-Net on RGB plus
  CLAHE green, trained on CPU for about 35 minutes on 8 children with children I and J held out, then tuned
  the threshold and flip averaging on those 4 images against the per-image bar. It measured the right
  thing: "Dice clears the bar on all 4 held-out images, but clDice falls just short ... Lower thresholds
  help clDice". It also tested `run.sh` "in a stripped environment with an empty `HOME`". Its own forecast
  was accurate: "Expect a similar pass rate on the hidden set, but not all 8" (3/4 held out; 5/8 hidden).
  Limitation it stated itself: "There wasn't time to retrain on all 20 images afterwards"; it stopped
  with 22 minutes of session left.
- **Sonnet** (32 turns): first a gradient-boosting pixel classifier ("averaged Dice about 0.72 under
  child-grouped cross-validation, and no image passed the bar, so I dropped it"), then a U-Net on all 20
  images for about 1,300 s (~850 iterations): "That is short, so it is probably undertrained". It never
  validated the final model: "I never ran a full held-out check on the final model ... I did not measure
  clDice or the per-image bar." It ended at 36 minutes with 24 minutes unused, saying "I don't have a
  reliable accuracy estimate". Unused files (`model.pkl`, `fit.py`) left in the pipeline.
- Neither model asked for or used web tools; both pipelines are valid, offline and well inside 60 s.

### Reading

This family is a **near-parity result, not a demonstrated gap**: both frontier agents built learned
segmenters from 20 labelled images on CPU in under 40 minutes that beat the second human observer's Dice on
every hidden image, and reached the human bar on both measures on 5/8 (Opus) and 4/8 (Sonnet) images,
against 6/8 for a GPU-trained specialist. The failure mode is consistent: thin-vessel connectivity (clDice),
and early stopping with session time left (both used about 60 % of the session). One attempt per model;
attempt-to-attempt variation is not measured.

## 8. Limitations

- 8 hidden images from 4 children; one image moves the headline by 0.125. Fellow eyes are correlated.
- The bar is the second observer's own agreement on each image, with no tolerance; hid_1625 for Opus
  missed by 0.00002 clDice. A tolerance would have been a different rule; none was fixed in advance.
- Whole-image metrics (no FOV mask), as released; papers usually report inside an FOV.
- Literature numbers in section 1 are secondary (aggregator or citing paper) except clDice and Frangi.
- CHASE_DB1 is public and well known; the sandbox has no web access, and hidden labels never reach it.
- The specialist was trained on a GPU (375 s) while agents train on 4 CPUs within one hour; the
  comparison is of delivered pipelines, not of training budgets.
- No Docker on teal: the image was first built on Modal (57 s build, oracle run).
