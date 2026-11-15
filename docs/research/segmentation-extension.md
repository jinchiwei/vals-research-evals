# Segmentation extension: feasibility before scored expansion

Jin asked to include tumor segmentation on 2026-11-14. Keep the real tabular prediction pilot running while auditing this upstream task.

## Available evidence

The [official registry](https://registry.opendata.aws/ucsf-pcnsl/) describes expert-annotated lesion segmentations for 150 PCNSL MRI patients. The [official tutorial](https://github.com/rauschecker-sugrue-labs/UCSF-PCNSL) identifies the distributed images as processed derivatives, with sequences registered into FLAIR and T1Post reference spaces and connected-component lesion masks. The verified local archive has 300 mask files; these are not 300 independent patients. Exact annotation/review protocol and distinctions between reference-space masks require further audit.

## Proposed tasks

1. **MRI to mask:** an agent receives sanitized MRI volumes, a documented output contract and an offline toolbox, then generates a segmentation in the required reference space. Grade mask validity, Dice, lesion-level sensitivity/false positives and volume error; surface distances require correct physical voxel spacing and explicit empty-mask handling. Do not define a success threshold after seeing model scores.
2. **Mask to features:** from a supplied reference mask, the agent computes a frozen set of imaging features. Check feature definitions, alignment and agreement with independently reproduced reference computations; released numbers alone may not reproduce without exact preprocessing/version information.
3. **End-to-end prediction:** compare mutation prediction from reference-mask features against agent-mask features, holding patient splits, feature extractor and downstream predictor fixed. Report each stage separately so loss of segmentation quality is not mistaken for inability to learn mutation biology.

The comparator is a declared fixed segmentation tool, while the evaluated system is the frontier agent plus the same available tools. Any model whose training set includes these patients is unsuitable for claiming generalization on them; disclose overlap or use independently held-out cases. Training a new segmentation model from scratch is outside the initial hackathon pilot.

## Gates before launch

- Verify reference target definition (enhancing tumor, FLAIR abnormality, or another compartment), annotation provenance and expert review.
- Check image/mask geometry and whether distributed preprocessing used lesion labels in a way that leaks the target (mask-guided crop/normalization/skull stripping).
- Exclude reference masks, mask-derived statistics, labels, originals IDs and identifying metadata from agent-visible test inputs; scrub NIfTI textual headers/extensions while preserving valid spatial geometry.
- Keep both reference spaces and all lesions for each patient in the same split.
- Select a small fixed development set without choosing on model failures. Score untouched held-out cases only after freezing task/tool versions.
- Prepare checkpoint dependencies offline; document GPU/CPU memory and wall-time limits and distinguish tool availability errors from segmentation errors.
- Run through Harbor/Valkyrie with trusted hidden-label verification. No hosted execution is claimed yet.

This extension is scientifically more interpretable than demanding accurate mutation prediction without establishing signal: segmentation has an anatomical reference, and the downstream comparison can localize error propagation. It still needs measured frontier results to establish difficulty.
