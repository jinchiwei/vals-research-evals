# Fixed logistic-regression permutation check

FAC CPU job **3067976 completed (0:0)** in 40 seconds. The frozen all-feature logistic pipeline was refit on 199 patient-label permutations per gene, including recomputing the same stratified split procedure each time. This null calibrates logistic regression only.

| Gene | Observed pooled AUROC | One-sided AUROC p | One-sided Brier p |
|---|---:|---:|---:|
| MYD88 | 0.562 | 0.270 | 0.395 |
| CD79B | 0.347 | 0.940 | 0.985 |

Plus-one permutation p-values include ties and have minimum 0.005. These are unadjusted across two genes and two metrics. Neither gene provides evidence of better-than-null performance for this fixed LR configuration. This does not prove absence of biological signal or invalidate genetic labels; it does not test the other models against their own nulls. No additional model API calls occurred. Full null distributions, settings and hashes are in result.aggregate.json.
