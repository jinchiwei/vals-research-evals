# Cached TabPFN public-release pilot

The SCS offline run completed successfully using the existing conda environment and a local TabPFN v2.5 checkpoint. No model download or authenticated TabPFN service was used. All 64 patients, 439 full features, fixed five-fold patient splits, and six-significant-digit inputs match the direct-model experiment. The sex-only control uses the same folds.

| Gene | TabPFN full OOF AUROC | TabPFN fold-0 AUROC | Logistic full OOF AUROC | TabPFN sex-only OOF AUROC |
|---|---:|---:|---:|---:|
| MYD88 | 0.420 | 0.433 | 0.562 | 0.481 |
| CD79B | 0.386 | 0.639 | 0.347 | 0.493 |

TabPFN package/checkpoint settings:

```json
{
  "model": "tabpfn.TabPFNClassifier",
  "other_parameters": "package defaults",
  "random_state": 20261114,
  "device": "cpu",
  "checkpoint_file": "tabpfn-v2.5-classifier-v2.5_default.ckpt",
  "checkpoint_sha256": "5d7170e2d3af01f9c501bb09ec3bd12e9944f8604de18002c647873c6ec04a12",
  "offline": true,
  "missing_values": "passed as NaN",
  "hyperparameter_search": false
}
```

Versions: {"tabpfn": "8.0.2"}. Torch/runtime provenance and source hashes are in each report.

These results do not establish a robust attainable signal for these two endpoints. The CD79B fold-0 result is not representative of its full cross-validation result. Do not compare a single-fold frontier score with a pooled baseline, infer invalid labels, flip predictions, or call this a demonstrated frontier-specific deficit. The fixed checkpoint and feature configuration are one comparator, not an exhaustive optimized reproduction of the historical internal pipeline.
