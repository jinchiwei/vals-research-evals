# Spleen segmentation and volumetry from abdominal CT

## Why this matters

Spleen volume is the measurement behind several clinical decisions: confirming
splenomegaly, following portal hypertension and haematological disease, and judging
response to treatment in myelofibrosis, where a 35 % fall in spleen volume is the usual
response criterion. Measuring it by hand means outlining the organ on every slice,
which takes a radiologist several minutes per scan. We want an automatic tool that
returns a spleen mask a reader can check, and a volume in millilitres they can put in
the report, within a few minutes of the scan arriving.

You are building that tool. There is no pretrained medical model in this environment
and no internet. You have the scientific Python stack in `/opt/benchmark-venv`
(numpy, scipy, scikit-image, SimpleITK, nibabel, scikit-learn, pandas{{TORCH_LINE}})
and a handful of labelled scans.

## Data

`/workspace/data/dev/<case>/` holds {{N_DEV}} contrast-enhanced abdominal CT scans
(portal-venous phase) with expert spleen masks:

- `image.nii.gz`: CT in Hounsfield units, int16, RAS orientation, units mm.
- `label.nii.gz`: uint8, 1 = spleen, 0 = everything else, on the same grid.

What you should know about the scans:

- Slice thickness varies from 1.5 to 8 mm between scans; in-plane pixels are about
  0.6 to 1 mm. Voxels are far from isotropic.
- Each scan has been cropped in-plane to the patient's body outline with a margin,
  to remove the table and air. All slices are kept. The hidden scans were cropped by
  the same rule. The crop does not centre on the spleen.
- Spleen sizes in the development cases run from about 90 to 300 mL. Real patients,
  including the hidden ones, can have larger or smaller spleens.
- Contrast timing varies, so spleen attenuation differs from scan to scan.

`/workspace/data/dev/volumes.csv` lists the reference spleen volume of each
development case, computed as voxel count times voxel volume.

## What to deliver

Leave a self-contained pipeline in `/workspace/output/pipeline/` with an entry point

```
bash /workspace/output/pipeline/run.sh INPUT_DIR OUTPUT_DIR
```

`INPUT_DIR` contains exactly one file, `image.nii.gz`, in the same format as the
development images. Your pipeline must write:

1. `OUTPUT_DIR/mask.nii.gz`: the spleen mask, values 0 and 1 only, **on the input
   grid** (same shape and the same affine as `image.nii.gz`, spatial units mm).
2. `OUTPUT_DIR/volume.json`: `{"spleen_volume_ml": <number>}`, the spleen volume in
   millilitres. It must agree with your own mask: voxel count times voxel volume,
   within 1 % (or 0.5 mL for tiny masks). A volume in voxels or in mm³ is wrong.

Rules for the pipeline:

- It runs with no network, as an unprivileged user, with `/opt/benchmark-venv/bin`
  first on `PATH` and a fresh empty `HOME`. It may use only that Python environment
  and files inside `/workspace/output/pipeline/`. Anything you installed or cached
  elsewhere will not exist when it is graded.
- **Time limit: {{LIMIT}} seconds per scan**, wall clock, on {{CPUS}} CPU cores and
  {{MEM_GB}} GB RAM, no GPU. The grader times each scan itself; anything your
  pipeline reports about its own timing is ignored.
- Keep `/workspace/output` under 500 MB in total.
- You may put your own predictions for development cases in
  `/workspace/output/visible_predictions/` for reference. They are not scored.

## How it is scored

After you finish, the grader runs your pipeline once on each of several hidden scans
that you never see, from the same source and prepared the same way.

Per scan:

- **Dice overlap** with the expert mask.
- **Volume error**: (your volume − reference volume) / reference volume.
- **Boundary**: normalised surface distance at 2 mm and 95th-percentile Hausdorff
  distance in mm are reported, not thresholded.
- A scan is **clinically acceptable** if Dice ≥ 0.94 **and** the absolute volume
  error is ≤ 10 %, the outputs are valid, and it finished within the time limit.
  These limits come from published reader agreement for spleen outlining on CT: a
  second expert reader reaches about 0.96 Dice and 4 % volume difference.

A scan's output is **invalid** if a file is missing, the mask is not on the input
grid, the mask holds values other than 0 and 1, or the volume is not a finite number
consistent with the mask in mL.

The headline score is the fraction of hidden scans that are clinically acceptable,
counted only if every hidden scan ran, produced valid output and finished in time.
Mean Dice and a comparison with a specialist segmentation tool are also recorded.

Test your pipeline end to end on the development cases the way the grader will run
it, including the time limit, before you finish.
