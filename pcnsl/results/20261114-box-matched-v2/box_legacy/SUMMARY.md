# PCNSL tabular development prototype

internal-development-only; not public-release verified; no live frontier trial

AUROC / Brier, averaged over 3 fixed repetitions. Folds per target: {"IRF4": 4, "KMT2D": 5, "PRKDC": 5, "MYD88": 5, "CD79B": 5, "ZFHX3": 5, "LRP1B": 5, "BTG1": 5, "ETV6": 5, "CDKN2A": 5, "PRDM1": 5, "TP53": 5}. Fixed baselines, not frontier agents.

| Gene | Positive / N | age_sex_logreg | spatial_age_logreg | spatial_age_sex_logreg | spatial_random_forest |
|---|---:|---:|---:|---:|---:|
| IRF4 | 4 / 33 | 0.782 / 0.185 | 0.773 / 0.167 | 0.830 / 0.141 | 0.701 / 0.130 |
| KMT2D | 13 / 33 | 0.283 / 0.295 | 0.408 / 0.333 | 0.373 / 0.350 | 0.354 / 0.292 |
| PRKDC | 12 / 33 | 0.266 / 0.275 | 0.508 / 0.284 | 0.485 / 0.294 | 0.487 / 0.259 |
| MYD88 | 25 / 33 | 0.473 / 0.266 | 0.673 / 0.216 | 0.685 / 0.208 | 0.563 / 0.208 |
| CD79B | 11 / 33 | 0.380 / 0.267 | 0.661 / 0.234 | 0.632 / 0.242 | 0.514 / 0.240 |
| ZFHX3 | 8 / 33 | 0.827 / 0.178 | 0.628 / 0.238 | 0.603 / 0.244 | 0.670 / 0.186 |
| LRP1B | 11 / 33 | 0.408 / 0.271 | 0.547 / 0.292 | 0.536 / 0.299 | 0.456 / 0.263 |
| BTG1 | 9 / 33 | 0.221 / 0.281 | 0.435 / 0.311 | 0.394 / 0.328 | 0.210 / 0.278 |
| ETV6 | 8 / 33 | 0.628 / 0.227 | 0.442 / 0.300 | 0.558 / 0.279 | 0.513 / 0.221 |
| CDKN2A | 18 / 33 | 0.314 / 0.275 | 0.463 / 0.318 | 0.441 / 0.330 | 0.319 / 0.288 |
| PRDM1 | 7 / 33 | 0.214 / 0.283 | 0.628 / 0.244 | 0.588 / 0.256 | 0.566 / 0.190 |
| TP53 | 6 / 33 | 0.465 / 0.262 | 0.307 / 0.316 | 0.321 / 0.298 | 0.333 / 0.195 |

- Historically analyzed cohort: these are development CV results, not new external validation.
- Repeated folds are correlated. Ranges describe split sensitivity, not confidence intervals.
- No permutation tests or multiplicity correction in this quick prototype.
- Balanced logistic regression is a discrimination baseline; probabilities may be miscalibrated.
- No automatic post-hoc probability flipping or winner-based gene selection.
- Agent input and private truth must be isolated before evaluating untrusted agents.
