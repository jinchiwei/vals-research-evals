# Clinically meaningful metrics for the medical-agent suite: literature review

Prepared by a research worker running Claude Opus 5.5 (model ID `claude-opus-5-5`), 2026-11-14.

## Scope and method

This review justifies the scoring choices for a suite in which a coding agent receives public medical data and must return a clinical-grade deliverable (a segmentation mask, a registration transform, calibrated probabilities or a measurement table), which a hidden grader compares against a reference standard and a specialist baseline. It extends `docs/research/evaluation-literature.md` (agent-benchmark design, contamination, grading isolation) and `docs/research/pcnsl-literature.md` (lymphoma data and endpoints). It does not repeat them; it covers what those files do not: which clinical metric to compute per task type, what makes a submission invalid, how clinical time limits enter the score, and how to compare scores on small test sets.

Every reference in the main text was checked in this session against Crossref, Europe PMC, arXiv, PubMed Central or the publisher page. Bibliographic data (authors, year, venue, volume, pages, DOI) come from Crossref or Europe PMC records. Numbers and thresholds are quoted only where I read them in the abstract or full text, and the source is named beside each one. Statements marked "Recommendation" are my design proposals for the suite, not claims from the literature. Items I could not verify are listed separately at the end and are not used in the argument.

Abbreviations used throughout: DSC, Dice similarity coefficient; NSD, normalized surface distance (also called surface Dice); HD95, 95th-percentile Hausdorff distance; TRE, target registration error; AUROC, area under the receiver operating characteristic curve; CI, confidence interval; OOD, out of distribution; GPU, graphics processing unit.

---

## 1. Metrics per task type

### (a) Semantic and lesion segmentation

**What the consensus says.** Metrics Reloaded, a Delphi consensus of a large international consortium, chooses metrics from a "problem fingerprint" that records the domain interest, target structure properties, dataset and output type [1]. For semantic segmentation it recommends an overlap metric (DSC or intersection over union) by default "unless the target structures are consistently small, relative to the grid size ... and the reference may be noisy", and states: "Our general recommendation is therefore to complement an overlap-based metric with a boundary-based metric" [1]. NSD is the default boundary metric when annotation imprecision should be tolerated [1]. NSD was introduced to "quantify the deviation between organ at risk surface contours rather than volumes, better reflecting the clinical task of correcting errors in automated organ segmentations" [3], which is the clinical argument for a boundary term: a clinician edits contours, so the cost of an error scales with how much surface must be redrawn, within a tolerance in millimetres.

**Lesion-wise detection.** When a case contains several lesions, a single per-case DSC lets one large lesion hide several missed small ones. Metrics Reloaded treats this as an instance segmentation or object detection problem: an F-beta score on matched objects is primary, complemented by average precision or a free-response ROC score when continuous scores exist, and panoptic quality is an alternative that "combines the assessment of overall detection performance and segmentation quality" [1]. BraTS-METS 2023 shows a practical implementation: lesions are matched by connected components, scores are computed per lesion, and missed or spurious lesions receive "a score of 0 for Dice and a fixed penalty of 374 for HD95" [7]. Lesions below 2 voxels were excluded by expert-panel decision [7].

**Volume error.** When the clinical use is a volume (tumour burden, response assessment), report the signed and absolute volume difference in millilitres in addition to overlap, and assess agreement with the Bland and Altman approach (mean difference and limits of agreement) rather than correlation [69]. Overlap metrics "do not take the correctness of an object's boundaries into account", and structure volume matters for some uses [2].

**Pitfalls, each from the pitfalls companion paper [2] unless noted.**
- Small structures: "single-pixel differences may hugely impact the metric scores", so DSC on small lesions is noisy and harsh [2]. Metrics Reloaded likewise notes overlap metrics have "limitations when dealing with small structures or high size variability" [1].
- Empty reference or empty prediction: both can cause "division by zero errors" [2]. Metrics Reloaded gives explicit aggregation rules for empty references [1]. Recommendation: define the score for empty cases before the run (for example, an empty reference with an empty prediction scores 1 for DSC and 0 false positives; an empty reference with any predicted lesion counts as a false-positive detection), never drop such cases, and report them separately.
- Outliers: "Spatial outliers in the reference may have a huge impact on distance-based metrics such as the Hausdorff Distance (HD)"; HD95 was designed for this [2].
- Aggregation: "a common mistake is to ignore the hierarchical data structure", for example computing a global pixel-pooled DSC so that "errors in small structures may be suppressed by correctly segmented larger structures in other images" [2]. Compute per case, then aggregate; respect patient and site clustering [1].
- Baselines: nnU-Net, a self-configuring U-Net pipeline, is the established segmentation comparator [5]. A 2024 re-benchmark found that "many of these recent claims fail to hold up when scrutinized for common validation shortcomings, such as the use of inadequate baselines, insufficient datasets, and neglected computational resources" [6]. A segmentation task that does not compare against a properly trained nnU-Net cannot claim specialist parity.

Distance metrics must be computed in physical space using the voxel spacing of the reference image; Taha and Hanbury's open tool and review catalogue the definitions and their implementation choices [4].

### (b) Image registration, including intraoperative and multimodal

**Primary: TRE on landmarks in millimetres.** Fitzpatrick and West state that "for most registration tasks, the most important error measure is target registration error (TRE)", the post-registration distance between corresponding points not used to compute the transform [9]. Rohlfing showed that image similarity and whole-tissue overlap can rate grossly wrong transformations as good; only overlap of small, localized anatomical labels separated accurate from inaccurate registrations, and he argues similarity and overlap should not be reported as evidence of accuracy [10]. A registration benchmark therefore needs expert landmarks (or small local labels) as its reference, not intensity similarity.

**Practice in Learn2Reg.** Learn2Reg evaluated robustness, accuracy, plausibility and runtime across brain, abdomen and thorax tasks with ultrasound, CT and MR [8]. Its metrics were DSC on anatomical labels, HD95 in millimetres, TRE in millimetres on landmarks, robustness variants based on the 30th percentile (DSC30, TRE30), and the standard deviation of the log Jacobian determinant of the displacement field as a plausibility (smoothness) measure [8]. Methods were ranked per metric by pairwise Wilcoxon signed-rank tests (p < 0.05), converted to rank scores, and combined by geometric mean; runtime was one of those metrics, measured from loading the first scan to writing the displacement field, on fixed hardware (Xeon Silver 4210R CPU and Quadro RTX 8000 GPU) for containerised submissions [8]. The authors note their design "did not consider any computational constraints (GPU memory, runtime on CPU)" [8], and they argue conventional methods need not be much slower than deep learning [8].

**Plausibility.** A deformation with folds (negative Jacobian determinant) is physically impossible for tissue. Recommendation: make "no folding beyond a small, pre-declared fraction of voxels inside the body mask" a validity gate and report the standard deviation of the log Jacobian as a secondary score, as Learn2Reg did [8]. I did not find a published numeric folding threshold to cite; the gate value is a design choice.

**Intraoperative brain shift.** CuRIOUS2018 benchmarked MRI-to-intraoperative-ultrasound registration for brain-shift correction, training on the public RESECT database and ranking six methods on 10 held-out cases by landmark TRE [11][12]. Brain shift varies widely by intervention and quantification method [13]. A 2021 update reviewing intraoperative ultrasound methods tabulates mean pre-resection shifts of about 6 to 8 mm in the studies it summarises, lists reported intraoperative-ultrasound-to-MRI registration errors from about 0.9 mm to about 4 mm, and cites Prada et al. as restoring navigation accuracy "to below a critical threshold of 2 mm" [14]. The same review notes that long computation times were the "main drawback" of some methods because they are "not conducive to clinical workflow", but it gives no numeric runtime limit [14].

**Radiotherapy (image-guided radiotherapy, IGRT).** The AAPM Task Group 132 report is the standard for registration quality assurance in radiotherapy [15]. As summarised by Latifi et al., it recommends for deformable registration a mean TRE below 2 mm and a maximum below 5 mm, a strict criterion of half a voxel for rigid registration in phantom tests, and Dice in the 0.8 to 0.9 range as acceptable contour agreement [16]. I could not open the TG-132 text itself, so these thresholds are cited through Latifi et al.

**Recommendation for the suite.** Headline: mean landmark TRE in millimetres, with the initial (unregistered) TRE and a classical comparator (for example ANTs SyN) on the same pairs. Gates: transform must be in physical (world) coordinates consistent with the image headers, must load and apply to the moving image, and must not fold beyond the declared fraction. Constraint: a per-task wall-clock budget matched to the clinical use (see section 1g).

### (c) Diagnostic classification

**Discrimination is not enough.** AUROC measures ranking only. Van Calster et al. argue poorly calibrated models can mislead decisions and that a well-calibrated model with lower AUROC can be more useful than a better-discriminating but miscalibrated one [17]. Modern deep networks are often miscalibrated [22].

**Calibration.** Van Calster et al. define four levels: mean, weak (calibration intercept and slope), moderate (event rate equals predicted risk across the range, assessed by a calibration curve) and strong; they prove moderate calibration "guarantees nonharmful decision making" and recommend development and validation focus on it, while noting that "a flexible assessment of calibration in small validation data sets is problematic" [18]. Metrics Reloaded adds that calibration metrics should be included when probabilities are used, favours proper scoring rules such as the Brier score, and lists calibration slope, the expected calibration index and the observed-to-expected ratio [1]. The pitfalls paper warns that on small test sets common calibration metrics "either underestimate or overestimate the true calibration error" [2].

**Operating points.** Clinical use happens at a threshold. Recommendation: pre-specify the operating point from the clinical role (for a rule-out triage tool, sensitivity fixed at a clinically chosen level; for a confirmatory tool, specificity fixed), then score the other quantity at that point, with a CI. Leibig et al. illustrate this framing: they report results against "85% sensitivity and 80% specificity as recommended by the NHS" for diabetic retinopathy screening [25]. Metrics Reloaded recommends expected cost when misclassification costs are unequal [1].

**Decision-curve net benefit.** Decision curve analysis computes net benefit across threshold probabilities, where the threshold expresses how a patient or clinician weighs false positives against false negatives [19]. Net benefit at threshold p_t is TP/n − (FP/n)·p_t/(1−p_t). Vickers, Van Calster and Steyerberg recommend net-benefit approaches over AUROC alone for judging whether a model, marker or test should be used [20].

**Prevalence shift.** AUROC is prevalence-independent; predictive values, accuracy and calibration are not [1]. Godau et al. show that prevalence differences between development and deployment affect calibration, decision thresholds and validation estimates, and propose re-calibrating with an estimated deployment prevalence [23]. Under imbalance, precision-recall analysis is more informative than ROC [21]. Recommendation: when the test set prevalence differs from the target clinical setting, report predictive values and net benefit at the target prevalence, and say which prevalence was assumed.

**Statistics.** For comparing AUROCs on the same cases, use a paired method such as DeLong's test [24] or a paired bootstrap.

### (d) Tabular clinical risk prediction

**Reporting standard.** TRIPOD+AI (27 items, superseding TRIPOD 2015) requires authors to "specify all measures and plots used (and their rationale) to evaluate model performance" with discrimination, calibration and clinical utility as examples (item 12e), to "report model performance estimates with confidence intervals", including for key subgroups (item 23a), to explain how the study size was arrived at (item 10), to describe missing-data handling (item 11) and fairness approaches (item 14), and to state data and code availability (items 18e, 18f) [26]. PROBAST+AI is the matching risk-of-bias and applicability tool [27]. The BMJ series on evaluating prediction models covers development through external validation [32].

**Why AUROC alone misleads.** A systematic review of 71 studies found 90% used AUROC for discrimination but "calibration was not addressed in 56 (79%) studies", and found no AUROC benefit of machine learning over logistic regression in comparisons at low risk of bias (difference in logit AUROC 0.00, 95% CI −0.18 to 0.18), whereas comparisons at high risk of bias favoured machine learning [30]. The external validation of the Epic Sepsis Model found a hospitalisation-level AUROC of 0.63, poor calibration, and that the model missed 67% of sepsis cases while alerting on 18% of all hospitalised patients [31]. An AUROC alone would not have shown the alert burden.

**Small samples and instability.** Riley et al. give sample-size criteria for developing prediction models [28]. Riley and Collins show that instability of individual risk estimates "is often considerable, and ultimately manifests itself as miscalibration of predictions in new data", and propose bootstrap prediction-instability and calibration-instability plots [29]. A benchmark built on a few hundred patients should therefore expect wide intervals on calibration and should not rank agents on small differences.

**Comparators.** Tree-based models remain state of the art on medium-sized tabular data (about 10,000 samples) [34]. TabPFN, a tabular foundation model, "outperforms all previous methods on datasets with up to 10,000 samples" and in 2.8 s beats "an ensemble of the strongest baselines tuned for 4 h" in classification [33]. Penalised logistic regression should remain a comparator because, at low risk of bias, it matches machine learning on discrimination [30].

**Recommendation.** Headline: a proper scoring rule (Brier score or log loss) or net benefit over a pre-specified clinical threshold range; secondaries: AUROC, calibration intercept and slope, a calibration curve, each with bootstrap CIs. Gates: one probability in [0, 1] per test patient, no use of outcome-derived columns.

### (e) Subgroup performance, fairness and shortcut learning

**Evidence that averages hide harm.**
- Underdiagnosis: chest X-ray classifiers trained on large public datasets under-diagnosed (labelled as healthy) under-served groups, with higher rates in intersectional subgroups such as Hispanic female patients [35]. A Matters Arising by Bernhardt, Jones and Glocker argued that potential sources of dataset bias complicate this investigation [71], which itself shows the subgroup metric and its test data must be defined carefully.
- Hidden stratification: models can perform well overall while missing a clinically important subset, such as a rare aggressive subtype; the effect appears in subsets with low prevalence, poor label quality, subtle features or spurious correlates [36].
- Site and acquisition shortcuts: pneumonia models identified the source hospital in 99.95% (NIH) and 99.98% (Mount Sinai) of radiographs, and because pneumonia prevalence was 34.2% at Mount Sinai versus 1.2% and 1.0% elsewhere, sorting by hospital alone gave an AUROC of 0.861 on pooled data [37]. COVID-19 radiograph classifiers relied on confounding factors and failed in new hospitals [38]. Gentian violet skin markings lowered a dermoscopy classifier's specificity from 84.1% to 45.8% [42].
- Protected attributes are encoded in images: deep models predict self-reported race from medical images across modalities, including under external validation [39]. Subgroup gaps in true- and false-positive rates were partly explained by population and prevalence differences between test subgroups, so gaps must be adjusted for these before being called bias [40]. Models that rely more on demographic shortcuts showed larger fairness gaps, and fairness achieved in one population did not reliably transfer to new hospitals [41].
- Challenges rarely report demographics; Garin et al. call for medical imaging competitions to report dataset demographics and evaluate for bias [44].

**Metrics.** Worst-group performance, the minimum of the metric over pre-defined groups, is the standard robustness target [43]. Recommendation: for every task with usable metadata (sex, age band, site or scanner, and race where available and appropriate), report the headline metric per group with CIs, the worst-group value and the largest gap, and for classification the false-negative rate per group (the underdiagnosis quantity in [35]). Hidden stratification is addressed by reporting performance on clinically defined subsets the reference team names in advance (for example small lesions, rare subtypes) [36]. Only score a gap when each group has enough cases for a meaningful interval; otherwise report it as descriptive.

**Shortcut probes.** Recommendation: add controlled tests that detect site or marker shortcuts, such as a test split from an unseen site, or paired images with and without an artefact as in [42]; score the drop.

### (f) Abstention, out-of-distribution input and image-quality failures

Kompa et al. argue that the ability to "say 'I'm not sure' or 'I don't know' when uncertain is a necessary capability to enable safe clinical deployment" and review abstention methods [45]. Selective classification trades coverage for risk and is evaluated with risk-coverage curves [47]. In diabetic retinopathy, referring the 0 to 20% most uncertain cases let models reach the NHS-recommended sensitivity and specificity [25]. For segmentation, Mehrtash et al. studied confidence calibration and predictive uncertainty for deep segmentation models [48].

Two cautions. First, abstention can worsen fairness: selective classification "can simultaneously magnify existing accuracy disparities between various groups" and increasing abstention can even lower accuracy for some groups [46]. Second, OOD detection in medical imaging is immature: the MOOD 2020 benchmark found that all submitted algorithms "show a high variance for different anomalies, making it yet hard to recommend them for clinical practice" [49].

**Recommendation.** Allow an explicit abstain or "not assessable" output only where the task defines it, charge each abstention a pre-declared cost (equivalent to sending the case to a human), cap total abstention, and score abstention per subgroup so that an agent cannot raise its score by abstaining on hard groups. Include a few deliberately corrupted or out-of-scope inputs (wrong modality, truncated volume, corrupted header) where the correct output is a refusal or a quality flag; score failure to flag as an error.

### (g) Runtime, compute and workflow constraints

**How challenges have scored runtime.**
- FLARE 2021 encouraged "fast inference speed, and low GPU memory consumption" alongside accuracy; the winner achieved "a 19× faster inference speed and reducing the GPU memory consumption by 60% with comparable accuracy" [50]. Its rules capped the container at 6 hours and 16 GB GPU memory for the 100-case test set, and stated that "both accuracy and efficiency will be evaluated for ranking" (challenge website, URL listed under [50]); the exact weighting was not given on that page. FLARE 2022 listed DSC, NSD, running time, area under the GPU memory-time curve and area under the CPU utilisation-time curve as metrics, and FLARE 2023 kept all but the CPU measure (organiser repository); the FLARE 2022 report appeared in The Lancet Digital Health [51].
- Learn2Reg included runtime as a ranked metric for containerised submissions on fixed hardware [8].

**What clinical sources say about time budgets.**
- Intraoperative pathology: a College of American Pathologists Q-Probes study of 32,868 frozen sections in 700 hospitals found that "ninety percent of FS procedures were completed within 20 minutes" and concluded that 90% of frozen sections can be turned around within 20 minutes from receipt to communication with the surgeon [54]. This is the best-documented benchmark I found for an intraoperative diagnostic answer.
- Intraoperative registration: the brain-shift literature treats long computation as incompatible with surgical workflow but gives no numeric limit [14]. Recommendation: set the budget from the 20-minute intraoperative turnaround norm [54] as an upper bound and justify anything tighter per task.
- Emergency stroke imaging: the AHA/ASA guideline sets a goal of brain imaging within 20 minutes of emergency-department arrival in at least half of candidates for thrombolysis or thrombectomy, and door-to-needle time within 60 minutes [53] (I verified this wording through AHA guideline summaries, not the full guideline text). An emergency triage tool that adds more than a few minutes therefore consumes a large share of the budget. Titano et al. showed that automated head-CT triage could "accelerate the time to diagnosis from minutes to seconds" [52].
- Screening and offline research use: I found no published numeric latency standard. These uses are throughput-bound (cases per hour, cost per case) rather than latency-bound.

**Recommendation.** Treat time as a gate first and a score second: a submission that exceeds the clinical budget for its use case fails that case (the answer would arrive too late to be used), and among on-time submissions report wall-clock time and peak memory on fixed hardware, as FLARE and Learn2Reg did. For an agent benchmark, measure the time to produce the deliverable for a new case, not the agent's total development time, and state both.

### (h) Statistics for small test sets

- Error bars are large: with 100 samples, cross-validated accuracy has error bars of about ±10%, and the standard error across folds underestimates them [57]. Metrics Reloaded recommends confidence intervals for all metrics on small test sets [1], and TRIPOD+AI requires CIs (item 23a) [26].
- Rankings are unstable: across challenges, bootstrapping showed the winner stayed first in only 21%, 11% and 9% of segmentation tasks for DSC, HD and HD95 rankings; leaving out a single test case changed the winner in up to 16% of cases, and in one task in 67%; different annotators produced different rankings in 15%, 46% and 62% of observer pairs for DSC, HD and HD95 [55]. Recommendation: report bootstrapped rank distributions (the challengeR toolkit does this) [56], and do not declare a winner when intervals overlap.
- Paired comparisons: agent and specialist are scored on the same cases, so use paired tests: Wilcoxon signed-rank as in Learn2Reg [8], DeLong for correlated AUROCs [24], McNemar for paired binary outcomes [59], or a paired bootstrap of the difference.
- Permutation nulls: label-permutation tests show whether a classifier beats chance on a small test set [70]. Recommendation: for each prediction task, include a permuted-label control and a trivial baseline (prevalence-only probability, identity transform, empty mask) so that "beats the baseline" has a defined floor.
- Respect clustering: aggregate per patient, then per site; do not pool pixels or images from the same patient as independent [1][2].
- Methodological failures in medical imaging ML, including small datasets and over-optimised benchmarks, are reviewed in [58].

---

## 2. Reporting and evaluation frameworks and what each demands of a benchmark

| Framework | Scope | What it demands of this suite |
|---|---|---|
| Metrics Reloaded [1] with pitfalls paper [2] | Metric selection for image classification, detection, semantic and instance segmentation | Choose metrics from the clinical question; pair overlap with boundary metrics; use lesion-wise detection where objects matter; add calibration when probabilities are used; define empty-reference handling; aggregate hierarchically; give CIs; use metadata to look for bias. |
| CLAIM 2024 update [60] | Reporting medical imaging AI studies | Name the "reference standard" and how it was produced; say "external testing" for evaluation on new data; describe data sources, partitions and model details. |
| TRIPOD+AI [26] and PROBAST+AI [27] | Prediction models, regression or machine learning | Report discrimination, calibration and clinical utility with CIs, including for subgroups; justify sample size; describe missing data and fairness; share code and data. |
| STARD-AI [61] | Diagnostic accuracy studies using AI | 18 new or modified items on top of STARD 2015, covering dataset practices, the AI index test and its evaluation, and algorithmic bias and fairness. |
| DECIDE-AI [62] | Early-stage live clinical evaluation of AI decision support | 17 AI-specific and 10 generic items on real clinical performance, safety and human factors. Relevant to the suite only to state that a sandboxed benchmark is pre-clinical evidence. |
| CONSORT-AI [64] and SPIRIT-AI [65] | Randomised trials of AI interventions, and their protocols | Out of scope for the suite; cite them to place benchmark evidence below trial evidence. |
| MI-CLAIM [66] | Minimum information for clinical AI modelling | Document how test-set information was kept out of every step before final evaluation; support replication. |
| FUTURE-AI [63] | Lifecycle guideline, 30 best practices under fairness, universality, traceability, usability, robustness and explainability | Robustness and fairness testing, traceability of data and code, usability in the clinical workflow. |
| FDA, Health Canada and MHRA good machine learning practice (2021), finalised by the International Medical Device Regulators Forum as N88 in 2025 [67] | Ten guiding principles for machine-learning medical devices | Training and test sets "appropriately independent", considering patient, acquisition and site dependence; reference datasets from "best available methods"; representative data; testing "during clinically relevant conditions" including key subgroups; focus on human-AI team performance; monitoring after deployment. |
| BIAS [68] and ranking-stability work [55][56] | Design and reporting of biomedical image analysis challenges | Publish the full design (metrics, aggregation, ranking, missing-data rules) before running; report how the reference was made (missing in 66% of tasks surveyed) and how missing submissions are handled (missing in 82%) [55]; quantify ranking uncertainty. |

---

## 3. Adoptable scoring table

Recommendation. The headline is what the leaderboard shows; a gate failure scores the case as a failure (zero or worst value) rather than removing it; the comparator is run on the same cases under the same budget.

| Task type | Headline score | Hard validity gates | Clinical constraint | Specialist comparator |
|---|---|---|---|---|
| Organ or structure segmentation | Per-case mean of DSC and NSD at a stated mm tolerance, averaged over cases [1][3] | Mask on the reference grid (shape, spacing, origin, orientation match); valid label set; every case present | Distances in mm; per-case runtime budget; HD95 reported | nnU-Net [5][6] |
| Lesion segmentation and detection | Lesion-wise F1 (detection) plus lesion-wise DSC with 0 for missed or spurious lesions [1][7]; absolute volume error in mL as secondary [69] | As above; pre-declared empty-reference rule; minimum lesion size declared [7] | Volume in mL; small-lesion subset reported separately | nnU-Net [5] |
| Registration (including intraoperative and multimodal) | Mean landmark TRE in mm, with initial TRE shown [8][9][11] | Transform in world coordinates and loadable; folding fraction below declared limit; no landmark use at inference | Wall-clock budget by use: intraoperative at most about 20 min by analogy with frozen-section turnaround [54], tighter where justified; runtime on fixed hardware [8] | ANTs or another classical registration, plus identity transform as floor |
| Diagnostic classification | Sensitivity (or specificity) at a pre-specified clinical operating point, plus net benefit over a stated threshold range [19][20] | One probability in [0,1] per case; all cases scored; abstention only if declared | Target prevalence stated [23]; calibration (Brier, slope, intercept) [17][18] | Tuned classical pipeline or established model |
| Tabular risk prediction | Brier score or net benefit at clinical thresholds; calibration slope and intercept [18][26] | Valid probabilities; no leakage columns; full test set | Bootstrap CIs; instability check [29] | TabPFN [33], gradient boosting [34], penalised logistic regression [30] |
| Measurement table | Absolute error in physical units against a declared tolerance; Bland-Altman limits [69] | Correct units and coordinate frame; every requested field present | Tolerance set from clinical use | Reference pipeline on the same inputs |
| Any task, subgroup layer | Worst-group headline score and largest gap with CIs [35][43] | Groups declared in advance; minimum group size for scoring | Site or scanner as a group [37] | Same comparator, per group |
| Any task, abstention and failure layer | Score with abstention charged a declared cost; risk-coverage [45][47] | Corrupted or out-of-scope inputs must be flagged | Abstention capped and checked per group [46] | Comparator's own abstention, if any |

---

## 4. Evaluation mistakes that would embarrass a healthcare benchmark

1. **Reporting AUROC alone for a model whose output is used as a probability.** Calibration was not addressed in 79% of reviewed prediction studies [30]; poor calibration can make a higher-AUROC model less useful [17]; the Epic Sepsis Model validation shows what aggregate numbers hid [31].
2. **Using image similarity or whole-organ overlap as registration accuracy.** These surrogates rate wrong transformations as good [10]; landmark TRE is the accepted measure [9].
3. **Pooling voxels or images across patients before computing DSC, or silently dropping empty-reference cases.** This hides small-structure errors and produces undefined values [1][2].
4. **Declaring a winner on a small test set without intervals.** Challenge winners often do not survive bootstrapping or a different annotator [55]; with about 100 cases, error bars are around ±10% [57].
5. **Letting the test split share sites, scanners or patients with training data.** Models detect the hospital and exploit prevalence differences [37][38]; regulators require independence across patient, acquisition and site [67].
6. **Ignoring subgroups.** Underdiagnosis concentrates in under-served groups [35], and clinically important subsets can fail while the average looks good [36].
7. **Comparing against a weak baseline.** Many segmentation claims vanish against a properly configured nnU-Net [6]; machine learning shows no AUROC advantage over logistic regression in low-bias comparisons [30].
8. **Allowing free abstention.** Abstention can widen group disparities [46] and inflate accuracy on the cases that remain.
9. **Not specifying the reference standard.** Two thirds of surveyed challenge tasks did not describe how the reference annotation was made [55]; CLAIM requires it [60].
10. **Scoring accuracy with no time budget for a time-critical use.** An intraoperative or stroke-triage answer that arrives after the clinical window is useless [53][54]; FLARE and Learn2Reg show runtime can be measured fairly on fixed hardware [8][50].

---

## References

All checked in this session. Bibliographic data from Crossref, Europe PMC or arXiv records; content claims from the abstract or full text named in the text.

1. Maier-Hein L, Reinke A, Godau P, et al. Metrics reloaded: recommendations for image analysis validation. Nat Methods. 2024;21(2):195–212. doi:10.1038/s41592-023-02151-z (full text PMC11182665)
2. Reinke A, Tizabi MD, Baumgartner M, et al. Understanding metric-related pitfalls in image analysis validation. Nat Methods. 2024;21(2):182–194. doi:10.1038/s41592-023-02150-0 (full text PMC11181963)
3. Nikolov S, Blackwell S, Zverovitch A, et al. Clinically applicable segmentation of head and neck anatomy for radiotherapy: deep learning algorithm development and validation study. J Med Internet Res. 2021;23(7):e26151. doi:10.2196/26151
4. Taha AA, Hanbury A. Metrics for evaluating 3D medical image segmentation: analysis, selection, and tool. BMC Med Imaging. 2015;15:29. doi:10.1186/s12880-015-0068-x
5. Isensee F, Jaeger PF, Kohl SAA, Petersen J, Maier-Hein KH. nnU-Net: a self-configuring method for deep learning-based biomedical image segmentation. Nat Methods. 2021;18:203–211. doi:10.1038/s41592-020-01008-z (also in the local library)
6. Isensee F, et al. nnU-Net revisited: a call for rigorous validation in 3D medical image segmentation. MICCAI 2024. arXiv:2404.09556
7. Moawad AW, Janas A, Baid U, et al. The Brain Tumor Segmentation (BraTS-METS) Challenge 2023: brain metastasis segmentation on pre-treatment MRI. arXiv:2306.00838 (2023)
8. Hering A, Hansen L, Mok TCW, et al. Learn2Reg: comprehensive multi-task medical image registration challenge, dataset and evaluation in the era of deep learning. IEEE Trans Med Imaging. 2023;42(3):697–712. doi:10.1109/TMI.2022.3213983 (arXiv:2112.04489)
9. Fitzpatrick JM, West JB. The distribution of target registration error in rigid-body point-based registration. IEEE Trans Med Imaging. 2001;20(9):917–927. doi:10.1109/42.952729
10. Rohlfing T. Image similarity and tissue overlaps as surrogates for image registration accuracy: widely used but unreliable. IEEE Trans Med Imaging. 2012;31(2):153–163. doi:10.1109/TMI.2011.2163944
11. Xiao Y, Rivaz H, Chabanas M, et al. Evaluation of MRI to ultrasound registration methods for brain shift correction: the CuRIOUS2018 challenge. IEEE Trans Med Imaging. 2020;39(3):777–786. doi:10.1109/TMI.2019.2935060
12. Xiao Y, Fortin M, Unsgård G, Rivaz H, Reinertsen I. REtroSpective Evaluation of Cerebral Tumors (RESECT): a clinical database of pre-operative MRI and intra-operative ultrasound in low-grade glioma surgeries. Med Phys. 2017;44(7):3875–3882. doi:10.1002/mp.12268
13. Gerard IJ, Kersten-Oertel M, Petrecca K, Sirhan D, Hall JA, Collins DL. Brain shift in neuronavigation of brain tumors: a review. Med Image Anal. 2017;35:403–420. doi:10.1016/j.media.2016.08.007
14. Gerard IJ, Kersten-Oertel M, Hall JA, Sirhan D, Collins DL. Brain shift in neuronavigation of brain tumors: an updated review of intra-operative ultrasound applications. Front Oncol. 2021;10:618837. doi:10.3389/fonc.2020.618837
15. Brock KK, Mutic S, McNutt TR, Li H, Kessler ML. Use of image registration and fusion algorithms and techniques in radiotherapy: report of the AAPM Radiation Therapy Committee Task Group No. 132. Med Phys. 2017;44(7):e43–e76. doi:10.1002/mp.12256
16. Latifi K, Caudell J, Zhang G, Hunt D, Moros EG, Feygelman V. Practical quantification of image registration accuracy following the AAPM TG-132 report framework. J Appl Clin Med Phys. 2018;19(4):125–133. doi:10.1002/acm2.12348
17. Van Calster B, McLernon DJ, van Smeden M, Wynants L, Steyerberg EW; STRATOS topic group. Calibration: the Achilles heel of predictive analytics. BMC Med. 2019;17:230. doi:10.1186/s12916-019-1466-7
18. Van Calster B, Nieboer D, Vergouwe Y, De Cock B, Pencina MJ, Steyerberg EW. A calibration hierarchy for risk models was defined: from utopia to empirical data. J Clin Epidemiol. 2016;74:167–176. doi:10.1016/j.jclinepi.2015.12.005
19. Vickers AJ, Elkin EB. Decision curve analysis: a novel method for evaluating prediction models. Med Decis Making. 2006;26(6):565–574. doi:10.1177/0272989X06295361
20. Vickers AJ, Van Calster B, Steyerberg EW. Net benefit approaches to the evaluation of prediction models, molecular markers, and diagnostic tests. BMJ. 2016;352:i6. doi:10.1136/bmj.i6
21. Saito T, Rehmsmeier M. The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets. PLoS One. 2015;10(3):e0118432. doi:10.1371/journal.pone.0118432
22. Guo C, Pleiss G, Sun Y, Weinberger KQ. On calibration of modern neural networks. ICML 2017. arXiv:1706.04599
23. Godau P, Kalinowski P, Christodoulou E, et al. Deployment of image analysis algorithms under prevalence shifts. MICCAI 2023, LNCS 14222:389–399. doi:10.1007/978-3-031-43898-1_38
24. DeLong ER, DeLong DM, Clarke-Pearson DL. Comparing the areas under two or more correlated receiver operating characteristic curves: a nonparametric approach. Biometrics. 1988;44(3):837–845. doi:10.2307/2531595
25. Leibig C, Allken V, Ayhan MS, Berens P, Wahl S. Leveraging uncertainty information from deep neural networks for disease detection. Sci Rep. 2017;7:17816. doi:10.1038/s41598-017-17876-z
26. Collins GS, Moons KGM, Dhiman P, et al. TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods. BMJ. 2024;385:e078378. doi:10.1136/bmj-2023-078378 (full text PMC11019967)
27. Moons KGM, Damen JAA, Kaul T, et al. PROBAST+AI: an updated quality, risk of bias, and applicability assessment tool for prediction models using regression or artificial intelligence methods. BMJ. 2025;388:e082505. doi:10.1136/bmj-2024-082505
28. Riley RD, Ensor J, Snell KIE, et al. Calculating the sample size required for developing a clinical prediction model. BMJ. 2020;368:m441. doi:10.1136/bmj.m441
29. Riley RD, Collins GS. Stability of clinical prediction models developed using statistical or machine learning methods. Biom J. 2023;65:2200302. doi:10.1002/bimj.202200302
30. Christodoulou E, Ma J, Collins GS, Steyerberg EW, Verbakel JY, Van Calster B. A systematic review shows no performance benefit of machine learning over logistic regression for clinical prediction models. J Clin Epidemiol. 2019;110:12–22. doi:10.1016/j.jclinepi.2019.02.004
31. Wong A, Otles E, Donnelly JP, et al. External validation of a widely implemented proprietary sepsis prediction model in hospitalized patients. JAMA Intern Med. 2021;181(8):1065–1070. doi:10.1001/jamainternmed.2021.2626
32. Collins GS, Dhiman P, Ma J, et al. Evaluation of clinical prediction models (part 1): from development to external validation. BMJ. 2024;384:e074819. doi:10.1136/bmj-2023-074819
33. Hollmann N, Müller S, Purucker L, et al. Accurate predictions on small data with a tabular foundation model. Nature. 2025;637:319–326. doi:10.1038/s41586-024-08328-6
34. Grinsztajn L, Oyallon E, Varoquaux G. Why do tree-based models still outperform deep learning on typical tabular data? NeurIPS 2022 Datasets and Benchmarks Track. arXiv:2207.08815
35. Seyyed-Kalantari L, Zhang H, McDermott MBA, Chen IY, Ghassemi M. Underdiagnosis bias of artificial intelligence algorithms applied to chest radiographs in under-served patient populations. Nat Med. 2021;27:2176–2182. doi:10.1038/s41591-021-01595-0
36. Oakden-Rayner L, Dunnmon J, Carneiro G, Ré C. Hidden stratification causes clinically meaningful failures in machine learning for medical imaging. Proc ACM Conf Health Inference Learn (CHIL). 2020:151–159. doi:10.1145/3368555.3384468
37. Zech JR, Badgeley MA, Liu M, Costa AB, Titano JJ, Oermann EK. Variable generalization performance of a deep learning model to detect pneumonia in chest radiographs: a cross-sectional study. PLoS Med. 2018;15(11):e1002683. doi:10.1371/journal.pmed.1002683
38. DeGrave AJ, Janizek JD, Lee SI. AI for radiographic COVID-19 detection selects shortcuts over signal. Nat Mach Intell. 2021;3:610–619. doi:10.1038/s42256-021-00338-7 (also in the local library)
39. Gichoya JW, Banerjee I, Bhimireddy AR, et al. AI recognition of patient race in medical imaging: a modelling study. Lancet Digit Health. 2022;4(6):e406–e414. doi:10.1016/S2589-7500(22)00063-2
40. Glocker B, Jones C, Bernhardt M, Winzeck S. Algorithmic encoding of protected characteristics in chest X-ray disease detection models. eBioMedicine. 2023;89:104467. doi:10.1016/j.ebiom.2023.104467 (preprint in the local library)
41. Yang Y, Zhang H, Gichoya JW, Katabi D, Ghassemi M. The limits of fair medical imaging AI in real-world generalization. Nat Med. 2024;30:2838–2848. doi:10.1038/s41591-024-03113-4
42. Winkler JK, Fink C, Toberer F, et al. Association between surgical skin markings in dermoscopic images and diagnostic performance of a deep learning convolutional neural network for melanoma recognition. JAMA Dermatol. 2019;155(10):1135–1141. doi:10.1001/jamadermatol.2019.1735
43. Sagawa S, Koh PW, Hashimoto TB, Liang P. Distributionally robust neural networks for group shifts: on the importance of regularization for worst-case generalization. ICLR 2020. arXiv:1911.08731
44. Garin SP, Parekh VS, Sulam J, Yi PH. Medical imaging data science competitions should report dataset demographics and evaluate for bias. Nat Med. 2023;29:1038–1039. doi:10.1038/s41591-023-02264-0 (also in the local library)
45. Kompa B, Snoek J, Beam AL. Second opinion needed: communicating uncertainty in medical machine learning. NPJ Digit Med. 2021;4:4. doi:10.1038/s41746-020-00367-3
46. Jones E, Sagawa S, Koh PW, Kumar A, Liang P. Selective classification can magnify disparities across groups. ICLR 2021. arXiv:2010.14134
47. Geifman Y, El-Yaniv R. Selective classification for deep neural networks. arXiv:1705.08500 (2017)
48. Mehrtash A, Wells WM, Tempany CM, Abolmaesumi P, Kapur T. Confidence calibration and predictive uncertainty estimation for deep medical image segmentation. IEEE Trans Med Imaging. 2020;39(12):3868–3878. doi:10.1109/TMI.2020.3006437
49. Zimmerer D, Full PM, Isensee F, et al. MOOD 2020: a public benchmark for out-of-distribution detection and localization on medical images. IEEE Trans Med Imaging. 2022;41(10):2728–2738. doi:10.1109/TMI.2022.3170077
50. Ma J, Zhang Y, Gu S, et al. Fast and low-GPU-memory abdomen CT organ segmentation: the FLARE challenge. Med Image Anal. 2022;82:102616. doi:10.1016/j.media.2022.102616. Challenge rules: https://flare.grand-challenge.org/ ; FLARE 2022 and 2023 metric lists: https://github.com/junma11/flare
51. Ma J, et al. Unleashing the strengths of unlabelled data in deep learning-assisted pan-cancer abdominal organ quantification: the FLARE22 challenge. Lancet Digit Health. 2024;6(11):e815–e826. doi:10.1016/S2589-7500(24)00154-7
52. Titano JJ, Badgeley M, Schefflein J, et al. Automated deep-neural-network surveillance of cranial images for acute neurologic events. Nat Med. 2018;24(9):1337–1341. doi:10.1038/s41591-018-0147-y (also in the local library)
53. Powers WJ, Rabinstein AA, Ackerson T, et al. Guidelines for the early management of patients with acute ischemic stroke: 2019 update to the 2018 guidelines. Stroke. 2019;50(12):e344–e418. doi:10.1161/STR.0000000000000211
54. Novis DA, Zarbo RJ. Interinstitutional comparison of frozen section turnaround time: a College of American Pathologists Q-Probes study of 32868 frozen sections in 700 hospitals. Arch Pathol Lab Med. 1997;121(6):559–567. PMID 9199619
55. Maier-Hein L, Eisenmann M, Reinke A, et al. Why rankings of biomedical image analysis competitions should be interpreted with care. Nat Commun. 2018;9:5217. doi:10.1038/s41467-018-07619-7
56. Wiesenfarth M, Reinke A, Landman BA, et al. Methods and open-source toolkit for analyzing and visualizing challenge results. Sci Rep. 2021;11:2369. doi:10.1038/s41598-021-82017-6
57. Varoquaux G. Cross-validation failure: small sample sizes lead to large error bars. NeuroImage. 2018;180:68–77. doi:10.1016/j.neuroimage.2017.06.061
58. Varoquaux G, Cheplygina V. Machine learning for medical imaging: methodological failures and recommendations for the future. NPJ Digit Med. 2022;5:48. doi:10.1038/s41746-022-00592-y
59. Dietterich TG. Approximate statistical tests for comparing supervised classification learning algorithms. Neural Comput. 1998;10(7):1895–1923. doi:10.1162/089976698300017197
60. Tejani AS, Klontzas ME, Gatti AA, et al. Checklist for Artificial Intelligence in Medical Imaging (CLAIM): 2024 update. Radiol Artif Intell. 2024;6(4):e240300. doi:10.1148/ryai.240300
61. Sounderajah V, et al. The STARD-AI reporting guideline for diagnostic accuracy studies using artificial intelligence. Nat Med. 2025;31:3283–3289. doi:10.1038/s41591-025-03953-8
62. Vasey B, Nagendran M, Campbell B, et al. Reporting guideline for the early-stage clinical evaluation of decision support systems driven by artificial intelligence: DECIDE-AI. Nat Med. 2022;28:924–933. doi:10.1038/s41591-022-01772-9
63. Lekadir K, Frangi AF, Porras AR, et al. FUTURE-AI: international consensus guideline for trustworthy and deployable artificial intelligence in healthcare. BMJ. 2025;388:e081554. doi:10.1136/bmj-2024-081554
64. Liu X, Cruz Rivera S, Moher D, Calvert MJ, Denniston AK; SPIRIT-AI and CONSORT-AI Working Group. Reporting guidelines for clinical trial reports for interventions involving artificial intelligence: the CONSORT-AI extension. Nat Med. 2020;26:1364–1374. doi:10.1038/s41591-020-1034-x
65. Cruz Rivera S, Liu X, Chan AW, Denniston AK, Calvert MJ; SPIRIT-AI and CONSORT-AI Working Group. Guidelines for clinical trial protocols for interventions involving artificial intelligence: the SPIRIT-AI extension. Nat Med. 2020;26:1351–1363. doi:10.1038/s41591-020-1037-7
66. Norgeot B, Quer G, Beaulieu-Jones BK, et al. Minimum information about clinical artificial intelligence modeling: the MI-CLAIM checklist. Nat Med. 2020;26(9):1320–1324. doi:10.1038/s41591-020-1041-y
67. US Food and Drug Administration, Health Canada, UK Medicines and Healthcare products Regulatory Agency. Good machine learning practice for medical device development: guiding principles. 2021. https://www.gov.uk/government/publications/good-machine-learning-practice-for-medical-device-development-guiding-principles ; finalised by the International Medical Device Regulators Forum as IMDRF/AIML WG/N88 FINAL:2025, https://www.imdrf.org/sites/default/files/2025-02/IMDRF_AIML%20WG_GMLP_N88%20Final.pdf
68. Maier-Hein L, Reinke A, Kozubek M, et al. BIAS: transparent reporting of biomedical image analysis challenges. Med Image Anal. 2020;66:101796. doi:10.1016/j.media.2020.101796
69. Bland JM, Altman DG. Statistical methods for assessing agreement between two methods of clinical measurement. Lancet. 1986;327(8476):307–310. doi:10.1016/S0140-6736(86)90837-8
70. Ojala M, Garriga GC. Permutation tests for studying classifier performance. J Mach Learn Res. 2010;11. https://jmlr.org/papers/v11/ojala10a.html
71. Bernhardt M, Jones C, Glocker B. Potential sources of dataset bias complicate investigation of underdiagnosis by machine learning algorithms. Nat Med. 2022;28:1157–1158. doi:10.1038/s41591-022-01846-8

Author lists beyond the first author, where given, are from Crossref or the publisher record; where only "et al." appears I did not confirm the full list.

## Unverified (not used as evidence above)

- **FLARE 2023 tolerances of 15 seconds per case and 4 GB GPU memory.** Stated in a participant paper (arXiv:2310.01159); I could not confirm them on an official FLARE page.
- **TrackRAD2025 latency rule.** Participant papers describe a limit of one second, some per frame and some per sequence (dataset paper: Med Phys 2025, doi:10.1002/mp.17964). The official definition was not confirmed.
- **TG-132 thresholds from the primary report.** The 2 mm mean / 5 mm maximum TRE, half-voxel rigid criterion and Dice 0.8–0.9 are cited through Latifi et al. [16]; the AAPM report PDF was not reachable. I also did not find a TG-132 numeric Jacobian tolerance.
- **Exact stroke-guideline wording.** The 20-minute imaging and 60-minute door-to-needle goals were read in AHA summary material quoting the 2018/2019 guideline, not in the full text of [53], which returned HTTP 403.
- **Titano et al. exact processing times** (often quoted as about 1.2 s versus 177 s for radiologists). Only the abstract's "minutes to seconds" was confirmed.
- **Learn2Reg TRE30 definition.** I confirmed that DSC30 and TRE30 use 30th-percentile statistics but not whether TRE30 is taken over the worst 30% of landmarks or cases.
- **Venue of Geifman and El-Yaniv [47]** (commonly cited as NIPS 2017); only the arXiv record was confirmed.
- **The DOI for Novis and Zarbo [54]**; Europe PMC gave no DOI, so the PubMed ID is given instead.
