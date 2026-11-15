"""Figures for results/suite-deck/CLINICAL_SUITE.pptx (slate theme).

Reads only docs/research/suite/hosted-agents2.json (hosted run 2, suite/clinical-v1@2,
instructions v3). Writes slate-canvas PNGs to results/suite-deck/figures/ and the
exact values plotted to figures/raw/*.json. No number is computed beyond counts and
means over values already in the JSON.

Run: ~/miniconda3/envs/vals-suite/bin/python results/suite-deck/src/make_figs.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DECK = Path(__file__).resolve().parents[1]
REPO = DECK.parents[1]
sys.path.insert(0, str(Path.home() / ".claude/skills/_shared"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from mpl_style import (AMBER, BLUEVIOLET, DEEPPINK, FONT_BODY, FONT_TITLE,  # noqa: E402
                       TURQUOISE, apply_style, theme_colors)

THEME = "slate"
T = theme_colors(THEME)
apply_style(THEME)
plt.rcParams.update({"font.size": 13, "axes.labelsize": 13, "xtick.labelsize": 12,
                     "ytick.labelsize": 12, "legend.fontsize": 12,
                     "legend.facecolor": T.canvas, "legend.edgecolor": T.canvas})
FIG = DECK / "figures"
RAW = FIG / "raw"
FIG.mkdir(exist_ok=True)
RAW.mkdir(exist_ok=True)

SRC = REPO / "docs/research/suite/hosted-agents2.json"
H2 = json.loads(SRC.read_text())
OPUS, SONNET = "anthropic/claude-opus-5-5", "anthropic/claude-sonnet-5-5"
COL = {OPUS: TURQUOISE, SONNET: DEEPPINK, "spec": AMBER}
NAME = {OPUS: "Opus 5.5", SONNET: "Sonnet 5.5", "spec": "Specialist"}
ORDER = ["reg_resect", "seg_spleen", "measure_hc18", "ecg_ptbxl", "risk_icu"]
TITLE = {"reg_resect": "MRI→US registration", "seg_spleen": "CT spleen mask + volume",
         "measure_hc18": "Fetal head circumference", "ecg_ptbxl": "12-lead ECG classes",
         "risk_icu": "ICU mortality risk"}
# Agent session limits in minutes (task timeouts; hosted-agents2.md "Prespecified design",
# hosted-agents1.md "Timeouts": ecg 1800 s, reg/hc18/icu 2700 s, spleen 3600 s).
SESSION_MIN = {"reg_resect": 45, "seg_spleen": 60, "measure_hc18": 45, "ecg_ptbxl": 30, "risk_icu": 45}


def att(fam, model):
    return next(a for a in H2["attempts"] if a["family"] == fam and a["model"] == model)


def save(fig, name, raw):
    fig.savefig(FIG / name, facecolor=T.canvas, dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    (RAW / (Path(name).stem + ".json")).write_text(json.dumps(raw, indent=1))


def mono(ax, x, y, s, **kw):
    kw.setdefault("color", T.ink_text)
    return ax.text(x, y, s, fontfamily=FONT_TITLE, **kw)


def style_ax(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(T.rule)
    ax.tick_params(colors=T.muted_text)
    ax.set_facecolor(T.canvas)


# ------------------------------------------------------------------ 1. task contract diagram
def fig_contract():
    fig, ax = plt.subplots(figsize=(13.0, 3.6))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 3.6)
    ax.axis("off")
    boxes = [
        (0.05, "AGENT WORKSPACE", "clinical README\ndev cases with\nreference answers", TURQUOISE),
        (2.70, "CLAUDE CODE", "30–60 min session\nmodel API only\none attempt", TURQUOISE),
        (5.35, "PIPELINE", "run.sh IN OUT\nself-contained\nruns offline", AMBER),
        (8.00, "VERIFIER", "hidden cases\nno network\nclinical time limit", DEEPPINK),
        (10.65, "CLINICAL SCORE", "mm · mL · risk\nvs clinical bar\nvs specialist", BLUEVIOLET),
    ]
    w, h, y = 2.30, 2.55, 0.55
    for x, head, body, c in boxes:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    facecolor=T.surface, edgecolor=c, linewidth=2.2))
        ax.add_patch(plt.Rectangle((x, y + h - 0.12), w, 0.12, facecolor=c, edgecolor="none"))
        mono(ax, x + w / 2, y + h - 0.45, head, ha="center", va="center", fontsize=13.5,
             fontweight="bold", color=T.ink_text)
        ax.text(x + w / 2, y + h / 2 - 0.25, body, ha="center", va="center", fontsize=12.5,
                color=T.ink_text, fontfamily=FONT_BODY, linespacing=1.45)
    for i in range(len(boxes) - 1):
        x0 = boxes[i][0] + w + 0.04
        x1 = boxes[i + 1][0] - 0.04
        ax.add_patch(FancyArrowPatch((x0, y + h / 2), (x1, y + h / 2), arrowstyle="-|>",
                                     mutation_scale=20, color=T.muted_text, linewidth=2))
    # boundary between agent side and verifier side
    ax.plot([7.82, 7.82], [0.25, 3.35], color=T.muted_text, linestyle=(0, (4, 3)), linewidth=1.3)
    mono(ax, 7.70, 0.25, "agent side", ha="right", va="center", fontsize=11, color=T.muted_text)
    mono(ax, 7.94, 0.25, "verifier side (hidden)", ha="left", va="center", fontsize=11,
         color=T.muted_text)
    save(fig, "fig_contract.png", {"diagram": "task contract", "source": "README 'The task contract'"})


# ------------------------------------------------------------------ 2. headline dumbbell
def fig_headline():
    rows = []
    for fam in ORDER:
        o, s = att(fam, OPUS), att(fam, SONNET)
        if fam in ("ecg_ptbxl", "risk_icu"):
            spec = 1.0 if all(o["specialist"]["gate"].values()) else 0.0
            n_lab = "1 cohort · all gate parts"
        else:
            spec = o["specialist"]["n_acceptable"] / o["specialist"]["n_cases"]
            n_lab = f"{o['specialist']['n_cases']} hidden cases"
        rows.append(dict(fam=fam, n_lab=n_lab, spec=spec,
                         opus=o["rewards"]["clinically_acceptable"],
                         sonnet=s["rewards"]["clinically_acceptable"],
                         opus_n=o.get("agent_metrics", {}).get("n_acceptable"),
                         sonnet_n=s.get("agent_metrics", {}).get("n_acceptable"),
                         spec_n=o["specialist"].get("n_acceptable"),
                         n=o["specialist"].get("n_cases")))
    fig, ax = plt.subplots(figsize=(8.2, 6.0))
    style_ax(ax)
    ys = list(range(len(rows)))[::-1]
    for y, r in zip(ys, rows):
        vals = [r["spec"], r["opus"], r["sonnet"]]
        ax.plot([min(vals), max(vals)], [y, y], color=T.rule, linewidth=6, solid_capstyle="round",
                zorder=1)
        jit = {"spec": 0.0, "opus": 0.17, "sonnet": -0.17}
        ax.scatter([r["spec"]], [y + jit["spec"]], marker="D", s=170, color=AMBER, zorder=4,
                   edgecolor=T.canvas, linewidth=1.5)
        ax.scatter([r["opus"]], [y + jit["opus"]], marker="o", s=170, color=TURQUOISE, zorder=5,
                   edgecolor=T.canvas, linewidth=1.5)
        ax.scatter([r["sonnet"]], [y + jit["sonnet"]], marker="o", s=170, color=DEEPPINK, zorder=5,
                   edgecolor=T.canvas, linewidth=1.5)
        if r["n"]:
            txt = f"{r['opus_n']}/{r['n']}  ·  {r['sonnet_n']}/{r['n']}  ·  {r['spec_n']}/{r['n']}"
        else:
            txt = "pass  ·  pass  ·  pass"
        mono(ax, 1.06, y, txt.replace("  ·  ", " · "), va="center", ha="left", fontsize=13, color=T.ink_text)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{TITLE[r['fam']]}\n{r['n_lab']}" for r in rows], fontsize=13.5,
                       color=T.ink_text, fontfamily=FONT_BODY)
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlabel("fraction of hidden cases clinically acceptable", color=T.ink_text)
    ax.xaxis.grid(True, color=T.rule, linewidth=0.8)
    ax.set_axisbelow(True)
    mono(ax, 1.06, len(rows) - 0.45, "Opus·Sonnet·Spec.", va="bottom", ha="left", fontsize=11.5,
         color=T.muted_text)
    handles = [Line2D([], [], marker="o", linestyle="", markersize=12, color=TURQUOISE, label="Opus 5.5"),
               Line2D([], [], marker="o", linestyle="", markersize=12, color=DEEPPINK, label="Sonnet 5.5"),
               Line2D([], [], marker="D", linestyle="", markersize=11, color=AMBER,
                      label="Specialist (same hidden cases)")]
    leg = ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.45, -0.12), ncol=2,
                    frameon=False)
    for t in leg.get_texts():
        t.set_color(T.ink_text)
    save(fig, "fig_headline.png", {"source": str(SRC.relative_to(REPO)), "rows": rows})


# ------------------------------------------------------------------ 3. fetal head per image
def fig_hc18():
    cases = att("measure_hc18", OPUS)["gap"]["per_case"]
    cases_s = att("measure_hc18", SONNET)["gap"]["per_case"]
    groups = [("spec", [(c["specialist_abs_err_mm"], c["specialist_acceptable"]) for c in cases]),
              (OPUS, [(c["agent_abs_err_mm"], c["agent_acceptable"]) for c in cases]),
              (SONNET, [(c["agent_abs_err_mm"], c["agent_acceptable"]) for c in cases_s])]
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    style_ax(ax)
    floor = 0.1
    raw = {}
    for i, (k, vals) in enumerate(groups):
        n = len(vals)
        xs = [i + ((j * 0.6180339) % 1 - 0.5) * 0.55 for j in range(n)]
        ok = [(x, max(v, floor)) for x, (v, a) in zip(xs, vals) if a]
        bad = [(x, max(v, floor)) for x, (v, a) in zip(xs, vals) if not a]
        c = COL[k]
        if ok:
            ax.scatter(*zip(*ok), s=34, color=c, edgecolor=T.canvas, linewidth=0.5, zorder=3)
        if bad:
            ax.scatter(*zip(*bad), s=46, facecolor=T.canvas, edgecolor=c, linewidth=1.7, zorder=4)
        n_ok = sum(a for _, a in vals)
        med = sorted(v for v, _ in vals)[n // 2]
        mono(ax, i, 900, f"{n_ok}/{n}", ha="center", va="center", fontsize=17, fontweight="bold",
             color=c)
        mono(ax, i, 480, "within tolerance", ha="center", va="center", fontsize=10.5,
             color=T.muted_text)
        raw[NAME[k]] = {"n": n, "n_within_tolerance": int(n_ok), "abs_err_mm": [v for v, _ in vals],
                        "within": [bool(a) for _, a in vals], "median_abs_err_mm_plotted": med}
    ax.set_yscale("log")
    ax.set_ylim(floor * 0.8, 1500)
    ax.set_xlim(-0.6, 2.6)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels([NAME[k] for k, _ in groups], color=T.ink_text, fontsize=13.5,
                       fontfamily=FONT_TITLE)
    ax.set_yticks([0.1, 1, 10, 100])
    ax.set_yticklabels(["≤0.1", "1", "10", "100"])
    ax.set_ylabel("|head circumference error| (mm, log scale)", color=T.ink_text)
    ax.yaxis.grid(True, color=T.rule, linewidth=0.8)
    ax.set_axisbelow(True)
    handles = [Line2D([], [], marker="o", linestyle="", markersize=8, color=T.ink_text,
                      label="within 4.9 % of reference"),
               Line2D([], [], marker="o", linestyle="", markersize=8, markerfacecolor=T.canvas,
                      markeredgecolor=T.ink_text, markeredgewidth=1.6, label="outside tolerance")]
    leg = ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2,
                    frameon=False)
    for t in leg.get_texts():
        t.set_color(T.ink_text)
    save(fig, "fig_hc18.png", {"source": str(SRC.relative_to(REPO)), "groups": raw})


# ------------------------------------------------------------------ 4. Opus fetal head timeline
def fig_timeline():
    a = att("measure_hc18", OPUS)
    end_turn = a["session_minutes_to_first_answer_or_end"]   # 11.6
    first_runsh = a["minutes_to_first_runsh_written"]         # 0.1
    proc_end = 19.7  # hosted-agents2.md: "process ended at 19.7 of 45 min" (background job woke it once)
    limit = SESSION_MIN["measure_hc18"]
    fig, ax = plt.subplots(figsize=(12.4, 2.9))
    ax.set_xlim(-0.5, limit + 1.5)
    ax.set_ylim(-1.75, 1.25)
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0, -0.18), limit, 0.36, facecolor=T.surface, edgecolor=T.rule))
    ax.add_patch(plt.Rectangle((0, -0.18), end_turn, 0.36, facecolor=TURQUOISE, edgecolor="none"))
    ax.add_patch(plt.Rectangle((end_turn, -0.18), proc_end - end_turn, 0.36, facecolor=TURQUOISE,
                               alpha=0.28, edgecolor="none"))
    for m in range(0, limit + 1, 5):
        mono(ax, m, -0.26, f"{m}", ha="center", va="top", fontsize=11, color=T.muted_text)
    mono(ax, limit + 0.9, -0.26, "min", ha="left", va="top", fontsize=11, color=T.muted_text)
    ev = [(first_runsh, -0.85, "0.1 min  baseline run.sh\n(constant perimeter)", "left"),
          (end_turn, 0.32, f"{end_turn} min  ends its turn:\n4-fold CV \"about 60%\"", "center"),
          (proc_end, -0.85, f"{proc_end} min  one more turn,\n\"Nothing changes\"", "left"),
          (limit, 0.32, f"{limit} min  session limit", "right")]
    for x, yy, s, ha in ev:
        ax.plot([x, x], [0.18 if yy > 0 else -0.62, yy],
                color=T.ink_text, linewidth=1.2)
        mono(ax, x, yy + (0.05 if yy > 0 else -0.05), s, ha=ha, va="bottom" if yy > 0 else "top",
             fontsize=12, color=T.ink_text, linespacing=1.3)
    mono(ax, (proc_end + limit) / 2 + 2.5, 0.0, f"{limit - end_turn:.1f} min unused after the answer",
         ha="center", va="center", fontsize=12, color=T.muted_text)
    save(fig, "fig_timeline.png", {"source": "hosted-agents2.json + hosted-agents2.md (measure_hc18 · Opus)",
                                   "first_runsh_min": first_runsh, "end_turn_min": end_turn,
                                   "process_end_min": proc_end, "limit_min": limit})


# ------------------------------------------------------------------ 5. session use, all ten
def fig_session():
    rows = []
    for fam in ORDER:
        for m in (OPUS, SONNET):
            a = att(fam, m)
            rows.append(dict(fam=fam, model=NAME[m], col=COL[m],
                             used=a["session_minutes_to_first_answer_or_end"],
                             limit=SESSION_MIN[fam], reward=a["rewards"]["reward"]))
    fig, ax = plt.subplots(figsize=(8.6, 6.4))
    style_ax(ax)
    n = len(rows)
    for i, r in enumerate(rows):
        y = n - 1 - i
        ax.barh(y, r["limit"], height=0.62, color=T.surface, edgecolor=T.rule, linewidth=0.8)
        ax.barh(y, r["used"], height=0.62, color=r["col"])
        mono(ax, r["limit"] + 0.8, y, f"{100 * (1 - r['used'] / r['limit']):.0f}% unused · reward {r['reward']:.2f}",
             va="center", ha="left", fontsize=11.5, color=T.ink_text)
    ax.set_yticks([n - 1 - i for i in range(n)])
    ax.set_yticklabels([f"{TITLE[r['fam']]} · {r['model'].split()[0]}" for r in rows],
                       fontsize=11.5, color=T.ink_text)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 15, 30, 45, 60])
    ax.set_xlabel("minutes (bar = session limit; fill = when the agent ended its turn)",
                  color=T.ink_text)
    ax.spines["bottom"].set_bounds(0, 60)
    handles = [Line2D([], [], marker="s", linestyle="", markersize=11, color=TURQUOISE, label="Opus 5.5"),
               Line2D([], [], marker="s", linestyle="", markersize=11, color=DEEPPINK, label="Sonnet 5.5")]
    leg = ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.32, -0.12), ncol=2,
                    frameon=False)
    for t in leg.get_texts():
        t.set_color(T.ink_text)
    save(fig, "fig_session.png", {"source": str(SRC.relative_to(REPO)), "session_limit_min": SESSION_MIN,
                                  "rows": [{k: v for k, v in r.items() if k != "col"} for r in rows]})


# ------------------------------------------------------------------ 6. per case, reg + spleen
def fig_percase():
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 4.6))
    raw = {}
    for ax, fam, key, lab, thr, thr_lab in [
            (axes[0], "reg_resect", "mean_tre_mm", "mean TRE (mm)", 2.0, "2.0 mm"),
            (axes[1], "seg_spleen", "dice", "Dice", 0.94, "0.94")]:
        style_ax(ax)
        po = att(fam, OPUS)["gap"]["per_case"]
        ps = att(fam, SONNET)["gap"]["per_case"]
        cases = [c["case"] for c in po]
        raw[fam] = []
        for x, (co, cs) in enumerate(zip(po, ps)):
            pts = [(-0.2, co[f"specialist_{key}"], co["specialist_acceptable"], AMBER, "D"),
                   (0.0, co[f"agent_{key}"], co["agent_acceptable"], TURQUOISE, "o"),
                   (0.2, cs[f"agent_{key}"], cs["agent_acceptable"], DEEPPINK, "o")]
            for dx, v, ok, c, mk in pts:
                ax.scatter([x + dx], [v], marker=mk, s=95 if mk == "o" else 80, zorder=4,
                           facecolor=c if ok else T.canvas, edgecolor=c, linewidth=1.9)
            raw[fam].append({"case": co["case"], "specialist": co[f"specialist_{key}"],
                             "specialist_pass": co["specialist_acceptable"],
                             "opus": co[f"agent_{key}"], "opus_pass": co["agent_acceptable"],
                             "sonnet": cs[f"agent_{key}"], "sonnet_pass": cs["agent_acceptable"]})
        ax.axhline(thr, color=T.ink_text, linestyle=(0, (4, 3)), linewidth=1.2, zorder=1)
        ax.set_xticks(range(len(cases)))
        ax.set_xticklabels(cases, fontsize=11, color=T.ink_text, fontfamily=FONT_TITLE)
        ax.set_ylabel(lab, color=T.ink_text)
        ax.yaxis.grid(True, color=T.rule, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_xlim(-0.6, len(cases) - 0.4)
        if fam == "reg_resect":
            ax.set_ylim(0, 11)
            ax.set_title("MRI→US registration · per hidden case (pass: < 2.0 mm)", loc="left",
                         color=T.ink_text, fontsize=13.5, fontfamily=FONT_TITLE)
        else:
            ax.set_ylim(0, 1.05)
            ax.set_title("CT spleen · per hidden case (pass: Dice ≥ 0.94 and volume ≤ 10 %)", loc="left",
                         color=T.ink_text, fontsize=13.5, fontfamily=FONT_TITLE)
    handles = [Line2D([], [], marker="D", linestyle="", markersize=10, color=AMBER, label="Specialist"),
               Line2D([], [], marker="o", linestyle="", markersize=11, color=TURQUOISE, label="Opus 5.5"),
               Line2D([], [], marker="o", linestyle="", markersize=11, color=DEEPPINK, label="Sonnet 5.5"),
               Line2D([], [], marker="o", linestyle="", markersize=11, markerfacecolor=T.canvas,
                      markeredgecolor=T.ink_text, markeredgewidth=1.8, label="hollow = case fails"),
               Line2D([], [], color=T.ink_text, linestyle=(0, (4, 3)), label="clinical threshold")]
    leg = fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.07), ncol=5,
                     frameon=False)
    for t in leg.get_texts():
        t.set_color(T.ink_text)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "fig_percase.png", {"source": str(SRC.relative_to(REPO)), **raw})


if __name__ == "__main__":
    fig_contract()
    fig_headline()
    fig_hc18()
    fig_timeline()
    fig_session()
    fig_percase()
    print("figures written to", FIG)
