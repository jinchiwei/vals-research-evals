# PCNSL tabular development prototype

internal-development-only; not public-release verified; no live frontier trial

AUROC / Brier, averaged over 3 fixed repetitions. Folds per target: {"IRF4": 2, "KMT2D": 5, "MYD88": 5, "CD79B": 5, "BTG1": 4, "ETV6": 3, "CDKN2A": 5, "PRDM1": 4, "TP53": 3}. Fixed baselines, not frontier agents.

| Gene | Positive / N | age_sex_logreg | spatial_age_logreg | spatial_age_sex_logreg | spatial_random_forest |
|---|---:|---:|---:|---:|---:|
| IRF4 | 2 / 33 | 0.774 / 0.198 | 0.349 / 0.179 | 0.435 / 0.166 | 0.597 / 0.093 |
| KMT2D | 10 / 33 | 0.348 / 0.291 | 0.529 / 0.285 | 0.519 / 0.297 | 0.433 / 0.246 |
| MYD88 | 24 / 33 | 0.562 / 0.254 | 0.597 / 0.252 | 0.625 / 0.261 | 0.492 / 0.230 |
| CD79B | 9 / 33 | 0.316 / 0.281 | 0.556 / 0.261 | 0.540 / 0.280 | 0.415 / 0.248 |
| BTG1 | 4 / 33 | 0.305 / 0.271 | 0.517 / 0.190 | 0.480 / 0.206 | 0.520 / 0.142 |
| ETV6 | 3 / 33 | 0.700 / 0.225 | 0.581 / 0.182 | 0.711 / 0.140 | 0.667 / 0.104 |
| CDKN2A | 17 / 33 | 0.227 / 0.288 | 0.338 / 0.351 | 0.306 / 0.380 | 0.273 / 0.308 |
| PRDM1 | 4 / 33 | 0.172 / 0.257 | 0.638 / 0.201 | 0.506 / 0.207 | 0.273 / 0.150 |
| TP53 | 3 / 33 | 0.289 / 0.277 | 0.652 / 0.138 | 0.641 / 0.139 | 0.711 / 0.091 |

- Historically analyzed cohort: these are development CV results, not new external validation.
- Repeated folds are correlated. Ranges describe split sensitivity, not confidence intervals.
- No permutation tests or multiplicity correction in this quick prototype.
- Balanced logistic regression is a discrimination baseline; probabilities may be miscalibrated.
- No automatic post-hoc probability flipping or winner-based gene selection.
- Agent input and private truth must be isolated before evaluating untrusted agents.
