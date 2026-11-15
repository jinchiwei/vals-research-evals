## The job

We want a sore-throat triage aid for a GP front desk or a phone app. A patient with a sore throat or cold
symptoms has a photo of the back of their throat taken with a smartphone (flash on, mouth open), and
answers a short yes/no symptom checklist plus age and sex. Your pipeline turns that into **one calibrated
probability that the pharyngitis is bacterial**. The clinic will use it to decide who goes on to a rapid
antigen test (and possibly antibiotics) and who can be sent home with supportive care. Missing a bacterial
throat matters more than sending an extra patient for a swab, but a tool that sends everyone for a swab
is useless.

## What the reference label is (read this)

There is no throat culture or rapid antigen test in this dataset. Each patient was called "Bacterial" or
"Non Bacterial" by 3 to 9 physicians: one examined the patient in person and the others read the photo
and the symptom record. **A patient counts as bacterial when at least half of the physicians called it
bacterial** (ties count as bacterial: if half the panel would act, the patient should be swabbed). So you
are predicting a physician panel's judgement, not microbiology. The development labels include the vote
counts so you can see how contested each case was.

## Data in `/workspace/data/`

- `dev/input/patients.csv`: one row per development patient: `case_id`, `age` (years), `sex` (F/M) and 20
  binary symptoms (1 = present): feeling_cold, sore_throat, cephalalgia (headache), myalgia, rhinorrhea,
  diarrhea, vomit, cough, pyrexia (fever), rigors, lethargy, sputum, abdominal_pain, vertigo, sternutation
  (sneezing), eye_infection, otalgia (ear pain), nasal_congestion, asthma, anorexia. No missing values.
- `dev/input/images/<case_id>.jpg`: one throat photo per patient, cropped by the dataset authors around
  the throat and not resized, so sizes vary widely (roughly 300 to 5700 px wide). Two phone models, two
  cities with different climates and lighting. Some photos are soft or focused on the lips; that is
  deliberate, it is what a phone app will see. All metadata (EXIF) has been removed.
- `dev/reference/labels.csv`: `case_id`, `bacterial` (0/1, the reference above), `n_votes`,
  `n_bacterial_votes`.
- `models/resnet50_imagenet1k_v2.pth`: torchvision ResNet-50 weights pretrained on ImageNet-1k (general
  photographs, nothing medical). Use it or not; it is there because the grader has no network.
- About 28% of development patients are bacterial by this definition. Expect the hidden patients to come
  from the same clinics, phones and period.

Source: PGUPharyngitis (Shojaei et al., Scientific Data 12:1418, 2025; figshare
10.6084/m9.figshare.28163513, CC BY 4.0). Changes made for this task: metadata stripped, files renamed,
one PNG re-encoded as JPEG, labels derived from the votes as above, patients split into development and
hidden sets.

## What "good enough" means here (fixed before any results were seen)

The grader scores the probabilities you produce for the hidden patients, all at once:

1. **Rule-out operating point**: at the threshold that catches at least 85% of bacterial patients
   (about the sensitivity of a rapid antigen test), at least 40% of non-bacterial patients must be spared
   the referral (specificity >= 0.40).
2. **Calibration**: expected calibration error (10 equal-width bins) <= 0.10 and a calibration slope
   between 0.5 and 2.0. The clinic will act on the number, not just the ranking.
3. **Net benefit**: referring everyone with probability >= 0.15 must give more net benefit than referring
   everyone or no one.
4. **No subgroup left behind**: at the threshold from point 1, sensitivity >= 0.70 in every group with
   at least 10 bacterial patients, by sex, by age (<15 and >=15 years) and by phone model.

All four must hold. Discrimination (AUROC) is also recorded.

## Practical constraints

- One call of `run.sh INPUT_DIR OUTPUT_DIR` processes **the whole hidden cohort** (`INPUT_DIR` looks like
  `dev/input/`: `patients.csv` plus `images/`). The grader's clock allows 60 s plus 2 s per patient on
  2 CPU cores, no GPU, no network.
- Write `OUTPUT_DIR/predictions.json` exactly as described under "Required outputs".
