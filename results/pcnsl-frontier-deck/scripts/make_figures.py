"""Figures for the PCNSL frontier deck.

Measured figures read aggregate JSON only (pilot summaries, hosted aggregate
inventory). Schematic figures carry a visible "SCHEMATIC" tag. No patient-level
records are read.

Usage: python make_figures.py REPO_ROOT OUT_DIR
"""
import glob
import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, Rectangle

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

for f in glob.glob(os.path.expanduser("~/.local/share/fonts/superstack-geist/*.ttf")):
    font_manager.fontManager.addfont(f)
plt.rcParams.update({
    "font.family": "Geist", "font.size": 13, "axes.edgecolor": "#BBBBBB",
    "axes.labelcolor": "#14141C", "xtick.color": "#555560", "ytick.color": "#555560",
    "figure.dpi": 200, "savefig.dpi": 200, "savefig.bbox": "tight", "savefig.pad_inches": 0.12,
})
INK, MUTED, DIM, RULE, PAPER = "#14141C", "#555560", "#888888", "#DDDDDD", "#F4F4F7"
VIOLET, TEAL, PINK, AMBER = "#8A2BE2", "#1AA89A", "#FF1493", "#F0C840"
MONO = "Geist Mono"
MODEL_COLOR = {"claude": VIOLET, "codex": TEAL}
provenance = {"figures": {}}


def tag(ax, text="SCHEMATIC — not measured data", x=0.0, y=1.0):
    ax.text(x, y, text, transform=ax.transAxes, fontsize=10, family=MONO,
            color=PINK, ha="left", va="bottom", fontweight="bold")


def box(ax, x, y, w, h, fc, ec=None, lw=0, r=0.02):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec or fc, lw=lw))


# ---------------------------------------------------------------- 1 credit matrix
def credit_matrix():
    fig, ax = plt.subplots(figsize=(8.2, 5.6))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    tag(ax, y=1.01)
    cells = [
        (0.18, 0.50, "Valid analysis\nstrong signal", "FULL CREDIT", "#E6F6F4", TEAL),
        (0.59, 0.50, "Valid analysis\nnull / inconclusive", "FULL CREDIT", "#E6F6F4", TEAL),
        (0.18, 0.07, "Leaked split / wrong\nendpoint, high AUROC", "FAIL", "#FFE8F3", PINK),
        (0.59, 0.07, "Invalid analysis\nweak result", "FAIL", "#FFE8F3", PINK),
    ]
    for x, y, body, verdict, fc, ec in cells:
        box(ax, x, y, 0.39, 0.39, fc, ec, 2)
        ax.text(x + 0.195, y + 0.25, body, ha="center", va="center", fontsize=15, color=INK)
        ax.text(x + 0.195, y + 0.08, verdict, ha="center", va="center", fontsize=14,
                family=MONO, fontweight="bold", color=ec)
    ax.text(0.375, 0.93, "Biological signal present", ha="center", fontsize=12, color=MUTED)
    ax.text(0.785, 0.93, "Little / no signal", ha="center", fontsize=12, color=MUTED)
    ax.text(0.15, 0.695, "Valid\nresearch\nartifact", ha="right", va="center", fontsize=12, color=MUTED)
    ax.text(0.15, 0.265, "Invalid\nresearch\nartifact", ha="right", va="center", fontsize=12, color=MUTED)
    fig.savefig(OUT / "fig_credit_matrix.png"); plt.close(fig)
    provenance["figures"]["fig_credit_matrix.png"] = "schematic; scoring principle from docs/research/benchmark-design.md"


# ---------------------------------------------------------------- 2 hosted counts
def hosted_counts():
    inv = json.loads((REPO / "pcnsl/results/20261114-hosted-release/aggregate_inventory.json").read_text())
    counts = inv["cohort_coverage"]["complete_spatial_one_sample_gene_counts"]
    genes = ["MYD88", "CDKN2A", "CD79B", "CARD11", "BTG1", "IRF4"]
    n = 63
    any_l = [counts[g]["any_listed"] for g in genes]
    rep = [counts[g]["reported_pathogenic"] for g in genes]
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    y = range(len(genes))
    h = 0.36
    ax.barh([i - h / 2 - 0.02 for i in y], any_l, height=h, color="#B9B9C4", label="Any listed variant row")
    ax.barh([i + h / 2 + 0.02 for i in y], rep, height=h, color=VIOLET, label="Reported qualifying alteration")
    for i, (a, r) in enumerate(zip(any_l, rep)):
        ax.text(a + 0.6, i - h / 2 - 0.02, str(a), va="center", fontsize=12, color=MUTED)
        ax.text(r + 0.6, i + h / 2 + 0.02, str(r), va="center", fontsize=12, color=INK, fontweight="bold")
    ax.set_yticks(list(y)); ax.set_yticklabels(genes, family=MONO, fontsize=13)
    ax.invert_yaxis(); ax.set_xlim(0, n)
    ax.axvline(n, color=RULE, lw=1)
    ax.set_xlabel(f"Patients with a record (of {n} with genomic records + FLAIR summary)", fontsize=12)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color="#EEEEEE"); ax.set_axisbelow(True)
    ax.legend(loc="lower right", frameon=False, fontsize=12)
    ax.set_title("Hosted v1.0 aggregate inventory — patient counts, not wild-type calls",
                 fontsize=13, color=INK, loc="left")
    fig.savefig(OUT / "fig_hosted_counts.png"); plt.close(fig)
    provenance["figures"]["fig_hosted_counts.png"] = {
        "measured_source": "pcnsl/results/20261114-hosted-release/aggregate_inventory.json:cohort_coverage.complete_spatial_one_sample_gene_counts",
        "values": {g: counts[g] for g in genes}}


# ---------------------------------------------------------------- 3 mechanism map
GROUPS = [
    ("Identity &\nchronology", ["B01", "B02", "B06", "B07"]),
    ("Genomic endpoint\n& denominators", ["B03", "B04", "B05", "B20"]),
    ("Geometry\n& units", ["B09", "B10", "B11", "B12", "B25"]),
    ("Leakage &\nselection", ["B08", "B13", "B14", "B22"]),
    ("Statistical\ninference", ["B15", "B16", "B17", "B18", "B19", "B21"]),
    ("Claim validity &\nreproducibility", ["B23", "B24", "B26", "B27", "B28", "B29", "B30"]),
]
EXERCISED = {  # author's mapping from task protocol text (repair_evals/cases.py, integrated.py)
    "B02": "endpoint", "B03": "endpoint", "B04": "endpoint", "B06": "endpoint",
    "B08": "claims", "B13": "claims", "B14": "claims", "B15": "claims", "B16": "claims",
    "B17": "claims", "B18": "claims", "B09": "geometry", "B10": "geometry", "B11": "geometry",
    "B01": "integrated", "B28": "replay", "B29": "clean ctrl",
}


def mechanism_map():
    fig, ax = plt.subplots(figsize=(12.4, 5.4))
    ax.set_xlim(0, 6); ax.set_ylim(-0.25, 9.3); ax.axis("off")
    tag(ax, "SCHEMATIC — author's mapping of protocol text; exercised ≠ failing", y=1.0)
    for gi, (label, ids) in enumerate(GROUPS):
        x = gi + 0.05
        ax.text(x + 0.45, 8.45, label, ha="center", va="center", fontsize=14, color=INK, fontweight="bold")
        for j, b in enumerate(ids):
            yy = 7.0 - j * 1.02
            ex = b in EXERCISED
            box(ax, x, yy, 0.9, 0.84, "#EFE3FB" if ex else "white", VIOLET if ex else "#C8C8D0", 1.6, r=0.06)
            ax.text(x + 0.07, yy + 0.42, b, va="center", fontsize=15, family=MONO,
                    color=VIOLET if ex else DIM, fontweight="bold")
            ax.text(x + 0.84, yy + 0.42, EXERCISED.get(b, "proposed"), va="center", ha="right",
                    fontsize=11.5, color=INK if ex else DIM)
    n_ex = len(EXERCISED)
    ax.text(0.05, -0.25, f"Filled: required by an executable task protocol ({n_ex}/30); all such tasks were passed by both tested models.   "
            f"Outline: proposed only ({30 - n_ex}/30).", fontsize=12.5, color=MUTED)
    fig.savefig(OUT / "fig_mechanism_map.png"); plt.close(fig)
    provenance["figures"]["fig_mechanism_map.png"] = {
        "type": "schematic", "catalog": "docs/research/benchmark-design.md B01-B30",
        "grouping_and_exercised_mapping": "author's judgement from repair_evals/cases.py and integrated.py protocol text",
        "exercised": EXERCISED}


# ---------------------------------------------------------------- 4 eval protocol
def eval_protocol():
    fig, ax = plt.subplots(figsize=(12.6, 4.6))
    ax.set_xlim(0, 12.6); ax.set_ylim(0, 4.6); ax.axis("off")
    tag(ax, "SCHEMATIC — local isolated runner, not a Valkyrie execution", y=0.99)
    steps = [
        (0.1, "Synthetic repo\n+ frozen protocol", "flawed or clean\nvariant; invented\nrecords only", "#F4F4F7", MUTED),
        (2.65, "Frontier agent", "Claude Opus 5.5 /\nGPT-6 Astra, high;\n600 s; tools on", "#EFE3FB", VIOLET),
        (5.2, "Submitted\nprogram", "patched code;\nno answers\nvisible to agent", "#F4F4F7", MUTED),
        (7.75, "Hidden replay", "4 new synthetic\ncohorts, verifier-\nonly fixtures", "#E6F6F4", TEAL),
        (10.3, "Attempt verdict", "pass only if\nall 4 fixtures\nmatch reference", "#FFF6D6", "#B8920A"),
    ]
    for x, title, body, fc, ec in steps:
        box(ax, x, 1.15, 2.2, 2.85, fc, ec, 1.8, r=0.08)
        ax.text(x + 1.1, 3.45, title, ha="center", va="center", fontsize=13, fontweight="bold", color=INK)
        ax.text(x + 1.1, 2.05, body, ha="center", va="center", fontsize=12, color=MUTED)
    for x in (2.33, 4.88, 7.43, 9.98):
        ax.annotate("", xy=(x + 0.3, 2.57), xytext=(x, 2.57),
                    arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.8, mutation_scale=16))
    ax.text(6.3, 0.55, "Flawed repo → must repair the mechanism, not the visible symptom.     "
            "Clean repo → must not damage valid behavior.", ha="center", fontsize=12.5, color=INK)
    ax.text(6.3, 0.12, "1 attempt = 1 agent run.  4 fixtures = 4 replays of that one submission — not 4 attempts, not patients.",
            ha="center", fontsize=12, color=PINK, fontweight="bold")
    fig.savefig(OUT / "fig_eval_protocol.png"); plt.close(fig)
    provenance["figures"]["fig_eval_protocol.png"] = "schematic; harness from scripts/run_repair_pilot.py manifests (timeout 600 s, effort high)"


# ---------------------------------------------------------------- 5 pilot results
def load_attempts():
    """Collect aggregate attempt records. Priority: results/20261114-repair-pilots/*.json,
    then exp/.../summary.json for runs not already present."""
    rows, seen = [], set()
    sources = sorted(glob.glob(str(REPO / "results/20261114-repair-pilots/pilot-*.json")))
    for src in sources:
        try:
            d = json.loads(Path(src).read_text())
        except Exception:
            continue
        if not isinstance(d, dict) or "results" not in d:
            continue
        status = d.get("snapshot_status", "")
        variant = d.get("manifest", {}).get("variant")
        seed = d.get("manifest", {}).get("seed")
        for r in d["results"]:
            key = (r["id"], r["backend"], r.get("variant", variant))
            if key in seen:
                continue
            seen.add(key)
            rows.append({**r, "variant": r.get("variant", variant), "seed": r.get("seed", seed), "source": os.path.relpath(src, REPO),
                         "exploratory": "Exploratory" in status})
    return rows


def pilot_results():
    rows = load_attempts()
    fam_order = {"endpoint": 0, "claims": 1, "geometry": 2, "integrated": 3}
    rows.sort(key=lambda r: (fam_order.get(r["family"], 9), r["variant"] != "flawed", r.get("seed") or 0, r["backend"] != "claude"))
    have_valid = any(r["family"] == "integrated" and r["variant"] == "valid" for r in rows)
    display = list(rows)
    if not have_valid:
        for b in ("claude", "codex"):
            display.append({"family": "integrated", "variant": "valid", "backend": b, "pending": True, "seed": 11})
    n = len(display)
    row_h = 0.52
    W, H = 7.4, row_h * n + 0.95
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
    x_fam, x_model, x_sq, sq, gap, x_ver = 2.55, 2.7, 4.35, 0.36, 0.08, 6.2
    top = H - 0.55
    ax.text(x_sq, top + 0.12, "hidden fixtures", fontsize=12, color=MUTED, family=MONO)
    ax.text(x_ver, top + 0.12, "result", fontsize=12, color=MUTED, family=MONO)
    last_fam = None
    for i, r in enumerate(display):
        y = top - row_h * (i + 0.5)
        if r["family"] == "endpoint":
            fam = "endpoint*"
        elif r["family"] != "integrated":
            fam = r["family"]
        elif r["variant"] != "flawed":
            fam = "integr. clean"
        elif r.get("seed") not in (None, 11):
            fam = f"integr. seed {r['seed']}"
        else:
            fam = "integrated"
        if fam != last_fam:
            ax.text(x_fam, y - row_h / 2, fam, ha="right", va="center", fontsize=16, color=INK)
            if i:
                ax.plot([0.05, W - 0.05], [y + row_h / 2, y + row_h / 2], color="#E4E4EA", lw=0.8)
            last_fam = fam
        name = {"claude": "Opus 5.5", "codex": "GPT-6 Astra"}[r["backend"]]
        c = MODEL_COLOR[r["backend"]]
        ax.text(x_model, y, name, ha="left", va="center", fontsize=15, color=c, fontweight="bold")
        for k in range(4):
            x = x_sq + k * (sq + gap)
            if r.get("pending"):
                ax.add_patch(Rectangle((x, y - sq / 2), sq, sq, fc="white", ec="#BBBBBB", lw=1.2, hatch="///"))
            else:
                ok = r["replay"]["checks"][k]["passed"] if k < len(r["replay"]["checks"]) else False
                ax.add_patch(Rectangle((x, y - sq / 2), sq, sq, fc=c if ok else "white", ec=c if ok else PINK, lw=1.5))
        verdict = "pending" if r.get("pending") else ("PASS" if r["classification"] == "pass" else r["classification"].upper())
        ax.text(x_ver, y, verdict, ha="left", va="center", fontsize=15, family=MONO,
                color=DIM if r.get("pending") else INK, fontweight="bold")
    ax.text(0.05, 0.12, "1 row = 1 agent attempt · seed 11 unless noted · *exploratory (generator changed)",
            fontsize=11.5, color=MUTED)
    fig.savefig(OUT / "fig_pilot_results.png"); plt.close(fig)
    provenance["figures"]["fig_pilot_results.png"] = {
        "type": "measured", "attempts": [
            {k: r.get(k) for k in ("id", "family", "variant", "seed", "backend", "requested_model", "observed_model_ids",
                                   "classification", "elapsed_seconds", "source", "exploratory")}
            | ({"fixtures": f"{r['replay']['passed_fixtures']}/{r['replay']['total_fixtures']}"} if not r.get("pending") else {"pending": True})
            for r in display]}
    return display


# ---------------------------------------------------------------- 6 endpoint schematic
def endpoint_schematic():
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 3.0))
    specs = [("Legacy “any listed” label", 4, 4), ("“Reported pathogenic” label", 2, 2)]
    for ax, (title, pos, folds) in zip(axes, specs):
        ax.set_xlim(0, 11); ax.set_ylim(-0.9, 3.9); ax.axis("off"); ax.set_aspect("equal")
        for i in range(33):
            cx, cy = 0.5 + (i % 11) * 1.0, 3.0 - (i // 11) * 1.0
            ax.add_patch(plt.Circle((cx, cy), 0.36, fc=PINK if i < pos else "#D8D8DE", ec="none"))
        ax.text(0, 3.75, title, fontsize=14, fontweight="bold", color=INK)
        ax.text(0, 0.05, f"IRF4 positives: {pos} of 33  ·  CV folds: {folds}", fontsize=14, color=INK, family=MONO)
        ax.text(0, -0.5, "Same 33 patients, different label definition", fontsize=12.5, color=MUTED)
    axes[0].text(0, 4.45, "SCHEMATIC layout of measured counts (historical 33-patient Box subset; IRF4)",
                 fontsize=10, family=MONO, color=PINK, fontweight="bold")
    fig.text(0.5, 0.06, "AUROCs under the two labels are not a controlled comparison; neither establishes useful mutation prediction.",
             ha="center", fontsize=12, color=INK)
    fig.savefig(OUT / "fig_endpoint_schematic.png"); plt.close(fig)
    provenance["figures"]["fig_endpoint_schematic.png"] = {
        "type": "schematic layout of measured counts",
        "source": "pcnsl/results/20261114-box-matched-v2/REPORT.md (IRF4: legacy 4/33, 4 folds; reported-pathogenic 2/33, 2 folds)"}


# ---------------------------------------------------------------- 7 hosted-release baseline (measured)
def hosted_baseline():
    src = "pcnsl/results/20261114-hosted-release/baseline.aggregate.json"
    agg = json.loads((REPO / src).read_text())
    seeds = agg["design"]["seeds"]
    by = {}
    for r in agg["runs"]:
        by.setdefault((r["gene"], r["baseline"]), {})[r["seed"]] = r
    genes = ["MYD88", "CD79B"]
    fig, ax = plt.subplots(figsize=(11.6, 3.9))
    fig.subplots_adjust(left=0.20, right=0.70, top=0.84, bottom=0.30)
    ax.set_xlim(0.38, 0.75); ax.set_ylim(-0.6, 1.6)
    ax.axvline(0.5, color="#AAAAB4", lw=1.2, ls=(0, (4, 3)), zorder=1)
    summary = {}
    for gi, g in enumerate(genes):
        y = 1 - gi
        lr = [by[(g, "spatial_logreg")][s]["pooled_oof_auroc"] for s in seeds]
        pv = [by[(g, "training_prevalence")][s]["pooled_oof_auroc"] for s in seeds]
        r0 = by[(g, "spatial_logreg")][seeds[0]]
        mean, lo, hi = sum(lr) / len(lr), min(lr), max(lr)
        summary[g] = {"spatial_logreg_by_seed": dict(zip(map(str, seeds), [round(v, 4) for v in lr])),
                      "mean": round(mean, 4), "seed_range": [round(lo, 4), round(hi, 4)],
                      "training_prevalence_by_seed": dict(zip(map(str, seeds), [round(v, 4) for v in pv])),
                      "positive": r0["positive"], "no_qualifying_report": r0["no_qualifying_report"],
                      "patients": r0["patients"]}
        yl, yp = y + 0.14, y - 0.24
        ax.plot([lo, hi], [yl, yl], color=VIOLET, lw=2.4, solid_capstyle="round", zorder=2)
        ax.scatter(lr, [yl] * 3, s=90, color=VIOLET, edgecolor="white", linewidth=1.6, zorder=3)
        ax.plot([mean, mean], [yl - 0.17, yl + 0.17], color=INK, lw=2.2, zorder=4)
        ax.scatter(pv, [yp] * 3, s=80, marker="D", color="#9A9AA6", edgecolor="white", linewidth=1.4, zorder=3)
        ax.text(-0.02, y, g, transform=ax.get_yaxis_transform(), ha="right", va="bottom", fontsize=17,
                family=MONO, fontweight="bold", color=INK)
        ax.text(-0.02, y - 0.04, f"{r0['positive']} qualifying /\n{r0['no_qualifying_report']} no qualifying report",
                transform=ax.get_yaxis_transform(), ha="right", va="top", fontsize=11.5, color=MUTED)
        ax.text(1.02, yl, f"mean {mean:.4f}  ·  seed range {lo:.4f}–{hi:.4f}", transform=ax.get_yaxis_transform(),
                ha="left", va="center", fontsize=13, color=INK, fontweight="bold")
        ax.text(1.02, yp, f"prevalence control {pv[0]:.4f} (all seeds)", transform=ax.get_yaxis_transform(),
                ha="left", va="center", fontsize=12, color=MUTED)
    ax.set_yticks([])
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color="#EEEEEE"); ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelsize=12)
    ax.set_xlabel("Pooled out-of-fold AUROC (internal 5-fold CV; dashed line = 0.5)", fontsize=12.5, labelpad=6)
    ax.text(0.0, 1.06, "MEASURED — hosted v1.0 release only · 63 patients · one dot per prespecified seed "
            f"({', '.join(map(str, seeds))})", transform=ax.transAxes, fontsize=10.5, family=MONO, color=MUTED,
            fontweight="bold", ha="left", va="bottom")
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker="o", color=VIOLET, lw=2.4, markersize=9, markeredgecolor="white",
                      label="Spatial logistic regression (C=1)"),
               Line2D([], [], marker="D", color="#9A9AA6", lw=0, markersize=8, markeredgecolor="white",
                      label="Training-prevalence control"),
               Line2D([], [], color=INK, lw=2.2, label="Mean of 3 seeds")]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.19, -0.02), ncol=3, frameon=False, fontsize=11.5)
    fig.savefig(OUT / "fig_hosted_baseline.png"); plt.close(fig)
    provenance["figures"]["fig_hosted_baseline.png"] = {
        "type": "measured", "source": src, "design": agg["design"],
        "excluded_targets": agg["excluded_targets"], "values": summary,
        "note": "Seed range summarizes three correlated runs; it is not a confidence interval. No score flipping."}


credit_matrix(); hosted_counts(); mechanism_map(); eval_protocol(); attempts = pilot_results(); endpoint_schematic()
hosted_baseline()
(OUT / "figures_provenance.json").write_text(json.dumps(provenance, indent=2))
print(json.dumps({k: (v if isinstance(v, str) else v.get("type", "measured")) for k, v in provenance["figures"].items()}, indent=1))
