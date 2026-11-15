# Imaging task data audit, 2026-11-14

This read-only audit uses only the hosted UCSF-PCNSL release on FAC. It supports segmentation, lesion volume/count and ADC quantification tasks; it does not run a model or claim clinical validity. Patient paths and selected-case records remain on FAC. Only aggregate results belong in `pcnsl/results/20261114-imaging-data/`.

FAC CPU job **3068002 completed successfully (0:0)** in 3 minutes 53 seconds. It inspected all 1,500 NIfTI headers and all 300 mask voxel arrays. No patient-level values or manifest rows were transferred.

## Actual unit and label findings

| Audit | Result |
|---|---|
| Image files | 1,200, including 300 ADC files |
| Masks | 300 across 150 patients |
| Mask spatial/temporal units | **Unknown/unknown in all 300** |
| ADC spatial/temporal units | **mm/sec in all 300** |
| Other images' units | 600 mm/sec; 300 unknown/unknown |
| ADC stored and effective scaling | Slope 1, intercept 0 in all 300 |
| Mask labels | All finite, nonnegative integers; positive labels contiguous from 1 |
| Binary / multiple-instance masks | 157 / 143 |
| Empty masks | 0 |
| Positive instance labels per mask | 1–52, median 1 |

**Physical volumes require explicit reference-image provenance.** The mask headers alone do not establish millimetres. The earlier complete geometry audit established matching shapes/affines for all 1,200 same-space image/mask pairs; each mask has a paired ADC image whose spatial units are mm. A scorer may inherit mm from that verified reference after checking the pair at runtime and recording the provenance. It must not silently treat arbitrary unknown-unit masks as mm. Absolute affine determinants range from approximately 0.123176 to 7.153229 coordinate-units³ per voxel, median 0.340786; the mm³ interpretation is justified through the paired reference, not the mask header.

**ADC intensity stays in image-native units.** The release dictionary explicitly describes minimum, mean, median and percentile ADC values as raw units. Its ADC file definitions supply no physical intensity multiplier. Header slope/intercept are identity throughout; the mm/sec spatial/temporal header setting does not encode mm²/s intensity. No physical ADC conversion is established.

Image dimensions span axis-wise minima [118, 55, 22] and maxima [512, 512, 512]; these bounds need not describe any single image. Compressed files span approximately 0.47–49.96 MB for non-ADC images, 1.16–44.54 MB for ADC, and 0.029–2.04 MB for masks. Exact aggregate dimensions, sizes, unit counts and dictionary definitions are in `pcnsl/results/20261114-imaging-data/audit.aggregate.json`.

## Development selection

Before model results, a private manifest froze three patients using Python `random.Random(20261114).sample` from 150 sorted eligible patient/session paths. Eligibility requires exactly one FLAIR and one T1Post reference mask, all four image sequences in each space, and matching shapes/affines. Both reference spaces are retained for each selected patient. This is a development set, not an independent test set.

The manifest SHA256 is `824b40597664f4f776e1977020dda0b08b1334bfb71a426574be9d7b12f32042`. Its private case labels are development-01 through development-03. It is exclusive-created, checked on rerun, and never placed in Git. The seed and selection depend only on data availability/geometry, not model performance or mutation labels.

## Task boundaries

For segmentation, candidate-visible inputs should contain only the requested MRI images and the task specification. Reference masks, released feature tables, lesion counts/volumes, and derived radiomics remain evaluator-only. For a separate quantification task, providing a specified mask is appropriate because the question measures measurement execution rather than segmentation inference. Reports must distinguish these two input contracts.

Count distinct positive instance labels when the task requests the supplied mask's lesion count; do not silently replace it with a binary connected-component definition. If evaluating newly predicted binary masks, specify connectivity and any minimum-size filtering in advance. Volume uses foreground voxel count times the absolute spatial-affine determinant after validating spatial units; conversion to mL must follow those units, not assume all headers are millimetres. The full unit/label audit supplies the observed release coverage.

ADC summaries should apply the NIfTI scaling once and report image-native values unless documented intensity units support a physical conversion. Spatial units such as millimetres in `xyzt_units` do not establish ADC intensity units. A plausible numerical range or unitless slope of one is insufficient evidence for mm²/s or a fixed 10^-6 multiplier. Use the same-space ADC image and mask; report finite-value handling explicitly.

## Preprocessing provenance

The upstream public PyALFE source was inspected at commit `2e1a8ff6ebb6e1d3687aa98d0492a7a12beab52e` without installing it. Its [pipeline](https://github.com/reghbali/pyalfe/blob/2e1a8ff6ebb6e1d3687aa98d0492a7a12beab52e/pyalfe/pipeline.py) places skull stripping and cross-modality registration before lesion segmentation. Its [skull-stripping implementation](https://github.com/reghbali/pyalfe/blob/2e1a8ff6ebb6e1d3687aa98d0492a7a12beab52e/pyalfe/tasks/skullstripping.py) predicts a brain mask from the image and applies its largest component. Its [registration implementation](https://github.com/reghbali/pyalfe/blob/2e1a8ff6ebb6e1d3687aa98d0492a7a12beab52e/pyalfe/tasks/registration.py) registers skull-stripped images to the target image. Its [T1 preprocessing](https://github.com/reghbali/pyalfe/blob/2e1a8ff6ebb6e1d3687aa98d0492a7a12beab52e/pyalfe/tasks/t1_preprocessing.py) trims a brain-image component, rather than a supplied lesion mask.

Conversely, the [quantification code](https://github.com/reghbali/pyalfe/blob/2e1a8ff6ebb6e1d3687aa98d0492a7a12beab52e/pyalfe/tasks/quantification.py) deliberately uses lesion masks: relative signal divides lesion signal by non-lesion dominant-tissue signal, and ADC summaries are calculated within lesion voxels. Those released feature tables directly encode reference lesions and cannot be candidate segmentation inputs.

This is evidence about the inspected upstream implementation, not proof of the exact archive's generating version, configuration, manual edits or preprocessing history. The archive lacks a README and no exact preprocessing manifest/model checkpoint provenance has been established. No independent audit of other users' files, caches or training cohorts was performed. Public documentation distinguishes FLAIR and T1Post targets, but the exact annotation procedure and relation of this release's two target definitions remain unresolved.

Existing FAC tooling includes nibabel and SimpleITK; the inspected neuronetwork environment lacks nnUNetv2 and PyRadiomics. Pretrained segmentation tools need explicit checkpoint provenance, training-overlap disclosure and an isolated setup. No model installations or model calls occurred during this audit.

Upstream [model configuration](https://github.com/reghbali/pyalfe/blob/2e1a8ff6ebb6e1d3687aa98d0492a7a12beab52e/pyalfe/containers.py) does identify candidate tool interfaces: nnUNetv2 `Dataset500_FLAIR`, fold 4, takes FLAIR; `Dataset503_Enhancement`, fold 0, takes T1 and T1Post. Its inference wrapper requests `checkpoint_final.pth`, and its model source is `reghbali/pyalfe-models` on Hugging Face. These names were read from public code; no checkpoint was downloaded or inspected. They do not prove which weights generated the release annotations or whether the release patients were in training.
