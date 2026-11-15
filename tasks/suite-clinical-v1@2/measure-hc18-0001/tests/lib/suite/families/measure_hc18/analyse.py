"""Aggregate statistics for comparators on hidden cases: bootstrap CIs, Bland-Altman, paired test.

Usage: python -I analyse.py DATA_ROOT NAME [NAME2]
Writes aggregates only to split/analysis.json.
"""
import json, sys
from pathlib import Path
import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
root, names = Path(sys.argv[1]), sys.argv[2:]
rng = np.random.default_rng(20261114)
out = json.loads((HERE / "split" / "analysis.json").read_text()) if (HERE / "split" / "analysis.json").exists() else {}
per = {}
for n in names:
    m = json.loads((root / "comparators" / n / "metrics.json").read_text())
    pc = sorted(m["per_case"], key=lambda p: p["case_id"])
    per[n] = pc
    err = np.array([p["err_mm"] if p["valid"] else np.nan for p in pc])
    within = np.array([p["within_tol"] for p in pc], float)
    ae = np.abs(err)
    B = rng.integers(0, len(pc), (5000, len(pc)))
    d = err[~np.isnan(err)]
    out[n] = {"n": len(pc),
              "mae_mm": float(np.nanmean(ae)), "mae_ci95": np.percentile(np.nanmean(ae[B], 1), [2.5, 97.5]).tolist(),
              "frac_within": float(within.mean()),
              "frac_within_ci95": np.percentile(within[B].mean(1), [2.5, 97.5]).tolist(),
              "bland_altman": {"bias_mm": float(d.mean()), "sd_mm": float(d.std(ddof=1)),
                               "loa_mm": [float(d.mean() - 1.96 * d.std(ddof=1)), float(d.mean() + 1.96 * d.std(ddof=1))]},
              "pct_err_abs_median": float(np.nanmedian(ae / np.array([p["ref_mm"] for p in pc]) * 100)),
              "n_gross_errors_gt_20mm": int(np.nansum(ae > 20))}
if len(names) == 2:
    a, b = (np.array([abs(p["err_mm"]) for p in per[n]]) for n in names)
    wa, wb = (np.array([p["within_tol"] for p in per[n]]) for n in names)
    out[f"paired_{names[0]}_vs_{names[1]}"] = {
        "wilcoxon_abs_err_p": float(stats.wilcoxon(a, b).pvalue),
        "mcnemar_discordant": [int((wa & ~wb).sum()), int((~wa & wb).sum())],
        "mcnemar_exact_p": float(stats.binomtest(int((wa & ~wb).sum()), int((wa != wb).sum())).pvalue) if (wa != wb).any() else 1.0}
(HERE / "split" / "analysis.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out, indent=1))
