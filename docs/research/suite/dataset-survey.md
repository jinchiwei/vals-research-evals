# Public medical datasets for the healthcare agent suite: licence and feasibility survey

Date: 14 November 2026. Author: research worker (Claude Opus 5.5, model ID `claude-opus-5-5`).

## Scope and method

This survey looks for public medical datasets that can be packaged into Harbor-format benchmark tasks on Valkyrie, the evaluation platform, which runs on Modal. The input data goes inside a Docker image uploaded to a third-party commercial platform, so the question for each dataset is whether its licence allows redistribution of a subset, including possible commercial hosting. I checked every licence marked "verified" in this session from the official dataset page, the licence file, or the hosting record (Zenodo, PhysioNet, the Kingston repository, NIRD/Sigma2, TCIA, the Amazon Web Services (AWS) open-data registry, GitHub). Where only a third-party mirror or a paper stated the licence, the entry says "third-party" and also appears in the unverified list at the end.

Abbreviations used throughout: CC BY = Creative Commons Attribution; NC = NonCommercial; SA = ShareAlike; ND = NoDerivatives; ODbL = Open Data Commons Open Database License; ODC-BY = Open Data Commons Attribution License; DUA = data use agreement; TCIA = The Cancer Imaging Archive; MSD = Medical Segmentation Decathlon; iUS = intra-operative ultrasound; TRE = target registration error (mean TRE = mTRE); AUROC = area under the receiver operating characteristic curve; ECE = expected calibration error; HC = head circumference; NSD = normalised surface distance.

Licence verdict key (the "Redistribute?" column):

- **Yes**: a permissive licence (CC0, CC BY, ODC-BY, ODbL, CC BY-SA, US public domain) that allows copying a subset into a Docker image with attribution. CC BY-SA and ODbL add a share-alike duty: any modified version we publish must carry the same licence, so the task folder needs a licence notice.
- **NC**: non-commercial only. Hosting on a commercial platform for a commercially run benchmark is a grey area at best. Treat as not usable unless the organisers confirm the event counts as non-commercial research.
- **ND**: verbatim copies only. Cropping, resampling or format conversion is a derivative and cannot be shared.
- **No**: a DUA, credentialing, or an explicit no-redistribution clause.
- **Unclear**: no licence stated anywhere official. Copyright then defaults to "all rights reserved", even when the files are freely downloadable.

"Contamination" estimates how likely frontier models saw the data, or facts about it, in training. For image tasks the reference is a pixel or voxel mask or landmark coordinates, which a model cannot plausibly recall. The practical risk is that the agent knows the dataset's conventions and the published tricks. For small tabular sets the risk is real, because the full CSV appears in thousands of notebooks. The sandbox has no internet, so the agent cannot download the public reference labels at run time.

## 1. Local material assessed first

### `/mnt/c/Users/jwei/arcadia/datasets/DRIVE` (29 MB)

- `training/images` holds 20 TIFF fundus images (565 × 584 pixels, RGB, LZW-compressed), `training/1st_manual` holds 20 vessel masks (GIF), and `training/mask` holds 20 field-of-view masks.
- `test/images` holds 20 images and `test/mask` holds 20 field-of-view masks. **The local copy has no test vessel annotations, and no second-observer annotations at all.** This matches the official page, which says: "For the test cases no annotations are made available, you will be able to submit your predictions to this site" ([drive.grand-challenge.org](https://drive.grand-challenge.org/)). Only the 20 training images can be graded locally.
- The official page gives no licence. It also notes that "Each image has been JPEG compressed", so fine-vessel edges carry compression artefacts.

### `/mnt/c/Users/jwei/arcadia/datasets/STARE` (364 MB)

- `stare-images.tar` (18.7 MB) holds the 20 vessel-segmentation images (`im0001`–`im0324`, gzipped PPM, 700 × 605).
- `labels-ah.tar` and `labels-vk.tar` hold 20 hand labels each, from two observers (Adam Hoover and Valentina Kouznetsova). Two observers allow an inter-observer ceiling, which DRIVE's training set lacks.
- `stare_raw_all-images.zip` (362 MB) holds 397 raw PPM images with no vessel labels. It is not needed.
- The official page ([cecas.clemson.edu/~ahoover/stare](http://cecas.clemson.edu/~ahoover/stare/), vessel page `/probing/`) only asks for a citation (Hoover, Kouznetsova and Goldbaum, IEEE TMI 2000) and says "Please contact me if you have any questions or requests concerning our data". **No licence is stated.**
- `datasets/ophtho_gan_code` is unrelated GAN (generative adversarial network) training code, not data.

Verdict for both: technically ready to use and small, but the licence is unclear. CHASE_DB1 (below) is a CC BY 4.0 retinal-vessel set of similar size and quality, so it is the safer choice for an uploaded image. Use DRIVE and STARE only for local development, or after emailing the maintainers.

### The teaching repository's `datasets/` folder

| Item | What it is | Verdict |
|---|---|---|
| `openi_*` files and the Open-i download script | Indiana University chest X-rays and reports from the National Library of Medicine's Open-i service. The local files are derived features and cached model outputs, not images | Third-party mirrors (Academic Torrents, Hugging Face) list **CC BY-NC-ND 4.0**. The official Open-i FAQ returned "under maintenance" today. Not usable as uploaded images (NC and ND). |
| `synthetic_demographics.csv` | Demographics generated by the repo itself | Synthetic and made in-house. It is not clinical ground truth, so it should not anchor a benchmark task. |
| APTOS-2019 (Kaggle) and the `aptos_mini` subset | Fundus diabetic-retinopathy grading | Kaggle competition rules. A secondary source says they permit non-commercial research use only and prohibit redistribution. I could not read the rules page (it needs JavaScript and a login). **Not usable.** The public Hugging Face copy of `aptos_mini` is itself a redistribution that should be checked against those rules. |
| RSNA pneumonia (Kaggle) | Chest X-rays from NIH ChestX-ray14 with bounding boxes from RSNA and the Society of Thoracic Radiology | Conflicting terms; see the chest X-ray section. |
| HAM10000 (Kaggle mirror) | Dermoscopy | Official Harvard Dataverse licence is **CC BY-NC 4.0** (verified). Not usable on a commercial platform. |
| `brain_ct.npz` (Hugging Face `little-duck/brain_CT_transform`) | 64-pixel brain CT slices, stroke vs normal | Downsampled toy data with unknown provenance and licence. **Not usable.** |
| `stroke.csv` (5,110 rows; columns match the Kaggle "Stroke Prediction Dataset" by fedesoriano) | Tabular stroke | Provenance and licence not established; the Kaggle page is the only source. **Not usable.** |
| UCI Heart Disease (fetched live) | Tabular, 303 Cleveland rows | **CC BY 4.0** (verified on [archive.ics.uci.edu/dataset/45](https://archive.ics.uci.edu/dataset/45/heart+disease): "This allows for the sharing and adaptation of the datasets for any purpose"). Very high contamination; see the tabular section. |
| NHANES 2013–14 (fetched live from CDC) | Survey and laboratory tables | US federal work, generally public domain. Not verified this session. |
| `crispr_guides.csv` | Doench 2016 guides | Not clinical; out of scope. |

## 2. Vetted candidate table

Columns: dataset and version | modality and task | reference (who made it) | cases | size | access | licence and redistribution (with source) | label-quality notes | contamination | rating.

### 2.1 3D segmentation: MSD, brain, stroke, abdomen

| Dataset | Modality and task | Reference | Cases | Size | Access | Licence and redistribution | Label notes | Contamination | Rating |
|---|---|---|---|---|---|---|---|---|---|
| **MSD Task09 Spleen** (release 1.0, 06/08/2018) | Portal-venous CT; spleen segmentation | Memorial Sloan Kettering Cancer Center; expert-verified per MSD | 41 labelled training, 20 unlabelled test (read from `dataset.json` in the archive today) | 1.61 GB archive, about 26 MB per case | Direct: `s3://msd-for-monai/` (no sign-in) | **CC BY-SA 4.0. Yes.** `dataset.json`: `"licence":"CC-BY-SA 4.0"`. [medicaldecathlon.com](http://medicaldecathlon.com/): "All data will be made available online with a permissive copyright-license (CC-BY-SA 4.0), allowing for data to be shared, distributed and improved upon." The licence file in the S3 bucket is the full CC BY-SA 4.0 text. | Single rater; test labels hidden, so use labelled training cases. | High for the dataset's existence; nil for the masks. | **Usable today** |
| MSD other tasks (01 BrainTumour 7.6 GB, 02 Heart 456 MB, 04 Hippocampus 28 MB, 05 Prostate 240 MB, 06 Lung 9.2 GB, 07 Pancreas 12.3 GB, 08 HepaticVessel 9.3 GB, 10 Colon 6.2 GB; archive sizes from the S3 listing) | CT and MRI | Various | Per task, see the MSD paper | As listed | Same bucket | CC BY-SA 4.0 per MSD. **Trap:** Task03 Liver is the LiTS data; see the next row. | Task01 uses the 2016–17 BraTS labels; the hippocampus volumes are cropped and tiny. | High | Usable with care (Task02 Heart and Task05 Prostate are small) |
| **LiTS** (Liver Tumor Segmentation, 2017) | CT; liver and tumour | Clinical sites; challenge organisers | 131 training + 70 test | About 29 GB (as MSD Task03) | CodaLab, Academic Torrents | Third-party sources (Academic Torrents, kaiko-ai eva docs, arXiv paper licence) say **CC BY-NC-ND 4.0**; one mirror says CC BY-NC-SA. The official CodaLab page showed no licence. MSD relicensed the same scans as CC BY-SA. | Known tumour-label inconsistency | High | **Not usable**: conflicting licences |
| **KiTS23** | CT; kidney, tumour, cyst | KiTS organisers | 489 training + 110 test | Large | GitHub (labels) and separate image servers | **CC BY-NC-SA 4.0. NC.** [kits-challenge.org/kits23](https://kits-challenge.org/kits23/): "The image and segmentation data are available under a CC BY-NC-SA 4.0 license." The page treats only challenge participation as non-commercial. | Good | High | **Not usable** (NC) |
| **TotalSegmentator CT dataset v2.0.1** | CT, 117 structures | Wasserthal et al., University Hospital Basel; semi-automatic labels refined by experts | 1,228 CT | 23.6 GB; about 19 MB per case | Zenodo [10047292](https://zenodo.org/records/10047292) | **CC BY 4.0. Yes** (Zenodo licence field). | Labels are model-assisted, so they favour TotalSegmentator-like outputs. | High | Usable with care: the specialist baseline was trained on these cases, see Section 3 |
| **AMOS 2022** v1 | 500 CT + 100 MRI; 15 abdominal organs | Ji et al.; annotated by a mixed human and model pipeline | 600 | 24.2 GB | Zenodo [7155725](https://zenodo.org/records/7155725) | **CC BY 4.0. Yes.** | Good; MRI subset smaller | Medium–high | **Usable today** (good multi-organ alternative) |
| **FLARE22** (50 labelled cases) | CT; 13 organs | Images and pancreas labels from MSD; other organs from AbdomenCT-1K | 50 labelled | Moderate | Zenodo [7860267](https://zenodo.org/record/7860267) | Zenodo record (third-party summary) says the other organ annotations are "research purpose only". No clear licence. | — | Medium | Not usable |
| **ISLES 2022** v2.3.1 | MRI (DWI, ADC, FLAIR; DWI = diffusion-weighted imaging, ADC = apparent diffusion coefficient, FLAIR = fluid-attenuated inversion recovery); acute ischaemic stroke lesion segmentation | Expert-annotated, multi-centre | 250 | 1.7 GB total, about 7 MB per case | Zenodo [7960856](https://zenodo.org/records/7960856) | **CC BY 4.0. Yes** (Zenodo licence field). | Small lesions; inter-rater variation on tiny infarcts | Medium | **Usable today** |
| **ATLAS v2.0** (stroke T1 MRI) | Chronic stroke lesion segmentation | Manual tracings | 655 public training + 300 hidden | Moderate | ICPSR/ADDEP and INDI | **No.** ICPSR: "you will need to download and complete the data use agreement and then email it". The redistribution terms of the agreement were not read; the DUA alone rules it out. | — | Medium | Not usable |
| **BraTS 2021** (adult glioma) | Multi-parametric MRI; tumour sub-regions | BraTS expert annotators | 1,251 training | About 12 GB | Synapse; TCIA (UPENN/BraTS collections) | TCIA table (search snippet, not the page itself) lists the segmentation training set as **CC BY 4.0**, with some source subsets "TCIA Restricted". Synapse terms not read. | Excellent | Very high | Usable with care: confirm the TCIA page. MSD Task01 is a safer CC BY-SA BraTS subset. |
| BraTS 2023/2024 | Same | Same | — | — | Synapse | The Synapse page did not render; no licence obtained. | — | — | Unverified |

### 2.2 Registration, including intra-operative

| Dataset | Modality and task | Reference | Cases | Size | Access | Licence and redistribution | Label notes | Contamination | Rating |
|---|---|---|---|---|---|---|---|---|---|
| **RESECT** v1 (2017) | Pre-operative 3T MRI (contrast T1, FLAIR) to 3D iUS before, during and after resection; low-grade glioma brain shift | Homologous landmarks by expert raters (MINC `.tag`, world mm) | 23 patients | 3.34 GB total (MINC and NIfTI copies), about 145 MB per patient for all files | Direct, no sign-in: NIRD archive, DOI [10.11582/2017.00004](https://archive.norstore.no/pages/public/datasetDetail.jsf?id=10.11582/2017.00004) | **CC BY 4.0. Yes.** NIRD record: "License: Creative Commons Attribution 4.0"; metadata `license_id: CC-BY-4.0`, "Access Rights public". | A later study reports a few landmarks with possible localisation errors in RESECT and BITE. The CuRIOUS2018 page says 22 of 23 patients have pre-resection iUS usable for the task. | Low–medium (the CuRIOUS papers are known; the coordinates are not memorable) | **Usable today** |
| **CuRIOUS 2018/2019** | Same task; test cases are extra St Olav's patients | Same raters | 10 test cases (2018) | — | Given only to challenge teams | The challenge page states no licence. Training data is RESECT. | — | — | Use RESECT itself |
| **ReMIND** (TCIA) | Pre-op MRI, 3D iUS, intra-op MRI; brain tumour resection | 356 segmentations (tumour, cavity, residual); **no landmarks** | 114 patients | 43.5 GB; segmentations 208 MB | TCIA Data Retriever and Aspera | **CC BY 4.0. Yes** ([TCIA ReMIND page](https://www.cancerimagingarchive.net/collection/remind/)). | No landmark ground truth for registration on TCIA | Low | Usable with care (segmentation-overlap metric only) |
| **ReMIND2Reg** v2.3 (Learn2Reg 2024/2025) | Contrast T1 or T2 MRI to post-resection iUS | Landmarks for validation and test held by organisers | 99 training patients, 5 validation | 3.2 GB zip | Zenodo [12700312](https://zenodo.org/records/12700312) | **CC BY 4.0. Yes** (Zenodo licence field). | The released zip appears not to include landmarks (not confirmed). Without them there is no reference. | Low | Usable with care |
| **BITE** (MNI, 2012) | Pre-op MRI to pre-resection iUS (group 2, 2.1 GB); pre-op MRI to post-resection iUS (group 4, 591 MB) | Landmarks: group 2 from two experts, group 4 about 15 per patient | 14 patients | 565 MB – 4.6 GB per group | Direct download | **Unclear.** The [BITE page](https://nist.mni.mcgill.ca/bite-brain-images-of-tumors-for-evaluation-database/) only asks for a citation, and says "All patients signed a specific consent form for the distribution of their anonymized images online (NEU-09-010)". No licence. | Same landmark caveat as RESECT | Low | Usable with care (email the MNI group) |
| **BraTS-Reg** v1 (Zenodo 2025) | Pre-operative vs follow-up glioma MRI | Expert landmarks; training only | About 140 training pairs (not confirmed) | 3.7 GB training + 533 MB validation | Zenodo [14642405](https://zenodo.org/records/14642405) | **CC BY-ND 4.0. ND.** Verbatim files can be shipped; cropped, resampled or converted files cannot. | Good | Medium | Usable with care (ship the original files unchanged) |
| **Learn2Reg NLST 2023** (lung CT, longitudinal) | Low-dose CT lung registration | Automatic keypoints for training; manual landmarks for validation and test, some unreleased | Over 200 pairs | Several GB | Lübeck cloud links on [learn2reg.grand-challenge.org/Datasets](https://learn2reg.grand-challenge.org/Datasets/) | **CC BY 4.0** per the Learn2Reg datasets page. Underlying NLST on TCIA. **Yes.** | Training keypoints are automatic (from the CorrField method), not manual | Medium | Usable with care (choose cases with public landmarks) |
| **Learn2Reg ThoraxCBCT** (2023) | Planning fan-beam CT to cone-beam CT (CBCT) across radiotherapy fractions | Keypoints and labels | At least 20 training pairs | — | Same page | **CC BY 3.0. Yes** (from the 4D-Lung TCIA collection). | — | Low | Usable with care. Strong "time-critical" framing (image-guided radiotherapy). |
| **Learn2Reg LungCT** (Radboud, 2020) | Inhale/exhale CT | 100 landmarks per case (test set: manual) | 30 (20 training / 10 test) | 530 MB | Zenodo 3835682 / Lübeck | Third-party claim of CC BY 4.0; the Learn2Reg page gives only a citation | — | Medium | Usable with care |
| **Learn2Reg OASIS** | Inter-subject T1 brain MRI | 35 FreeSurfer labels (automatic) | 416 training + 39 test | 1.3 GB | Lübeck cloud | **OASIS Data Use Agreement**; Learn2Reg says to "refer to the OASIS Data Use Agreement". Older DUA lets derived data be distributed "under terms … established by the creators". | Automatic labels | High | Usable with care |
| **Learn2Reg AbdomenMRCT** | MR to CT, abdomen | Organ masks | 16 pairs + 90 unpaired scans | 1.8 GB | Lübeck cloud | Mixed: TCIA, BCV (Beyond the Cranial Vault, requires Synapse registration), and CHAOS readmes | Few, noisy labels | Medium | Not usable as-is (BCV terms) |
| COMULIS (Learn2Reg 2024, microscopy) | Correlative microscopy | — | — | — | — | Not checked | — | — | Unverified, and off-theme |

### 2.3 Retinal

| Dataset | Task | Reference | Cases | Size | Access | Licence and redistribution | Label notes | Contamination | Rating |
|---|---|---|---|---|---|---|---|---|---|
| **CHASE_DB1** | Fundus vessel segmentation, children | Two independent human observers | 28 images (14 children, both eyes), 999 × 960 | **2.4 MB zip** | Direct: [Kingston research portal](https://researchinnovation.kingston.ac.uk/en/datasets/chasedb1-retinal-vessel-reference-dataset-4/) | **CC BY 4.0. Yes.** Kingston record: "CHASEDB1 File: application/zip, 2.4 MB … Licence: Creative Commons: Attribution 4.0". | Two observers give an inter-observer ceiling | High (classic benchmark) | **Usable today** |
| DRIVE | Vessel segmentation | One observer (training); test labels hidden | 40 images (20 graded locally) | 29 MB local | grand-challenge (registration) | **Unclear**; no licence on the official page | JPEG artefacts | Very high | Usable with care (local development only) |
| STARE | Vessel segmentation | Two observers | 20 images | 19 MB (images) + 0.6 MB (labels) local | Direct | **Unclear**; no licence on the official page | Pathological images, good for robustness | Very high | Usable with care |
| **IDRiD** | Lesion segmentation (81 images, 4288 × 2848); DR grading (516); optic disc and fovea localisation | Clinical experts (Indian ophthalmology clinic) | 81 / 516 | Moderate (JPG and TIFF) | IEEE DataPort (open access; download needs a free IEEE account) | **CC BY 4.0. Yes.** [IEEE DataPort page](https://ieee-dataport.org/open-access/indian-diabetic-retinopathy-image-dataset-idrid): "License: Creative Commons Attribution". | User comments report missing grading labels for some images | Medium | Usable with care (needs someone's IEEE account to download) |
| APTOS 2019 | DR grading | Clinicians (Aravind) | About 3,662 training | 19 GB raw | Kaggle | Kaggle rules: non-commercial, no redistribution (secondary source) | Known label noise | High | Not usable |
| REFUGE | Glaucoma; optic disc and cup segmentation | Ophthalmologists | 1,200 | — | grand-challenge, Figshare | No official licence found; one paper claims CC BY 4.0 | — | Medium | Unverified |

### 2.4 Chest X-ray

| Dataset | Task | Reference | Cases | Access | Licence and redistribution | Label notes | Contamination | Rating |
|---|---|---|---|---|---|---|---|---|
| **NIH ChestX-ray14** | 14-finding multi-label classification; age and sex available | **Natural-language-processing (NLP) text-mined labels** ("expected to have accuracy >90%") | 112,120 images, 30,805 patients | NIH Box | NIH terms as quoted by the Hugging Face mirror card: "There are no restrictions on the use of the NIH chest x-ray images", with three attribution conditions (link, cite CVPR 2017, credit the NIH Clinical Center). The official README on Box did not render. **Yes, pending confirmation.** | Labels are noisy and sometimes clinically wrong (a widely documented critique) | Very high | Usable with care. Prefer the RSNA adjudicated boxes for labels. |
| **RSNA Pneumonia 2018** | Pneumonia opacity detection and classification | Radiologists from RSNA and the Society of Thoracic Radiology, adjudicated | About 30,000 images (subset of ChestX-ray14) | RSNA S3 bucket (direct) or Kaggle | **Conflict.** The RSNA page fetched today says "You may access and use the imaging datasets and annotations for the purposes of academic research and education … as long as you meet the following attribution requirements". A search snippet of the same page also listed "other commercial or non-commercial purposes". The Kaggle rules (quoted in a paper) say non-commercial. The terms PDF was not readable. | Good | High | Usable with care (the RSNA-hosted copy only, after reading the terms PDF) |
| VinDr-CXR | 22 local findings + 6 global labels, boxes | 17 radiologists | 18,000 | PhysioNet, credentialed | **No.** "Only credentialed users who sign the DUA can access the files. License: PhysioNet Credentialed Health Data License 1.5.0" | Excellent | Medium | Not usable |
| Open-i (Indiana University) | Reports and images | Radiologist reports | 3,996 reports / about 8,121 images | NLM | CC BY-NC-ND 4.0 per mirrors; official page down today | — | High | Not usable |

### 2.5 Dermatology

| Dataset | Licence (source) | Rating |
|---|---|---|
| HAM10000 v4 (10,015 dermoscopy images; histopathology-confirmed for more than half) | **CC BY-NC 4.0** (Harvard Dataverse licence field, verified) | Not usable (NC) |
| Fitzpatrick17k (16,577 clinical images with Fitzpatrick skin-type labels) | Annotations: "Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported" ([GitHub](https://github.com/mattgroh/fitzpatrick17k)). Images are not in the repo: "You can download the images from their original source … the url column", from the Atlas Dermatologico and DermaAmin websites, whose copyright is separate | Not usable |
| DDI (Diverse Dermatology Images, Stanford) | Research Use Agreement ([ddi-dataset.github.io](https://ddi-dataset.github.io/)): "YOU MAY NOT DISTRIBUTE, PUBLISH, OR REPRODUCE A COPY of any portion or all of the Diverse Dermatology Images Dataset to others without specific prior written permission" | Not usable |

No dermatology set with skin-tone subgroups is redistributable for commercial hosting. The subgroup-calibration requirement therefore moves to ECG (sex and age).

### 2.6 ECG

| Dataset | Task | Reference | Cases | Size | Licence | Label notes | Contamination | Rating |
|---|---|---|---|---|---|---|---|---|
| **PTB-XL** v1.0.3 | 12-lead, 10-second ECG; 71 SCP-ECG statements (SCP-ECG is the standard ECG statement coding), 5 diagnostic superclasses; age and sex metadata | Up to two cardiologists; "A large fraction of the records was validated by a second cardiologist" | 21,799 ECGs, 18,869 patients | 3.0 GB (both 100 Hz and 500 Hz); 100 Hz alone is about 0.5 GB | **CC BY 4.0. Yes.** [PhysioNet](https://physionet.org/content/ptb-xl/1.0.3/): "Anyone can access the files … License: Creative Commons Attribution 4.0 International Public License" | Some labels come from the device's automatic interpretation; duplicates were removed in 1.0.2–1.0.3. Recommended folds: train on 1–8, validate on 9, test on 10. | High (standard benchmark) | **Usable today** |
| **Chapman-Shaoxing / Ningbo** (`ecg-arrhythmia` 1.0.0) | 12-lead rhythm and conduction labels | Licensed physicians | 45,152 patients | 5.1 GB | **CC BY 4.0. Yes** (PhysioNet) | Some label inconsistencies reported in the literature | Medium | Usable today (external test set for PTB-XL models) |

### 2.7 Pathology (patch-level, open licence)

| Dataset | Task | Size | Licence | Rating |
|---|---|---|---|---|
| **NCT-CRC-HE-100K / CRC-VAL-HE-7K** (Kather) | 9-class colorectal tissue classification; "224x224 pixels (px) at 0.5 microns per pixel" | 100,000 + 7,180 patches; the 7K set is 800 MB | **CC BY 4.0. Yes** (Zenodo [1214456](https://zenodo.org/records/1214456)) | **Usable today** (true scanning resolution) |
| PatchCamelyon (PCam) | Lymph-node metastasis, binary; 96 × 96 patches downsampled from CAMELYON16 | About 7 GB | **CC0.** GitHub: "The data is provided under the CC0 License, following the license of Camelyon16" | Usable with care (MedMNIST-like toy patch size) |

### 2.8 Tabular and EHR without credentialing

EHR = electronic health record; ICU = intensive care unit.

| Dataset | Task | Size | Licence | Label notes | Contamination | Rating |
|---|---|---|---|---|---|---|
| **PhysioNet/CinC Challenge 2012** | ICU in-hospital mortality from the first 48 hours (time series of 37 variables + descriptors, plus SAPS-I and SOFA severity scores) | 12,000 stays (sets A, B, C, 4,000 each); outcome files `Outcomes-a/b/c.txt` are now all published | **ODC-BY 1.0. Yes** ([PhysioNet](https://physionet.org/content/challenge-2012/1.0.0/): "Open Data Commons Attribution License v1.0") | Real outcomes from MIMIC-II | Medium (well known, but the per-stay labels are not memorisable) | **Usable today** |
| **PhysioNet/CinC Challenge 2019** | Early sepsis prediction, hourly | 40,336 subjects from two hospital systems | **CC BY 4.0. Yes** (PhysioNet) | Sepsis-3 labels derived by the organisers; the hidden third hospital system is not public, so only two systems are available | Medium | Usable today |
| **MIMIC-IV Clinical Database Demo** v2.2 | Full relational EHR | 100 patients, 15.5 MB | **ODbL v1.0. Yes** (share-alike for derived databases) ([PhysioNet](https://physionet.org/content/mimic-iv-demo/2.2/)) | Real data, but n = 100 is too small for a stable risk metric | Medium | Usable with care (good for "query the EHR" tasks, not for scoring calibration) |
| **eICU-CRD Demo** v2.0.1 | Multi-centre ICU EHR | Over 2,500 unit stays from 20 hospitals, 130.6 MB | **ODbL v1.0. Yes** | — | Medium | Usable today (hospital-level subgroups) |
| **UCI Heart Disease** | Coronary disease presence | 303 Cleveland rows (920 across four sites) | **CC BY 4.0. Yes** | 1988 data; heavy missingness outside Cleveland | **Very high**: the agent may know published accuracies and even rows | Usable with care (fine as a calibration smoke test, weak as evidence) |
| NHANES | Population survey | Varies | US public domain (not verified this session) | No hard outcomes without linked mortality files | High | Usable with care |
| Synthea | Synthetic EHR generator | Any size | Generator: Apache-2.0 (verified on GitHub) | Synthetic rules, not clinical truth | Medium | Usable with care (tests the plumbing, not clinical skill) |

### 2.9 Measurement in physical units

| Dataset | Task | Reference | Cases | Size | Licence | Rating |
|---|---|---|---|---|---|---|
| **HC18** v2 (fetal head circumference) | 2D ultrasound; measure HC in mm using the per-image pixel size (0.052–0.326 mm) | Trained sonographer (ellipse annotation image + HC in mm in `training_set_pixel_size_and_HC.csv`) | 999 training, 335 test (test labels hidden on [hc18.grand-challenge.org](https://hc18.grand-challenge.org/)) | Training zip 132.9 MB, test 43.5 MB | **CC BY 4.0. Yes** (Zenodo [1327317](https://zenodo.org/records/1327317)) | **Usable today** |
| CAMUS (echo, left-ventricle ejection fraction) | 2D echo | Cardiologist contours | 500 patients | — | Third-party: CC BY-NC-SA 4.0, "strictly only non-commercial scientific research" | Not usable |
| Spleen or organ volume from MSD or AMOS masks | Volume in mL | Derived from the expert mask × voxel spacing | See above | See above | CC BY-SA / CC BY | Usable today (secondary measurement) |

### 2.10 Surgical video

Cholec80, EndoVis and similar sets were not checked. They are typically non-commercial, multi-GB, and need frame-level tooling. Not feasible today.

## 3. Specialist baselines for the usable candidates

| Dataset | Baseline we can run offline | Weights: source and licence | Published reference performance | Training overlap with our cases? |
|---|---|---|---|---|
| RESECT (MRI to iUS) | ANTs SyN (ANTs = Advanced Normalization Tools; SyN = symmetric normalisation) with mutual information, or NiftyReg, after the given world-coordinate alignment. No weights needed. | ANTs: Apache-2.0. NiftyReg: BSD (not re-checked today). | CuRIOUS2018 (Xiao et al., IEEE TMI 2020, [PMC7611407](https://pmc.ncbi.nlm.nih.gov/articles/PMC7611407)): RESECT training initial mTRE **5.37 ± 4.27 mm**; test initial 6.38 ± 4.36 mm; best test 1.57 ± 0.96 mm (ImFusion, 20 s on GPU); DeedsSSC 1.87 ± 0.93 mm (25 s on CPU); NiftyReg 3.21 ± 3.57 mm (115 s). | None for classical methods. Learned methods from CuRIOUS trained on RESECT, so do not use them as the baseline. |
| MSD Task09 Spleen | **TotalSegmentator** `total` task (spleen label), CPU or GPU, about 1 minute | Apache-2.0: "Openly available for any usage (Apache-2.0 license)" for the `total` task ([GitHub](https://github.com/wasserth/TotalSegmentator)). Weights are downloaded from the authors' release; pre-fetch them into the baseline image. | Overall Dice 0.943 on the internal test set; 0.849 on BTCV (Wasserthal et al., Radiology: AI 2023, [PMC10546353](https://pmc.ncbi.nlm.nih.gov/articles/PMC10546353/)). Spleen-specific Dice is in a results file that was not read. | **No.** TotalSegmentator trained only on University Hospital Basel CT ("from the University Hospital Basel picture archiving and communication system"); MSD spleen is from Memorial Sloan Kettering. This is a genuine generalisation baseline. The opposite holds for nnU-Net's pretrained MSD models, which were trained on these exact 41 cases. If nnU-Net is used, take the cross-validation fold model that held each case out. |
| TotalSegmentator dataset | TotalSegmentator | As above | 0.943 Dice | **Yes, total overlap.** Use AMOS or MSD as the test data instead. |
| ISLES 2022 | DeepISLES ensemble (top ISLES'22 teams) or an nnU-Net trained on the other cases | DeepISLES code at github.com/ezequieldlrosa/DeepIsles; weights licence **not verified** | Dice 0.82 ± 0.12 on the ISLES'22 hidden test set (grand-challenge DeepISLES page; de la Rosa et al., Nature Communications 2025) | **Yes.** DeepISLES trained on all 250 public cases. As generalisation evidence its score on public cases is optimistic; the hidden test labels are not public. |
| HC18 | Classical pipeline: denoise, skull edge, Hough or least-squares ellipse fit, perimeter by the Ramanujan approximation × pixel size; or a 2D nnU-Net trained on the remaining training images (about 1 hour on GPU) | No pretrained weights needed | Moccia et al. (Mask-R² CNN) report a mean absolute difference of 1.95 mm on HC18 (secondary source; the leaderboard was not read). The van den Heuvel 2018 random-forest system reports gestational-age errors in days rather than mm. | Only if trained on our held-out images; exclude them. |
| PTB-XL | `xresnet1d101` or `inception1d` from the benchmark repo, trained on folds 1–8 (GPU, under 1 hour at 100 Hz) | Code GPL-3.0 ([helme/ecg_ptbxl_benchmarking](https://github.com/helme/ecg_ptbxl_benchmarking)); we train our own weights, so no weights licence issue | Macro AUROC on fold 10: superdiagnostic 0.928 (xresnet1d101), 0.930 (resnet1d_wang); all statements 0.925; rhythm 0.957 (Strodthoff et al., IEEE JBHI 2021, repo README) | No, provided fold 10 is held out. Any public "PTB-XL pretrained" checkpoint saw folds 1–8 only by convention; check before use. |
| PhysioNet 2012 | (a) SAPS-I already in the data; (b) gradient-boosted trees on hand-made 48-hour summaries; (c) TabPFN v2 on the same summaries | TabPFN code Apache-2.0. **TabPFN-2 weights**: "Prior Labs License (Apache 2.0 with an additional attribution requirement)". TabPFN 2.5, 2.6, 3 and 3.5 weights are **non-commercial**, and **3.5 is the default**. Weights download needs a Prior Labs login and licence acceptance, which a person on the team must do. | Challenge top Event 1 score (min(sensitivity, positive predictive value)) **0.5353** and top Event 2 score (Hosmer–Lemeshow H statistic, lower is better) **17.88** (Silva et al., CinC 2012, via MIT DSpace) | No: train on set A, test on set B or C. |
| CHASE_DB1 | Classical Frangi or matched filter with thresholding; small U-Net trained on CHASE images not in the task | No weights needed | Inter-observer agreement (observer 2 vs observer 1) is the ceiling; compute it ourselves. Typical deep-learning Dice in the literature is about 0.80–0.83 (not verified). | Exclude test images from training. |
| Kather CRC | ImageNet ResNet-50 linear probe or fine-tune on NCT-CRC-HE-100K, tested on CRC-VAL-HE-7K | timm/torchvision ImageNet weights (BSD/Apache-type licences; ImageNet terms are a separate question) | Kather et al., PLOS Medicine 2019: nine-class accuracy "more than 94%" on the independent 7K set (exact figure not confirmed) | 100K and 7K come from different patients by design. Pathology foundation models (UNI, Virchow and others) are gated and may include these patches in their evaluations. |

## 4. Ranked shortlist: a credible suite packable today

Each task image should stay under about 200 MB. The case counts below are deliberately small; the grader holds the references.

| Rank | Dataset and task | Exact subset | Metric (clinical meaning) | Baseline | Expected frontier-agent difficulty | Data in image |
|---|---|---|---|---|---|---|
| 1 | **RESECT: pre-operative MRI to pre-resection iUS registration (brain shift), intra-operative and time-limited** | 4 patients: T1 contrast (or FLAIR) MRI + pre-dura iUS, NIfTI only. The agent outputs warped MRI landmark coordinates (we give MRI-side landmarks; the grader holds the iUS side) or a displacement field. | mTRE in mm on the expert landmarks; pass if mTRE ≤ 2 mm, and must improve on the initial alignment. **Wall-clock limit of 2 minutes per case on CPU** to mimic the operating room. | ANTs SyN with mutual information; report the CuRIOUS published 1.57 / 1.87 / 3.21 mm and the initial 5.37 mm | **Hard.** Multimodal MRI-to-ultrasound with partial field of view, speckle, and no intensity correspondence. Agents tend to run rigid or affine registration only, or to over-warp. The time limit forbids long training. | About 60–90 MB (estimated from 145 MB per patient including MINC duplicates and the during/after-resection iUS, which we drop) |
| 2 | **MSD Task09 Spleen: 3D CT segmentation, plus spleen volume** | 5 labelled training cases (for example `spleen_2`, `_10`, `_19`, `_29`, `_44`; pick ones near the median size) | Dice and NSD at 2 mm; absolute spleen volume error in mL (splenomegaly is volume-based). Runtime limit 10 minutes per case on CPU. | TotalSegmentator (no training overlap) | **Medium.** Easy if the agent knows to use a classical threshold plus connected components on contrast CT; hard to reach Dice above 0.9 without a pretrained model. Tests whether it handles NIfTI orientation and spacing correctly. | About 130 MB |
| 3 | **HC18: fetal head circumference in mm** | 40 training images (with their pixel sizes) whose HC values and annotations go only to the grader, plus 100 other training images with labels for the agent to calibrate on | Absolute error in mm; percentage within ±3 mm. Clinically, a few mm of HC error shifts estimated gestational age. | Classical ellipse fit; published 1.95 mm (deep learning) | **Medium.** Requires correct pixel-size scaling and an ellipse perimeter rather than a pixel count. A classic trap for agents that ignore units. | About 20 MB |
| 4 | **PTB-XL: calibrated 5-superclass ECG classification with sex and age subgroups** | Train on folds 1–8, subsampled to about 6,000 records at 100 Hz (stored as float16 `.npz`); test on fold 10 (about 2,200 records) with labels withheld | Macro AUROC; Brier score and ECE; worst-subgroup AUROC across sex × age band (< 40, 40–65, > 65) | xresnet1d101 trained on the same subsample; published full-data AUROC 0.928 | **Medium–hard.** Multi-label output with calibration required. Agents often output hard labels or ignore the patient-wise folds. | About 150 MB (0.5 GB per 21,799 records at int16 ≈ 24 KB per record; 8,200 records ≈ 200 MB raw, about 150 MB compressed) |
| 5 | **PhysioNet 2012: 48-hour ICU in-hospital mortality, calibrated risk** | Set A (4,000 stays, with outcomes) for training; 1,000 stays from set B for testing, outcomes withheld (`Outcomes-b.txt` stays with the grader) | AUROC, Brier score, calibration slope and intercept, and the challenge Event 1 score; subgroups by ICU type and age | SAPS-I; gradient-boosted trees; TabPFN-2 (licence acceptance needed) | **Medium.** Irregular time series, `-1` missing-value codes, the need to aggregate. Overconfident probabilities are the common failure. | About 15 MB |
| 6 | **CHASE_DB1: retinal vessel segmentation, two-observer reference** | Images 1–20 (both eyes of 10 children) with observer-1 masks for training; images from the remaining 4 children as the hidden test | Dice and clDice (centreline Dice, which rewards vessel connectivity) vs observer 1, reported against the observer-2-vs-observer-1 ceiling | Matched filter or Frangi; small U-Net | **Medium.** Thin vessels and the need to split by child, since left and right eyes are correlated. | 2.4 MB |
| 7 | **Kather CRC: 9-class histology patch classification at 0.5 µm/px** | 2,700 patches from NCT-CRC-HE-100K (300 per class) for training; 900 from CRC-VAL-HE-7K (100 per class) as the hidden test | Balanced accuracy; tumour-vs-rest sensitivity; ECE | ImageNet ResNet-50 linear probe | **Easy–medium.** Strong colour-normalisation shortcuts. A useful contrast to show agents do well on clean 2D classification. | About 120 MB |
| 8 (stretch) | **ISLES 2022: 3D stroke lesion segmentation and infarct volume** | 4 cases from distinct centres (DWI + ADC + FLAIR) | Dice, lesion-wise F1, absolute volume difference in mL (relevant to thrombectomy selection) | DeepISLES (training overlap: report as an upper bound, not as generalisation) | **Hard.** Small lesions; multi-sequence alignment (to my knowledge ISLES'22 FLAIR is in its native space, not co-registered to DWI; this was not re-checked today). | About 30 MB |

Coverage check: registration with an intra-operative time limit (1); 3D segmentation (2, and 8); calibrated classification with subgroups (4, and 7 for calibration); tabular risk (5); measurement in physical units (3, and the volumes in 2 and 8). Modalities: MRI, ultrasound, CT, fundus, ECG, histopathology, ICU time series. If a second registration task is wanted, Learn2Reg ThoraxCBCT (CC BY 3.0, planning CT to CBCT for radiotherapy) is the natural time-critical alternative.

## 5. Licence and ethics notes a judge may ask about

1. **Commercial platform vs NC licences.** Valkyrie runs on Modal, a commercial service, and the benchmark is a company-run evaluation. Everything shortlisted is CC BY, CC BY-SA or ODC-BY, so no non-commercial question arises. HAM10000, KiTS, Open-i, APTOS, CAMUS, Fitzpatrick17k and DDI were excluded for this reason.
2. **Attribution and share-alike duties.** Each task folder should carry a `LICENSE-DATA.md` with the dataset citation, the licence name and link, and a note of modifications (cropping, format conversion, file renaming). MSD data is CC BY-SA 4.0, so a modified spleen subset must stay CC BY-SA. PhysioNet 2012 (ODC-BY) and the eICU and MIMIC demos (ODbL) need the attribution text; ODbL also needs share-alike for derived databases.
3. **Licence laundering in the MSD.** MSD Task03 (liver) republishes LiTS scans under CC BY-SA, while third-party LiTS sources list CC BY-NC-ND. Avoid Task03 and say why if asked.
4. **ND licences.** BraTS-Reg (CC BY-ND 4.0) can be shipped only as unmodified original files. Do not crop or resample it inside the image.
5. **De-identification and consent.** All shortlisted sets are released de-identified by their custodians. RESECT and BITE patients consented to public release (BITE states a specific consent form for online distribution). We do not re-identify, link, or add data.
6. **No credentialed data.** Nothing from MIMIC-IV full, VinDr-CXR, eICU full, ATLAS or UCSF private releases goes into an image. The UCSF PCNSL (primary central nervous system lymphoma) MRI release stays on its private server, as instructed.
7. **Weights licences are separate from data licences.** The TotalSegmentator `total` model is Apache-2.0, but several of its subtasks need a licence and one is CC BY-NC. TabPFN's default 3.5 weights are non-commercial; only TabPFN-2 weights are Apache-with-attribution, and downloading them needs a person to accept the terms. We must not accept any licence on anyone's behalf.
8. **Contamination.** Public benchmarks are well known. Mitigations: hidden references, renamed files, held-out splits the agent cannot see, physical-unit metrics that cannot be guessed, and no internet in the sandbox. UCI Heart was left off the shortlist because the full table is likely memorised.
9. **Clinical validity claims.** These tasks measure technical competence on retrospective data. None is a claim of clinical safety. Reference labels have known noise (single raters for MSD, some landmark errors in RESECT, automatic interpretation in some PTB-XL labels). Report inter-observer ceilings where they exist (CHASE_DB1, STARE).

## 6. Unverified items and what would settle them

| Item | Status | What would settle it |
|---|---|---|
| DRIVE and STARE licence | No licence on either official page | Email the maintainers (DRIVE via grand-challenge; STARE via Adam Hoover) for written redistribution permission |
| LiTS licence | Third-party sources only (CC BY-NC-ND vs CC BY-NC-SA) | Official CodaLab data page or the LiTS organisers |
| Open-i (Indiana) licence | Mirrors say CC BY-NC-ND 4.0; the official FAQ was under maintenance today | Re-check [openi.nlm.nih.gov/faq](https://openi.nlm.nih.gov/faq) |
| NIH ChestX-ray14 wording | Quoted from the Hugging Face mirror card, not the NIH README | Read `README_CHESTXRAY.pdf` on the NIH Box folder |
| RSNA Pneumonia terms (commercial use?) | The RSNA page states research and education; the terms PDF was not read; the Kaggle copy is non-commercial | Read "Pneumonia Detection Challenge Terms of Use and Attribution" on rsna.org |
| BraTS 2021 CC BY 4.0 on TCIA; BraTS 2023/2024 terms | Search snippet only; Synapse page did not render | TCIA BraTS collection page licence column; Synapse wiki |
| APTOS rules | Secondary paper: non-commercial, no redistribution | Kaggle rules section 7 (needs a login) |
| FLARE22 / FLARE23 | "Research purpose only" for AbdomenCT-1K labels | flare22.grand-challenge.org/Rules |
| REFUGE, CAMUS | Licence from third parties only | Figshare record 10.6084/m9.figshare.26049574; humanheart-project page |
| Learn2Reg LungCT CC BY 4.0; ReMIND2Reg landmarks | Third-party; landmarks probably not in the zip | Zenodo 3835682 licence field; unzip the ReMIND2Reg listing |
| BraTS-Reg case count | Not shown on the Zenodo page | Unzip the listing or read the BraTS-Reg paper |
| DeepISLES weights licence | Not stated in the results found | LICENSE file at github.com/ezequieldlrosa/DeepIsles |
| NHANES public-domain status | Not fetched today | CDC NHANES data-use statement |
| NiftyReg licence | Not re-checked | NiftyReg repository LICENSE |
| HC18 leaderboard best error; Kather exact accuracy (94.3%?); CHASE_DB1 typical Dice | Secondary sources | hc18.grand-challenge.org leaderboard; Kather 2019 full text; a CHASE benchmark paper |
| RESECT per-patient NIfTI size | Estimated from the 3.34 GB total | NIRD table of contents (292 KB JSON) or a single-patient download |
| PhysioNet 2012 Event 1 winner | Overview says 0.5353; a participant paper says its 0.5345 was second | Silva et al. 2012 overview, results table |
| Surgical video sets, COMULIS | Not checked | Not needed for the shortlist |

Probe file: the first 3 MB of the MSD spleen archive, used to read `dataset.json`, is at `/mnt/c/Users/jwei/arcadia/repos/vals-research-evals/exp/suite-data-probe/msd-head/spleen_head.bin`. It can be deleted.
