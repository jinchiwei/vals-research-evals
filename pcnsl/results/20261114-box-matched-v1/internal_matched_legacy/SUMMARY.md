# PCNSL tabular development prototype

internal-development-only; not public-release verified; no live frontier trial

AUROC / Brier, averaged over 3 fixed repetitions. Folds per target: {"IRF4": 4, "KMT2D": 5, "PRKDC": 5, "MYD88": 5, "CD79B": 5, "ZFHX3": 5, "LRP1B": 5, "BTG1": 5, "ETV6": 5, "CDKN2A": 5, "PRDM1": 5, "TP53": 5}. Fixed baselines, not frontier agents.

| Gene | Positive / N | age_sex_logreg | spatial_age_logreg | spatial_age_sex_logreg | spatial_random_forest |
|---|---:|---:|---:|---:|---:|
| IRF4 | 4 / 33 | 0.813 / 0.197 | 0.836 / 0.147 | 0.899 / 0.111 | 0.756 / 0.115 |
| KMT2D | 13 / 33 | 0.272 / 0.290 | 0.379 / 0.359 | 0.358 / 0.359 | 0.446 / 0.273 |
| PRKDC | 12 / 33 | 0.279 / 0.272 | 0.442 / 0.294 | 0.421 / 0.304 | 0.528 / 0.250 |
| MYD88 | 25 / 33 | 0.422 / 0.270 | 0.653 / 0.226 | 0.650 / 0.220 | 0.495 / 0.225 |
| CD79B | 11 / 33 | 0.361 / 0.282 | 0.646 / 0.248 | 0.618 / 0.258 | 0.461 / 0.256 |
| ZFHX3 | 8 / 33 | 0.830 / 0.173 | 0.555 / 0.289 | 0.540 / 0.289 | 0.602 / 0.206 |
| LRP1B | 11 / 33 | 0.325 / 0.281 | 0.490 / 0.323 | 0.470 / 0.335 | 0.394 / 0.268 |
| BTG1 | 9 / 33 | 0.230 / 0.286 | 0.404 / 0.334 | 0.378 / 0.343 | 0.139 / 0.308 |
| ETV6 | 8 / 33 | 0.620 / 0.228 | 0.402 / 0.335 | 0.518 / 0.307 | 0.483 / 0.225 |
| CDKN2A | 18 / 33 | 0.251 / 0.292 | 0.430 / 0.336 | 0.362 / 0.370 | 0.237 / 0.304 |
| PRDM1 | 7 / 33 | 0.136 / 0.306 | 0.491 / 0.297 | 0.452 / 0.314 | 0.407 / 0.214 |
| TP53 | 6 / 33 | 0.391 / 0.278 | 0.233 / 0.314 | 0.259 / 0.305 | 0.305 / 0.209 |

- Historically analyzed cohort: these are development CV results, not new external validation.
- Repeated folds are correlated. Ranges describe split sensitivity, not confidence intervals.
- No permutation tests or multiplicity correction in this quick prototype.
- Balanced logistic regression is a discrimination baseline; probabilities may be miscalibrated.
- No automatic post-hoc probability flipping or winner-based gene selection.
- Agent input and private truth must be isolated before evaluating untrusted agents.
