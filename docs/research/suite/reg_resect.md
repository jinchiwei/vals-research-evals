# reg_resect: pre-operative MRI to intra-operative ultrasound registration (brain shift)

Worker: Claude Opus 5.5 (claude-opus-5-5), 2026-11-14, on teal. Code: `suite/families/reg_resect/`.
Tests: `tests/suite/test_reg_resect.py`. Data: `/home/jkwei/data/vals-suite/reg_resect/` (not in Git).

## Task

During glioma surgery the brain moves once the dura is opened, so neuronavigation on the
pre-operative MRI becomes wrong. The agent builds an offline pipeline (`run.sh INPUT_DIR OUTPUT_DIR`).
For each case it gets the contrast T1 and FLAIR MRI, the pre-resection 3D ultrasound and the MRI
landmark coordinates. It must return each landmark's position in the ultrasound, within **120 s per
case on 4 CPU cores**, with no network.

**Output format.** `landmarks_us.csv` with header `id,x,y,z` in RAS world mm, the same convention as
the input CSV and the NIfTI sform. I chose points rather than a transform because a transform file
adds two more places to go wrong: direction (fixed-to-moving or the reverse) and file convention
(ITK, ANTs or FSL). With points, the only convention left is RAS versus LPS, and the README states it
explicitly. A dense field (`displacement_ras.nii.gz`) is optional and is used only to report folding.
Agent brief: `suite/families/reg_resect/README_agent.md`.

## Data facts verified

- **Source and licence.** NIRD archive, doi:10.11582/2017.00004. Downloaded directly with no login.
  The record metadata gives `license_id: CC-BY-4.0` and `access_rights: public`. The CC BY 4.0 legal
  code and the record JSON/HTML are saved under `meta/`. All 162 fetched files matched the archive's
  MD5 fixity values. 1028 MB was fetched (NIfTI T1, FLAIR, US-before and all tags, 22 patients);
  MINC copies and the during/after-resection ultrasound were not fetched. See `SOURCE.md`.
- **Format.** NIfTI-1, `sform_code` 1, `qform_code` 0, RAS axis codes. MRI is mostly 1 mm isotropic.
  Cases 2, 14 and 15 have a 0.5 × 0.5 × 1 mm T1 and a 1.02 mm FLAIR. Ultrasound is isotropic
  0.14–0.29 mm, stored as float64 or float32, and is 0 outside the sweep.
- **Landmarks.** MINC `.tag` files, rows `x1 y1 z1 x2 y2 z2 ""`. For `CaseN-MRI-beforeUS.tag` the
  first triple is MRI and the second is pre-resection US, in RAS world mm. There are 15–16 per case.
  22 of 23 patients have them (Case11 does not), which matches the CuRIOUS page's "22 of 23".
  Landmarks were placed on FLAIR (CuRIOUS 2018 paper). T1 and FLAIR share one world frame:
  mutual information peaks at the identity, checked on Cases 1, 2, 5 and 14.
- **Coordinate convention, verified.** Treating tags as RAS and converting to LPS for SimpleITK
  puts **100 %** of the US landmarks on non-zero US voxels and 100 % of the MRI landmarks inside the
  FLAIR, in all 22 cases. Treating them as LPS without the flip puts 0 % inside in 16 of 22 cases.
- **Initial error reproduced exactly.** The mean of the 22 per-case mean landmark distances is
  **5.37 ± 4.27 mm** (pooled over 338 landmarks: 5.39 ± 4.33). The published RESECT training value
  is 5.37 ± 4.27 mm (Xiao et al. 2020, CuRIOUS2018, Table III). Per case it ranges from 1.10 mm
  (Case24) to 19.68 mm (Case12). The published per-case table (RESECT paper, Med Phys 2017) is
  paywalled and was not read, so the per-case values are verified only through the aggregate.
- **Header leak.** NIfTI `descrip` contained the RESECT path, e.g. "mnc2nii Case12/MRI/...". It is
  cleared in the staged copies. Voxel data, dtype and affine are unchanged.

## Split (seed 20261114; `staged/split.json` has the rule, mapping and SHA-256 of every file)

Rule, fixed before any result:
1. Exclude cases whose initial mTRE is ≤ 2.0 mm, where a do-nothing answer would already pass:
   Case1, Case7 and Case24.
2. Permute the remaining 19 with `numpy.random.default_rng(20261114)`.
3. Take the first 6 as hidden, the next 4 as development and keep 9 in reserve. Reserve cases are
   never shown and never used.

| Set | Token (RESECT patient) | Initial mTRE mm |
|---|---|---|
| dev | c6eae9 (Case13), c4fe8a (Case8), c0c472 (Case26), ca3825 (Case14) | 4.57, 2.63, 2.83, 3.03 (mean 3.27) |
| hidden | ce4785 (Case23), cb06b4 (Case21), c18b03 (Case17), cdd96a (Case25), c65c1b (Case2), c57eed (Case16) | mean 6.18 ± 2.30 |
| reserve | Case5, 3, 27, 19, 4, 15, 12, 6, 18 | not used |

The draw made development easier than hidden (initial 3.27 vs 6.18 mm). I recorded this and did not
re-draw.

## Thresholds and limits (sources)

- **Clinically acceptable** (per case): mean TRE < **2.0 mm**, and lower than the initial error.
  Source: Gerard et al., Front Oncol 2021;10:618837, citing Prada et al.: navigation accuracy
  restored "to below a critical threshold of 2 mm". AAPM TG-132 (mean TRE < 2 mm, via Latifi et
  al. 2018) agrees. Both are taken from `metrics-review.md` §1(b). Not tuned.
- **Time:** 120 s per case, 4 CPUs (DESIGN.md). The metrics review gives about 20 min as the
  intra-operative upper bound. 120 s is tighter, and is in line with the CuRIOUS runtimes of
  20–115 s (and 450 s for cDRAMMS).
- **Quality** in [0, 1]: exp(−mTRE / 2 mm).
- **Validity:** strict CSV; exactly the input ids; finite values; every point within 10 mm of the
  US field of view (voxels > 0), since every reference landmark lies inside it.
- **Reported in metrics.json:** initial mTRE, improvement in mm and as a ratio, median and maximum
  TRE, per-landmark TRE, fraction of landmarks under 2 mm, and the folding fraction when a field is
  given. Runtime comes from the core runner's monotonic clock.

## Specialist baseline

The baseline is **MIND-feature rigid registration**: `pipeline_src/mind_reg.py`, using only numpy,
scipy and SimpleITK, so it runs in the build-tier image.
1. Resample the US and FLAIR onto a 1 mm grid aligned with the US. Use the navigation alignment as
   the start, and an eroded non-zero US mask.
2. Compute six-neighbourhood MIND descriptors on both images.
3. Run an exhaustive masked-SSD translation search over ±16 mm, using FFT correlation.
4. Refine all 6 rigid parameters with Powell.
5. Map the MRI landmarks with the inverse transform.

The frozen config is `{"spacing": 1.0, "pre_sigma_mri": 1.0, "search_mm": 16}`. I chose ±16 mm
a priori from the RESECT training range (up to about 20 mm), not from hidden results.

**Tuning used development cases only** (`tune_dev.py`):

| Variant (dev mean mTRE; initial 3.27) | Result |
|---|---|
| Rigid Mattes MI, FLAIR gradient magnitude | 5.31, 0/4 pass |
| Rigid MI, FLAIR intensity | 9.55, 0/4 |
| Rigid MI, T1 gradient magnitude | 11.98, 0/4 (T1-intensity run did not finish) |
| MIND rigid, 1.5 mm grid (default) | 1.97, 2/4 |
| MIND, no rigid refinement | 2.05, 2/4 |
| MIND, T1 instead of FLAIR | 3.05, 1/4 |
| MIND, 1.0 mm grid ± small variants (erosion, sigma, search range) | 1.83–2.19 |

An earlier harness bug made three development cases silently fall back to MI. I found and fixed it
before freezing; the table shows the corrected runs.

**Frozen configuration, development cases** (per case; runtime measured on teal under heavy shared
load):

| Case | Initial mm | Specialist mm | Best possible rigid fit to landmarks (mm) | s |
|---|---|---|---|---|
| c0c472 | 2.83 | 1.35 | 1.18 | 12 |
| c4fe8a | 2.63 | 2.25 | 1.37 | 8 |
| c6eae9 | 4.57 | 2.32 | 1.03 | 16 |
| ca3825 | 3.03 | 1.47 | 1.03 | 12 |
| mean | 3.27 | **1.85** | 1.15 | |

**Hidden cases (aggregate, single run after freezing):**
- Initial mTRE 6.18 ± 2.30 mm; specialist **3.03 ± 2.71 mm** (median 1.91, range 1.37–8.38).
- **4 of 6 cases clinically acceptable** (reward 0.667); 5 of 6 improved.
- One case got worse, ending at 8.38 mm (a wrong local optimum).
- Runtime: 11–24 s per case on the first run and 7–13 s on the self-check rerun, against a 120 s
  limit. The results are deterministic: both runs give identical TREs.

**Context: published CuRIOUS2018 results.** These were on 10 different St Olav's test patients,
whose initial error was 6.38 ± 4.36 mm: ImFusion 1.57 ± 0.96 mm (20 s, GPU), DeedsSSC 1.87 ± 0.93
(25 s, CPU), cDRAMMS 2.18 ± 1.23 (450 s), NiftyReg 3.21 ± 3.57 (115 s). Our baseline's mean is in
the NiftyReg range and its median is at DeedsSSC level. It is rigid only, while the top methods
are deformable (DeedsSSC uses MIND-SSC discrete optimisation).

**Does the family have a "specialist passes" bar?** Partly. The specialist clears 2 mm on 4 of 6
hidden cases, but its mean over hidden cases (3.03 mm) does not clear 2 mm. A frontier-gap claim is
therefore valid per case: on the 4 cases the specialist passes, an agent that fails shows a gap. At
the task level it is "specialist 0.67 vs agent X", not pass/fail. A deformable stage (MIND/deeds-
style) would very likely raise the bar. It was not attempted, for time.

## Grader self-check (local, `build.py`; core `grading.grade_task`, hidden cases)

| Pipeline | reward | ran | valid | within_time | acceptable | quality |
|---|---|---|---|---|---|---|
| oracle (embedded hidden references) | **1.0** | 1 | 1 | 1 | 1 | 1.0 |
| identity (do nothing) | 0.0 | 1 | 1 | 1 | 0 | 0.070 (it reproduces the initial error) |
| lps (oracle answer written in ITK LPS) | 0.0 | 1 | **0** | 1 | 0 | 0 |
| slow (oracle answer after 25 s, limit set to 20 s) | 0.0 | 0 | 0 | **0** | 0 | 0 |
| specialist | 0.667 | 1 | 1 | 1 | 0.667 | 0.331 |

The first validity rule was the US volume's axis-aligned bounding box plus 10 mm. It caught only
3 of 6 LPS cases, because the volumes are oblique. The field-of-view distance rule catches all 6.
The test suite has 8 tests on synthetic fixtures (all pass in 3 s). They cover:
- a known shift giving exactly 0 and exactly 1 mm TRE;
- identity reproducing the initial error;
- the wrong frame, with an LPS hint in the reason;
- missing, extra, NaN and wrong-header outputs;
- row order;
- folding;
- the tag parser and the split rule;
- oracle = 1.0 and the timeout kill through the core runner.

## Export spec

`suite/families/reg_resect/spec.py` defines what goes where:
- **Agent image:** README, 4 development cases with both landmark sets, and LICENSE-DATA.md.
- **`tests/` only:** 6 hidden cases (`input/` and `reference/`), specialist outputs with
  `runtime.json`, `task_config.json`, and the grader modules.
- **`solution/`:** the specialist pipeline only. It contains no hidden data. The oracle pipeline
  embeds hidden references and must never be shipped.

`spec.build_spec(work_dir, specialist_results_dir=...)` returns a `suite.core.export.FamilySpec`.
Exported with:

```bash
PYTHONPATH=. ~/miniconda3/envs/vals-suite-reg_resect/bin/python -c "from suite.families.reg_resect.spec import build_spec; \
from suite.core.export import export_task; print(export_task(build_spec('/home/jkwei/data/vals-suite/reg_resect/export_work', \
specialist_results_dir='/home/jkwei/data/vals-suite/reg_resect/build_20261114/tests/specialist'), '/home/jkwei/data/vals-suite/reg_resect/dist'))"
```

The output is `/home/jkwei/data/vals-suite/reg_resect/dist/reg-resect-build-0001/`: `environment/` is
202 MB, `tests/` is 285 MB, and `solution/` is 32 KB. Checks run on it:
- The exporter's leak check (bytes, gunzipped content and SHA-256) passed.
- `exp/suite-platform-probe/check_taskconfig.py` reports no problems: separate verifier, verifier
  no-network, agent allowlist `api.anthropic.com`, 4 CPUs, 16 GB, artifact `/workspace/output`.
- A dry run of the exported `tests/grade.py` on `solution/pipeline` gives reward 0.667 with the same
  per-case TREs as above, at 5.5–11 s per case.

The Harbor oracle (`solution/`) is the specialist, so a hosted oracle run should score 0.667, not 1.0.
The 1.0 oracle is the local lookup pipeline. `build.py` separately writes the self-check `tests/` tree
and the specialist outputs, under `build_20261114/`.

**Size estimate.** The agent image is about 1.0 GB:
- `python:3.12-slim`: about 130 MB (estimate);
- pinned wheels: 664 MB as installed here, of which SimpleITK alone is 263 MB;
- development data: 202 MB.

The verifier upload is about 285 MB. This exceeds the survey's 200 MB target, mainly because of
SimpleITK. Ways to reduce it, not done:
- drop T1 (landmarks are on FLAIR), which saves about 60 MB;
- convert US float64 to float32;
- crop the US to the field of view.

## Limitations and unverified

- Per-case initial errors are verified only through the published aggregate (exact match). The
  RESECT per-case table is paywalled.
- Six hidden cases give coarse fractions (steps of 1/6). Runtimes were measured on a shared,
  heavily loaded host (load average above 12), not on Modal. The specialist time is about 10× below
  the limit, so the margin is large.
- RESECT is public and well known; it is a contamination risk. IDs are re-drawn and headers
  cleared, but the images themselves are original.
- A later study (cited in the dataset survey) reports a few landmarks with possible localisation
  errors; they are not removed.
- The specialist is rigid only. A deformable stage was not attempted, and the reserve cases were
  not used as an extra check.
- I did not run `scripts/validate_exports.py` (SDK packing), build a Docker image or do a hosted run.
  The image size is an estimate.
- The MI-based `pipeline_src/register.py` is kept only as the documented failed alternative.
