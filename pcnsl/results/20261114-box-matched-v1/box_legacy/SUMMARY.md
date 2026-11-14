# PCNSL tabular development prototype

internal-development-only; not public-release verified; no live frontier trial

AUROC / Brier, averaged over 3 fixed repetitions. Folds per target: {"IRF4": 4, "KMT2D": 5, "PRKDC": 5, "MYD88": 5, "CD79B": 5, "ZFHX3": 5, "LRP1B": 5, "BTG1": 5, "ETV6": 5, "CDKN2A": 5, "PRDM1": 5, "TP53": 5}. Fixed baselines, not frontier agents.

| Gene | Positive / N | age_sex_logreg | spatial_age_logreg | spatial_age_sex_logreg | spatial_random_forest |
|---|---:|---:|---:|---:|---:|
| IRF4 | 4 / 33 | 0.813 / 0.197 | 0.819 / 0.149 | 0.899 / 0.114 | 0.779 / 0.113 |
| KMT2D | 13 / 33 | 0.272 / 0.290 | 0.381 / 0.358 | 0.360 / 0.359 | 0.421 / 0.277 |
| PRKDC | 12 / 33 | 0.279 / 0.272 | 0.452 / 0.294 | 0.426 / 0.304 | 0.554 / 0.246 |
| MYD88 | 25 / 33 | 0.422 / 0.270 | 0.650 / 0.228 | 0.643 / 0.221 | 0.503 / 0.225 |
| CD79B | 11 / 33 | 0.361 / 0.282 | 0.661 / 0.242 | 0.631 / 0.252 | 0.474 / 0.254 |
| ZFHX3 | 8 / 33 | 0.830 / 0.173 | 0.557 / 0.289 | 0.532 / 0.289 | 0.608 / 0.203 |
| LRP1B | 11 / 33 | 0.325 / 0.281 | 0.503 / 0.319 | 0.477 / 0.330 | 0.386 / 0.271 |
| BTG1 | 9 / 33 | 0.230 / 0.286 | 0.395 / 0.336 | 0.369 / 0.346 | 0.157 / 0.300 |
| ETV6 | 8 / 33 | 0.620 / 0.228 | 0.403 / 0.334 | 0.525 / 0.304 | 0.465 / 0.230 |
| CDKN2A | 18 / 33 | 0.251 / 0.292 | 0.409 / 0.339 | 0.353 / 0.374 | 0.256 / 0.299 |
| PRDM1 | 7 / 33 | 0.136 / 0.306 | 0.515 / 0.287 | 0.482 / 0.305 | 0.394 / 0.215 |
| TP53 | 6 / 33 | 0.391 / 0.278 | 0.239 / 0.320 | 0.270 / 0.308 | 0.317 / 0.206 |

- Historically analyzed cohort: these are development CV results, not new external validation.
- Repeated folds are correlated. Ranges describe split sensitivity, not confidence intervals.
- No permutation tests or multiplicity correction in this quick prototype.
- Balanced logistic regression is a discrimination baseline; probabilities may be miscalibrated.
- No automatic post-hoc probability flipping or winner-based gene selection.
- Agent input and private truth must be isolated before evaluating untrusted agents.
