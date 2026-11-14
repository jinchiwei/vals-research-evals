"""Bespoke figures for results/deck/COMPARISON.pptx (slate theme).

Reads ONLY existing result artifacts (read-only); writes figures + raw data
under results/deck/figures/. Run with PYTHONPATH containing matplotlib.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DECK = Path(__file__).resolve().parents[1]
RES = DECK.parent
sys.path.insert(0, str(Path.home() / ".claude/skills/_shared"))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle  # noqa: E402
from mpl_style import (apply_style, theme_colors, TURQUOISE, DEEPPINK, AMBER,  # noqa: E402
                       BLUEVIOLET, FONT_TITLE, FONT_BODY)

THEME = "slate"
T = theme_colors(THEME)
apply_style(THEME)
FIG = DECK / "figures"
RAW = FIG / "raw"
FIG.mkdir(exist_ok=True)
RAW.mkdir(exist_ok=True)

RUNS = {
    "v1 dev · seed 11": "20261113-opus55-dev-v1c",
    "v2 dev · seed 11": "20261113-opus55-workflow-dev",
    "v2 held-out · seed 101": "20261113-opus55-workflow-heldout",
}
FAM_COL = {"audit": TURQUOISE, "change": DEEPPINK, "reports": AMBER}


def jload(p):
    return json.loads(Path(p).read_text())


def run_results(run_dir):
    """summary.json if present, else completed per-case result.json files."""
    d = RES / run_dir
    if (d / "summary.json").exists():
        return jload(d / "summary.json")["results"], "summary.json"
    out = [jload(p) for p in sorted(d.glob("*/result.json"))]
    return out, f"{len(out)} per-case result.json (summary pending)"


def save(fig, name):
    fig.savefig(FIG / name, facecolor=T.canvas, dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)


def mono(ax, x, y, s, **kw):
    kw.setdefault("color", T.ink_text)
    return ax.text(x, y, s, fontfamily=FONT_TITLE, **kw)


def sans(ax, x, y, s, **kw):
    kw.setdefault("color", T.ink_text)
    return ax.text(x, y, s, fontfamily=FONT_BODY, **kw)


def panel_title(ax, s):
    ax.set_title(s, fontfamily=FONT_TITLE, color=T.ink_text, weight="bold", fontsize=13, loc="left", pad=10)


# ---------------------------------------------------------------- figure 1
def fig_candidates():
    v1 = RES / RUNS["v1 dev · seed 11"]
    a_fl = jload(v1 / "audit-1e59baa758d2/workspace/answer.json")["items"][0]
    a_cl = jload(v1 / "audit-bb4f631767c4/workspace/answer.json")["items"][0]
    ch = jload(v1 / "change-a17fef6551cb/workspace/answer.json")["items"]
    # graded-correct answers (score 1.0, tolerance 1e-4) stand in for gold here
    rep_in = jload(RES / RUNS["v2 dev · seed 11"] / "reports-bf388e3b4f69-workflow/workspace/input.json")
    docs = [r for r in rep_in["reports"] if r["subject"] == "R1"]
    rep_ans = [i for i in jload(RES / RUNS["v2 dev · seed 11"] / "reports-bf388e3b4f69-workflow/workspace/answer.json")["items"] if i["id"] == "R1"][0]
    raw = {"audit_flawed": a_fl, "audit_clean": a_cl, "change": ch, "reports_R1_docs": docs, "reports_R1_answer": rep_ans,
           "note": "Synthetic. Values are the agent's graded-correct answers (verifier tolerance 1e-4)."}
    (RAW / "fig_candidates.json").write_text(json.dumps(raw, indent=1))

    fig = plt.figure(figsize=(16.0, 5.0))
    gs = fig.add_gridspec(1, 3, width_ratios=[0.95, 0.95, 1.85], wspace=0.26)

    # A — audit
    ax = fig.add_subplot(gs[0])
    metrics = [("global", "global_auc"), ("protocol\nonly", "protocol_auc"), ("within\nprotocol", "controlled_auc")]
    w = 0.36
    for j, (lab, item, col) in enumerate([("flawed control", a_fl, DEEPPINK), ("clean control", a_cl, TURQUOISE)]):
        xs = [i + (j - 0.5) * w for i in range(3)]
        vals = [item[k] for _, k in metrics]
        ax.bar(xs, vals, width=w * 0.92, color=col, label=f"{lab} → {item['verdict']}", zorder=3)
        for x, v in zip(xs, vals):
            mono(ax, x, v + 0.012, f"{v:.2f}", ha="center", va="bottom", fontsize=8.8)
    ax.axhline(0.65, color=AMBER, lw=1.4, ls=(0, (4, 3)), zorder=4)
    sans(ax, 2.98, 0.655, "0.65 rule", color=AMBER, fontsize=9.5, ha="right", va="bottom")
    ax.set_xticks(range(3), [m for m, _ in metrics], fontsize=11)
    ax.set_ylim(0.4, 1.24)
    ax.set_xlim(-0.5, 3.0)
    ax.set_ylabel("AUC", fontsize=12)
    ax.tick_params(axis="y", labelsize=10)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", ncol=1, fontsize=10, frameon=False, borderaxespad=0.2, handlelength=1.2)
    panel_title(ax, "Audit · AUC by conditioning")

    # B — change
    ax = fig.add_subplot(gs[1])
    vcol = {"decline": DEEPPINK, "stable": TURQUOISE, "insufficient": AMBER}
    lo_lim, hi_lim = -0.40, 0.40
    for k, it in enumerate(ch):
        y = len(ch) - 1 - k
        lo, hi = it["slope"] - 1.96 * it["se"], it["slope"] + 1.96 * it["se"]
        c = vcol[it["verdict"]]
        ax.plot([max(lo, lo_lim), min(hi, hi_lim)], [y, y], color=c, lw=3, solid_capstyle="butt", zorder=3)
        if lo < lo_lim:
            ax.plot(lo_lim + 0.01, y, marker="<", color=c, ms=9, zorder=4)
        if hi > hi_lim:
            ax.plot(hi_lim - 0.01, y, marker=">", color=c, ms=9, zorder=4)
        if lo_lim < it["slope"] < hi_lim:
            ax.plot(it["slope"], y, "o", color=c, ms=8, zorder=5)
        mono(ax, hi_lim + 0.03, y, it["verdict"], color=c, fontsize=10.5, va="center")
    ax.axvline(-0.08, color=T.ink_text, lw=1.2, ls=(0, (4, 3)))
    sans(ax, -0.085, len(ch) - 0.45, "−0.08 /yr", fontsize=9.5, ha="right", color=T.ink_text)
    ax.set_yticks(range(len(ch)), [it["id"] for it in reversed(ch)], fontsize=11, fontfamily=FONT_TITLE)
    ax.set_xlim(lo_lim, hi_lim)
    ax.set_ylim(-0.6, len(ch) - 0.2)
    ax.set_xlabel("slope ± 1.96·se  (SD units / yr)", fontsize=11)
    ax.tick_params(axis="x", labelsize=10)
    ax.grid(axis="y", visible=False)
    panel_title(ax, "Change · calibrated slope")
    sans(ax, hi_lim, -0.5, "arrow = interval extends past axis", fontsize=9, color=T.muted_text, ha="right", va="bottom")

    # C — reports: one synthetic subject's document chain
    ax = fig.add_subplot(gs[2])
    ax.set_axis_off()
    panel_title(ax, "Reports · subject R1, requested finding: edema")
    order = ["late-0", "prior-0", "doc-770358", "doc-770358-addendum", "sinus-R1"]
    byid = {d["id"]: d for d in docs}
    ax.set_xlim(0, 13.6)
    ax.set_ylim(-1.25, len(order) + 0.15)
    mono(ax, 0.0, len(order) - 0.05, "exam / signed", fontsize=9.5, color=T.muted_text)
    mono(ax, 3.3, len(order) - 0.05, "document · text", fontsize=9.5, color=T.muted_text)
    for k, did in enumerate(order):
        d = byid[did]
        y = len(order) - 1 - k
        gold = did == rep_ans["source_id"]
        current_exam = d["exam_date"] == max(x["exam_date"] for x in docs)
        face = T.surface if not gold else TURQUOISE
        tc = T.ink_text if not gold else "#0B0B0F"
        ax.add_patch(FancyBboxPatch((3.15, y - 0.38), 10.45, 0.76, boxstyle="round,pad=0.0,rounding_size=0.08",
                                    fc=face, ec="none"))
        mono(ax, 0.0, y + 0.15, d["exam_date"], fontsize=9.6, va="center",
             color=(AMBER if current_exam else T.ink_text), weight=("bold" if current_exam else "normal"))
        mono(ax, 0.0, y - 0.18, "signed " + d["signed_at"][:10], fontsize=8.4, va="center")
        tag = d["type"] + (f" · applies_to: {', '.join(d['applies_to'])}" if d.get("applies_to") else "")
        mono(ax, 3.3, y + 0.16, f"{did}  ·  {tag}", fontsize=8.4, va="center", color=tc)
        sans(ax, 3.3, y - 0.17, d["text"], fontsize=9.2, va="center", color=tc)
    sans(ax, 0.0, -0.85, "amber = most recent exam date · filled = authoritative source\n"
         f"gold answer → status {rep_ans['status']}, change {rep_ans['change']}", fontsize=9.5, color=T.ink_text)
    save(fig, "fig_candidates.png")


# ---------------------------------------------------------------- figure 2
def fig_harness():
    v1 = jload(RES / "20261113-valkyrie-validation/validation.json")
    v2 = jload(RES / "20261113-valkyrie-v2-validation/validation.json")
    ok1 = sum(1 for t in v1["tasks"] if not t["problems"])
    ok2 = sum(1 for t in v2["tasks"] if not t["problems"])
    raw = {"v1_valid": ok1, "v1_total": len(v1["tasks"]), "v2_valid": ok2, "v2_total": len(v2["tasks"]),
           "cli": v1["cli"], "sdk": v1["sdk"], "hosted_run": [v1["hosted_run"], v2["hosted_run"]],
           "roundtrips": "12/12 per variant: scripts/verify_isolated.py on dist/development-v1b and dist/workflow-v2, re-run 2026-11-13 by deck agent"}
    (RAW / "fig_harness.json").write_text(json.dumps(raw, indent=1))

    fig, ax = plt.subplots(figsize=(15.2, 5.4))
    ax.set_axis_off()
    ax.set_xlim(0, 30)
    ax.set_ylim(0, 11)

    def box(x, y, w, h, head, body, col, dashed=False, fill=None):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.25",
                                    fc=(fill or T.surface), ec=(col if dashed else "none"),
                                    lw=1.6, ls=((0, (5, 3)) if dashed else "-")))
        ax.add_patch(Rectangle((x, y + h - 0.16), w, 0.16, fc=col, ec="none"))
        mono(ax, x + 0.3, y + h - 0.55, head, fontsize=12.5, weight="bold", color=col, va="top")
        sans(ax, x + 0.3, y + h - 1.35, body, fontsize=10.8, va="top", linespacing=1.45)

    def arrow(x0, y0, x1, y1, col=T.ink_text, dashed=False):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=18,
                                     color=col, lw=1.8, ls=((0, (4, 3)) if dashed else "-")))

    box(0.2, 1.2, 5.6, 8.9, "generator", "seeded synthetic cases\n3 families\ndev seeds 11 / 23 / 37\nheld-out seed 101\n\nv2 workflow adds:\ncohort joins, exclusions,\nlabel revisions, mixed\nunits, age norms,\nfinding-specific addenda", TURQUOISE)
    arrow(5.9, 5.7, 6.8, 5.7)
    # task folder with sub-compartments
    ax.add_patch(FancyBboxPatch((6.9, 1.2), 7.3, 8.9, boxstyle="round,pad=0,rounding_size=0.25", fc=T.surface, ec="none"))
    ax.add_patch(Rectangle((6.9, 9.94), 7.3, 0.16, fc=BLUEVIOLET, ec="none"))
    mono(ax, 7.2, 9.55, "Harbor task folder", fontsize=12.5, weight="bold", color=BLUEVIOLET, va="top")
    comps = [("instruction.md + environment/", "agent-visible: Dockerfile, input.json", TURQUOISE),
             ("tests/", "hidden verifier + expected.json", DEEPPINK),
             ("solution/", "reference oracle (solve.sh)", AMBER)]
    for k, (h, b, c) in enumerate(comps):
        y = 7.0 - k * 2.0
        ax.add_patch(FancyBboxPatch((7.2, y), 6.7, 1.65, boxstyle="round,pad=0,rounding_size=0.15", fc=T.canvas, ec=c, lw=1.4))
        mono(ax, 7.45, y + 1.15, h, fontsize=10, color=c, va="center", weight="bold")
        sans(ax, 7.45, y + 0.5, b, fontsize=10.2, va="center")
    # branches
    arrow(14.3, 7.8, 15.4, 8.3)
    arrow(14.3, 3.6, 15.4, 2.9)
    box(15.5, 6.0, 7.2, 4.6, "local tool-agent pilot",
        "bubblewrap sandbox · Read/Write/Edit/Bash\nno repo, generator, grader or key\nclaude-opus-5-5 · effort high\n240 s and $3 cap per task", TURQUOISE)
    box(15.5, 0.5, 7.2, 4.6, "Valkyrie SDK · offline",
        f"CLI {v1['cli']} · SDK {v1['sdk']}\nvalidate + pack, no upload\nv1: {ok1}/{len(v1['tasks'])} tasks · v2: {ok2}/{len(v2['tasks'])} tasks\noracle ↔ verifier roundtrip 12/12 each", AMBER)
    arrow(22.8, 8.3, 24.0, 8.3)
    box(24.1, 6.0, 5.7, 4.6, "graded trace", "answer.json + analysis.py\nverifier tol 1e-4\nmodel IDs, tool calls,\nusage, est. cost", DEEPPINK)
    arrow(22.8, 2.8, 24.0, 2.8, col=DEEPPINK, dashed=True)
    box(24.1, 0.5, 5.7, 4.6, "hosted Valkyrie run", "NOT RUN\nneeds event account,\nModal + provider key", DEEPPINK, dashed=True, fill=T.canvas)
    save(fig, "fig_harness.png")


# ---------------------------------------------------------------- figure 3
def fig_scores():
    ctrl = jload(RES / "20261113-controls-v1/summary.json")
    rows, sources = [], {}
    for it in ctrl["iterations"]:
        rows.append({"label": f"scripted · {it['strategy']}", "group": "control",
                     **{f: it["families"][f] for f in ("audit", "change", "reports")},
                     "resolved": sum(c["resolved"] for c in it["cases"]), "n": len(it["cases"])})
    for lab, rd in RUNS.items():
        res, src = run_results(rd)
        sources[lab] = src
        fam = {}
        for r in res:
            fam.setdefault(r["family"], []).append(r["score"])
        rows.append({"label": f"Opus 5.5 · {lab}", "group": "model",
                     **{f: (sum(v) / len(v) if (v := fam.get(f)) else None) for f in ("audit", "change", "reports")},
                     "resolved": sum(bool(r["resolved"]) for r in res), "n": len(res),
                     "models": sorted({m for r in res for m in r["actual_models"]})})
    (RAW / "fig_scores.json").write_text(json.dumps({"rows": rows, "sources": sources,
        "excluded": ["20261113-opus55-dev-v1 (bwrap read-only fs; 0 model calls)",
                     "20261113-opus55-dev-v1b (API unreachable EAI_AGAIN; model '<synthetic>', 0 tokens)"]}, indent=1))

    fig, ax = plt.subplots(figsize=(11.6, 5.6))
    ax.set_axis_off()
    cols = ["audit", "change", "reports", "resolved"]
    cx = [6.2, 8.1, 10.0, 12.2]
    n = len(rows)
    ax.set_xlim(0, 13.4)
    ax.set_ylim(-2.4, n + 0.6)
    for j, c in enumerate(cols):
        mono(ax, cx[j], n + 0.05, c, ha="center", fontsize=12, weight="bold",
             color=(FAM_COL.get(c, T.ink_text)))
    for i, r in enumerate(rows):
        y = n - 1 - i - (0.35 if r["group"] == "model" else 0)
        mono(ax, 0.0, y, r["label"], fontsize=11.5, va="center",
             color=(T.ink_text if r["group"] == "model" else T.muted_text))
        for j, f in enumerate(cols[:3]):
            v = r[f]
            col = FAM_COL[f]
            alpha = 0.25 + 0.75 * v
            ax.add_patch(FancyBboxPatch((cx[j] - 0.8, y - 0.36), 1.6, 0.72,
                                        boxstyle="round,pad=0,rounding_size=0.1",
                                        fc=col, alpha=(alpha if r["group"] == "model" else alpha * 0.55), ec="none"))
            mono(ax, cx[j], y, f"{v:.2f}", ha="center", va="center", fontsize=12, weight="bold",
                 color=("#0B0B0F" if v >= 0.5 else T.ink_text))
        mono(ax, cx[3], y, f"{r['resolved']}/{r['n']}", ha="center", va="center", fontsize=12.5,
             weight="bold", color=(T.ink_text if r["group"] == "model" else T.muted_text))
    ysep = n - 3 - 0.67
    ax.plot([0, 13.2], [ysep + 0.0, ysep + 0.0], color=T.rule, lw=1.2)
    sans(ax, 0.0, n - 0.35 + 0.05, "", fontsize=1)
    sans(ax, 0.0, -1.6, "Excluded from model accuracy (0 model tokens): v1 sandbox start failure (read-only fs) ·\n"
         "v1b API unreachable (EAI_AGAIN, model '<synthetic>').  Scripted rows: dev seeds 11/23/37, 12 cases, not LLMs.",
         fontsize=10, color=T.ink_text, va="center", linespacing=1.5)
    save(fig, "fig_scores.png")
    return rows, sources


# ---------------------------------------------------------------- figure 4
def fig_effort():
    import os
    case_key = {"audit-1e59baa758d2": ("audit · flawed", 0), "audit-bb4f631767c4": ("audit · clean", 1),
                "audit-feea1196a0ff": ("audit · flawed", 0), "audit-71637c50833e": ("audit · clean", 1),
                "change-a17fef6551cb": ("change", 2), "change-cf1e4a6527ec": ("change", 2),
                "reports-bf388e3b4f69": ("reports", 3), "reports-bfa707df367c": ("reports", 3)}
    recs = []
    for k, (lab, rd) in enumerate(RUNS.items()):
        res, _ = run_results(rd)
        for r in res:
            base = r["case"].replace("-workflow", "")
            ws = RES / rd / r["case"] / "workspace"
            verdict = None
            if base.startswith("audit"):
                verdict = jload(ws / "answer.json")["items"][0]["verdict"]
            name = case_key[base][0]
            if base.startswith("audit"):
                name = "audit · flawed" if verdict == "unsupported" else "audit · clean"
            recs.append({"run": lab, "run_i": k, "case": r["case"], "slot": name, "score": r["score"],
                         "input_kb": os.path.getsize(ws / "input.json") / 1024,
                         "analysis_lines": len((ws / "analysis.py").read_text().splitlines()),
                         "output_tokens": r["usage"]["output_tokens"], "elapsed_s": r["elapsed_seconds"],
                         "tool_calls": len(r["tools_used"]), "cost_usd": r["cost_usd"]})
    (RAW / "fig_effort.json").write_text(json.dumps(recs, indent=1))
    slots = [("audit · flawed", TURQUOISE, "-"), ("audit · clean", TURQUOISE, (0, (3, 2))),
             ("change", DEEPPINK, "-"), ("reports", AMBER, "-")]
    panels = [("input_kb", "input.json size (KB)", True), ("analysis_lines", "analysis.py lines", False),
              ("output_tokens", "output tokens", False), ("elapsed_s", "wall-clock (s)", False)]
    fig, axes = plt.subplots(1, 4, figsize=(15.2, 4.9))
    for ax, (key, lab, logy) in zip(axes, panels):
        for s, c, ls in slots:
            pts = sorted([(r["run_i"], r[key]) for r in recs if r["slot"] == s])
            if not pts:
                continue
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=c, ls=ls, lw=2.2, marker="o", ms=7, label=s)
        if logy:
            ax.set_yscale("log")
        ax.set_xticks(range(len(RUNS)), ["v1\ndev", "v2\ndev", "v2\nheld-out"], fontsize=11)
        ax.set_xlim(-0.3, len(RUNS) - 0.7)
        ax.tick_params(axis="y", labelsize=10.5)
        ax.grid(axis="x", visible=False)
        ax.set_title(lab, fontfamily=FONT_TITLE, color=T.ink_text, weight="bold", fontsize=12.5, loc="left")
    axes[0].legend(loc="upper center", bbox_to_anchor=(2.35, -0.2), ncol=4, fontsize=11, frameon=False)
    fig.subplots_adjust(wspace=0.32)
    save(fig, "fig_effort.png")
    return recs


# ---------------------------------------------------------------- figure 5
def fig_next():
    fig, ax = plt.subplots(figsize=(9.6, 5.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.set_xlabel("evidence-chain length  →", fontsize=12)
    ax.set_ylabel("specification gap  →", fontsize=12)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(T.muted_text)
    ax.add_patch(Rectangle((0.2, 0.2), 4.1, 3.4, fc=T.surface, ec="none"))
    mono(ax, 0.45, 3.35, "tested · 12/12 solved", fontsize=10, color=T.ink_text, weight="bold", va="top")
    pts = [(1.2, 1.4, "v1", TURQUOISE), (3.0, 2.2, "v2 workflow", DEEPPINK)]
    for x, y, s, c in pts:
        ax.plot(x, y, "o", color=c, ms=13, zorder=4)
        mono(ax, x, y - 0.45, s, fontsize=10.5, ha="center", va="top", color=c)
    ax.add_patch(FancyArrowPatch((1.4, 1.5), (2.82, 2.12), arrowstyle="-|>", mutation_scale=14, color=T.ink_text, lw=1.3))
    cands = [(2.4, 8.0, "repair an underspecified\nanalysis repository", AMBER),
             (7.9, 2.55, "reconcile much longer\nevidence chains", BLUEVIOLET),
             (7.6, 8.0, "both axes", T.muted_text)]
    for x, y, s, c in cands:
        ax.plot(x, y, "o", ms=16, mfc="none", mec=c, mew=2.2, zorder=4)
        below = c == BLUEVIOLET
        mono(ax, x if below else x + 0.4, y - 0.5 if below else y, s, fontsize=10.5, ha=("center" if below else "left"),
             va=("top" if below else "center"), color=(c if c != T.muted_text else T.ink_text))
    for x, y in [(2.42, 7.55), (7.5, 2.55)]:
        ax.add_patch(FancyArrowPatch((2.98, 2.5) if x < 5 else (3.35, 2.22), (x, y), arrowstyle="-|>", mutation_scale=16,
                                     color=T.ink_text, lw=1.4, ls=(0, (4, 3))))
    sans(ax, 9.8, 9.6, "illustrative positioning · not measured", fontsize=9.5, ha="right", va="top", color=T.muted_text)
    save(fig, "fig_next.png")


if __name__ == "__main__":
    fig_candidates()
    fig_harness()
    rows, sources = fig_scores()
    recs = fig_effort()
    fig_next()
    print(json.dumps({"sources": sources, "rows": rows}, indent=1))
