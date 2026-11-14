# PCNSL tabular development prototype

internal-development-only; not public-release verified; no live frontier trial

AUROC / Brier, averaged over 3 fixed repetitions. Folds per target: {"IRF4": 4, "KMT2D": 5, "PRKDC": 5, "MYD88": 5, "CD79B": 5, "ZFHX3": 5, "LRP1B": 5, "BTG1": 5, "ETV6": 5, "CDKN2A": 5, "PRDM1": 5, "TP53": 5}. Fixed baselines, not frontier agents.

| Gene | Positive / N | age_sex_logreg | spatial_age_logreg | spatial_age_sex_logreg | spatial_random_forest |
|---|---:|---:|---:|---:|---:|
| IRF4 | 4 / 33 | 0.782 / 0.185 | 0.779 / 0.163 | 0.830 / 0.138 | 0.701 / 0.131 |
| KMT2D | 13 / 33 | 0.283 / 0.295 | 0.401 / 0.336 | 0.365 / 0.354 | 0.371 / 0.288 |
| PRKDC | 12 / 33 | 0.266 / 0.275 | 0.508 / 0.282 | 0.479 / 0.292 | 0.489 / 0.259 |
| MYD88 | 25 / 33 | 0.473 / 0.266 | 0.677 / 0.214 | 0.690 / 0.207 | 0.565 / 0.206 |
| CD79B | 11 / 33 | 0.380 / 0.267 | 0.646 / 0.240 | 0.624 / 0.250 | 0.519 / 0.237 |
| ZFHX3 | 8 / 33 | 0.827 / 0.178 | 0.615 / 0.238 | 0.600 / 0.243 | 0.707 / 0.181 |
| LRP1B | 11 / 33 | 0.408 / 0.271 | 0.534 / 0.298 | 0.523 / 0.305 | 0.455 / 0.262 |
| BTG1 | 9 / 33 | 0.221 / 0.281 | 0.438 / 0.312 | 0.390 / 0.329 | 0.194 / 0.282 |
| ETV6 | 8 / 33 | 0.628 / 0.227 | 0.438 / 0.303 | 0.547 / 0.283 | 0.505 / 0.218 |
| CDKN2A | 18 / 33 | 0.314 / 0.275 | 0.485 / 0.317 | 0.460 / 0.329 | 0.289 / 0.292 |
| PRDM1 | 7 / 33 | 0.214 / 0.283 | 0.610 / 0.249 | 0.573 / 0.261 | 0.568 / 0.188 |
| TP53 | 6 / 33 | 0.465 / 0.262 | 0.321 / 0.306 | 0.329 / 0.290 | 0.344 / 0.193 |

- Historically analyzed cohort: these are development CV results, not new external validation.
- Repeated folds are correlated. Ranges describe split sensitivity, not confidence intervals.
- No permutation tests or multiplicity correction in this quick prototype.
- Balanced logistic regression is a discrimination baseline; probabilities may be miscalibrated.
- No automatic post-hoc probability flipping or winner-based gene selection.
- Agent input and private truth must be isolated before evaluating untrusted agents.
