# PCNSL tabular development prototype

internal-development-only; not public-release verified; no live frontier trial

AUROC / Brier, averaged over 3 fixed repetitions. Folds per target: {"IRF4": 2, "KMT2D": 5, "MYD88": 5, "CD79B": 5, "BTG1": 4, "ETV6": 3, "CDKN2A": 5, "PRDM1": 4, "TP53": 3}. Fixed baselines, not frontier agents.

| Gene | Positive / N | age_sex_logreg | spatial_age_logreg | spatial_age_sex_logreg | spatial_random_forest |
|---|---:|---:|---:|---:|---:|
| IRF4 | 2 / 33 | 0.737 / 0.182 | 0.398 / 0.082 | 0.634 / 0.080 | 0.782 / 0.070 |
| KMT2D | 10 / 33 | 0.378 / 0.283 | 0.517 / 0.286 | 0.514 / 0.301 | 0.417 / 0.240 |
| MYD88 | 24 / 33 | 0.509 / 0.257 | 0.637 / 0.240 | 0.642 / 0.238 | 0.448 / 0.241 |
| CD79B | 9 / 33 | 0.284 / 0.279 | 0.528 / 0.283 | 0.515 / 0.300 | 0.392 / 0.250 |
| BTG1 | 4 / 33 | 0.319 / 0.269 | 0.267 / 0.225 | 0.264 / 0.238 | 0.382 / 0.156 |
| ETV6 | 3 / 33 | 0.700 / 0.204 | 0.689 / 0.163 | 0.796 / 0.126 | 0.767 / 0.090 |
| CDKN2A | 17 / 33 | 0.283 / 0.279 | 0.314 / 0.389 | 0.265 / 0.424 | 0.328 / 0.309 |
| PRDM1 | 4 / 33 | 0.351 / 0.293 | 0.339 / 0.277 | 0.342 / 0.281 | 0.230 / 0.173 |
| TP53 | 3 / 33 | 0.367 / 0.259 | 0.511 / 0.148 | 0.519 / 0.147 | 0.520 / 0.119 |

- Historically analyzed cohort: these are development CV results, not new external validation.
- Repeated folds are correlated. Ranges describe split sensitivity, not confidence intervals.
- No permutation tests or multiplicity correction in this quick prototype.
- Balanced logistic regression is a discrimination baseline; probabilities may be miscalibrated.
- No automatic post-hoc probability flipping or winner-based gene selection.
- Agent input and private truth must be isolated before evaluating untrusted agents.
