# PCNSL tabular development prototype

internal-development-only; not public-release verified; no live frontier trial

AUROC / Brier, averaged over three fixed 5-fold repetitions. These are fixed baselines, not frontier agents.

| Gene | Positive / N | Age+sex LR | Spatial+age LR | Spatial+age+sex LR | All LR | All RF |
|---|---:|---:|---:|---:|---:|---:|
| IRF4 | 5 / 40 | 0.823 / 0.178 | 0.750 / 0.162 | 0.823 / 0.129 | 0.707 / 0.116 | 0.777 / 0.105 |
| KMT2D | 17 / 40 | 0.302 / 0.279 | 0.244 / 0.370 | 0.240 / 0.374 | 0.322 / 0.551 | 0.362 / 0.273 |
| PRKDC | 13 / 40 | 0.406 / 0.260 | 0.406 / 0.296 | 0.428 / 0.294 | 0.328 / 0.475 | 0.261 / 0.283 |
| MYD88 | 30 / 40 | 0.334 / 0.273 | 0.458 / 0.285 | 0.452 / 0.281 | 0.282 / 0.413 | 0.359 / 0.230 |
| CD79B | 14 / 40 | 0.518 / 0.264 | 0.543 / 0.285 | 0.560 / 0.292 | 0.552 / 0.332 | 0.462 / 0.257 |
| ZFHX3 | 11 / 40 | 0.692 / 0.229 | 0.474 / 0.295 | 0.442 / 0.306 | 0.357 / 0.413 | 0.346 / 0.246 |
| LRP1B | 12 / 40 | 0.258 / 0.287 | 0.493 / 0.294 | 0.447 / 0.315 | 0.483 / 0.365 | 0.511 / 0.223 |
| BTG1 | 12 / 40 | 0.351 / 0.274 | 0.423 / 0.314 | 0.391 / 0.334 | 0.447 / 0.417 | 0.533 / 0.232 |
| ETV6 | 10 / 40 | 0.614 / 0.237 | 0.476 / 0.292 | 0.571 / 0.268 | 0.573 / 0.265 | 0.460 / 0.221 |
| CDKN2A | 21 / 40 | 0.319 / 0.273 | 0.555 / 0.283 | 0.551 / 0.292 | 0.355 / 0.493 | 0.440 / 0.280 |
| PRDM1 | 9 / 40 | 0.266 / 0.276 | 0.502 / 0.296 | 0.438 / 0.326 | 0.643 / 0.222 | 0.553 / 0.184 |
| TP53 | 6 / 40 | 0.430 / 0.268 | 0.289 / 0.275 | 0.291 / 0.269 | 0.320 / 0.226 | 0.211 / 0.170 |

- Historically analyzed cohort: these are development CV results, not new external validation.
- Repeated folds are correlated. Ranges describe split sensitivity, not confidence intervals.
- No permutation tests or multiplicity correction in this quick prototype.
- Balanced logistic regression is a discrimination baseline; probabilities may be miscalibrated.
- No automatic post-hoc probability flipping or winner-based gene selection.
- Agent input and private truth must be isolated before evaluating untrusted agents.
