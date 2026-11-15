"""Figures for results/suite-deck/CLINICAL_SUITE.pptx (slate theme), after round 3.

Reads only tracked files:
  docs/research/suite/hosted-agents2.json      hosted run 2 (= attempt R1), per image, timeline
  docs/research/suite/hosted-agents3.json      three attempts per task and model (R1-R3)
  docs/research/suite/hosted-keepworking1.json fetal head, arms R and K
  docs/research/suite/hosted-clockcheck1.json  fetal head, arm K2 (skipped with a message if absent)
  docs/research/suite/task-manifest.json       specialist rewards
  docs/research/suite/data/*.json|csv          vessel, causal and report-label aggregates
  pcnsl/results/*/REPORT.md                    PCNSL AUROCs (numbers copied below, with the file)
  docs/research/suite/dataset-survey.md        dataset counts (tallied below, with the section)

Writes slate-canvas PNGs to results/suite-deck/figures/ and the exact values plotted to
figures/raw/<stem>.json. No number is computed beyond counts, means and ratios of values in the inputs.

Run: ~/miniconda3/envs/vals-suite/bin/python results/suite-deck/src/make_figs.py
"""
from __future__ import annotations

import csv
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

SUITE = REPO / "docs/research/suite"
BOX = dict(boxstyle="square,pad=0.15", facecolor=T.canvas, edgecolor="none")  # canvas-coloured label backing
DATA = SUITE / "data"


def rel(p: Path) -> str:
    return str(p.relative_to(REPO))


def load(p: Path):
    return json.loads(p.read_text()) if p.is_file() else None


H2 = load(SUITE / "hosted-agents2.json")
H3 = load(SUITE / "hosted-agents3.json")
HK = load(SUITE / "hosted-keepworking1.json")
HK2 = load(SUITE / "hosted-clockcheck1.json")
MAN = load(SUITE / "task-manifest.json")
VSUM = load(DATA / "seg_vessel_summary.json")
CSUM = load(DATA / "causal_ate_summary.json")
TSUM = load(DATA / "report_label_summary.json")

OPUS, SONNET = "anthropic/claude-opus-5-5", "anthropic/claude-sonnet-5-5"
SHORT = {OPUS: "claude-opus-5-5", SONNET: "claude-sonnet-5-5"}
COL = {OPUS: TURQUOISE, SONNET: DEEPPINK, "spec": AMBER}
NAME = {OPUS: "Opus 5.5", SONNET: "Sonnet 5.5", "spec": "Specialist"}
TITLE = {"reg_resect": "MRI→US registration", "seg_spleen": "CT spleen mask + volume",
         "measure_hc18": "Fetal head circumference", "ecg_ptbxl": "12-lead ECG classes",
         "risk_icu": "ICU mortality risk", "seg_vessel": "Retinal vessel mask"}
# Agent session limits in minutes (task timeouts; hosted-agents3.md: reg, hc18, icu 2700 s;
# spleen 3600 s; ecg 1800 s).
SESSION_MIN = {"reg_resect": 45, "seg_spleen": 60, "measure_hc18": 45, "ecg_ptbxl": 30, "risk_icu": 45}


def full(model: str) -> str:
    """Normalise 'claude-opus-5-5' / 'anthropic/claude-opus-5-5' to the anthropic/ form."""
    m = model if model.startswith("anthropic/") else "anthropic/" + model
    return m


def log(msg):
    print(msg, file=sys.stderr)


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


def legend_below(obj, handles, ncol, anchor=(0.5, -0.12), **kw):
    leg = obj.legend(handles=handles, loc="upper center", bbox_to_anchor=anchor, ncol=ncol,
                     frameon=False, **kw)
    for t in leg.get_texts():
        t.set_color(T.ink_text)
    return leg


def h(marker, color, label, filled=True, ms=11, ls=""):
    if filled:
        return Line2D([], [], marker=marker, linestyle=ls, markersize=ms, color=color, label=label)
    return Line2D([], [], marker=marker, linestyle=ls, markersize=ms, markerfacecolor=T.canvas,
                  markeredgecolor=color, markeredgewidth=1.8, label=label)


def att2(fam, model):
    return next(a for a in H2["attempts"] if a["family"] == fam and a["model"] == model)


def r3_attempts(fam):
    """Rows from hosted-agents3.json per_attempt_including_run2, keyed (model, 'R1'/'R2'/'R3')."""
    out = {}
    for a in H3["per_attempt_including_run2"]:
        if a["family"] == fam:
            out[(full(a["model"]), a["attempt"].split()[0])] = a
    return out


def spec_reward(fam):
    t = next(t for t in MAN["tasks"] if t["family"] == fam)
    return t["specialist_reward"]


def vessel_rows():
    with open(DATA / "seg_vessel_per_image.csv") as f:
        return list(csv.DictReader(f))


def load_k2():
    """Tolerant reader for hosted-clockcheck1.json (schema not fixed when this was written)."""
    if HK2 is None:
        log("skip K2: docs/research/suite/hosted-clockcheck1.json not found")
        return []
    rows = None
    for key in ("per_attempt", "attempts", "per_attempt_k2", "k2_attempts"):
        if isinstance(HK2.get(key), list):
            rows = HK2[key]
            break
    if rows is None:
        log("skip K2: no attempt list in hosted-clockcheck1.json")
        return []
    out = []
    for a in rows:
        arm = str(a.get("arm", "K2")).upper()
        if arm not in ("K2", "CLOCKCHECK", "CLOCK-CHECK"):
            continue
        rew = a["rewards"].get("reward") if isinstance(a.get("rewards"), dict) else a.get("reward")
        frac = a.get("session_fraction_used")
        if frac is None and a.get("agent_process_wall_s") and a.get("session_limit_s"):
            frac = a["agent_process_wall_s"] / a["session_limit_s"]
        if rew is None or frac is None or not a.get("model"):
            continue
        out.append({"arm": "K2", "model": full(a["model"]), "reward": float(rew), "frac": float(frac),
                    "attempt": a.get("attempt")})
    if not out:
        log("skip K2: hosted-clockcheck1.json has no usable K2 rows")
    return out


K2 = load_k2()


# ------------------------------------------------------------------ 1. task contract diagram
def fig_contract():
    fig, ax = plt.subplots(figsize=(13.0, 3.6))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 3.6)
    ax.axis("off")
    boxes = [
        (0.05, "AGENT WORKSPACE", "clinical README\ndev cases with\nreference answers", TURQUOISE),
        (2.70, "CLAUDE CODE", "30–60 min session\nmodel API only\none attempt per run", TURQUOISE),
        (5.35, "PIPELINE", "run.sh IN OUT\nself-contained\nruns offline", AMBER),
        (8.00, "VERIFIER", "hidden cases\nno network\nclinical time limit", DEEPPINK),
        (10.65, "CLINICAL SCORE", "mm · mL · risk\nvs clinical bar\nvs specialist", BLUEVIOLET),
    ]
    w, hh, y = 2.30, 2.55, 0.55
    for x, head, body, c in boxes:
        ax.add_patch(FancyBboxPatch((x, y), w, hh, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    facecolor=T.surface, edgecolor=c, linewidth=2.2))
        ax.add_patch(plt.Rectangle((x, y + hh - 0.12), w, 0.12, facecolor=c, edgecolor="none"))
        mono(ax, x + w / 2, y + hh - 0.45, head, ha="center", va="center", fontsize=13.5,
             fontweight="bold", color=T.ink_text)
        ax.text(x + w / 2, y + hh / 2 - 0.25, body, ha="center", va="center", fontsize=12.5,
                color=T.ink_text, fontfamily=FONT_BODY, linespacing=1.45)
    for i in range(len(boxes) - 1):
        x0 = boxes[i][0] + w + 0.04
        x1 = boxes[i + 1][0] - 0.04
        ax.add_patch(FancyArrowPatch((x0, y + hh / 2), (x1, y + hh / 2), arrowstyle="-|>",
                                     mutation_scale=20, color=T.muted_text, linewidth=2))
    ax.plot([7.82, 7.82], [0.25, 3.35], color=T.muted_text, linestyle=(0, (4, 3)), linewidth=1.3)
    mono(ax, 7.70, 0.25, "agent side", ha="right", va="center", fontsize=11, color=T.muted_text)
    mono(ax, 7.94, 0.25, "verifier side (hidden)", ha="left", va="center", fontsize=11,
         color=T.muted_text)
    save(fig, "fig_contract.png", {"diagram": "task contract", "source": "README 'The task contract'"})


# ------------------------------------------------------------------ 2. pooled headline
def fig_headline():
    pooled = {(p["family"], full(p["model"])): p for p in H3["pooled_3_attempts"]}
    order = ["measure_hc18", "reg_resect", "seg_spleen", "seg_vessel", "ecg_ptbxl", "risk_icu"]
    nlab = {"measure_hc18": "83 hidden images", "reg_resect": "6 hidden cases",
            "seg_spleen": "6 hidden cases", "seg_vessel": "8 hidden images · 1 attempt",
            "ecg_ptbxl": "cohort · all gate parts", "risk_icu": "cohort · all gate parts"}
    rows = []
    for fam in order:
        r = {"family": fam}
        if fam == "seg_vessel":
            r["spec"] = VSUM["specialist"]["n_acceptable"] / VSUM["n_hidden"]
            for m in (OPUS, SONNET):
                a = next(x for x in VSUM["attempts"] if full(x["model"]) == m)
                r[m] = {"rewards": [a["reward"]], "gap": 0 if a["gap_verdict"].startswith("no gap") else 1,
                        "n": 1}
        else:
            r["spec"] = spec_reward(fam)
            for m in (OPUS, SONNET):
                p = pooled[(fam, m)]
                r[m] = {"rewards": p["rewards"], "gap": p["gap_shown_in"], "n": p["n_attempts"]}
        rows.append(r)
    fig, ax = plt.subplots(figsize=(8.4, 6.0))
    style_ax(ax)
    ys = list(range(len(rows)))[::-1]
    for y, r in zip(ys, rows):
        ax.axhline(y, color=T.rule, linewidth=0.6, zorder=0)
        ax.scatter([r["spec"]], [y], marker="D", s=190, color=AMBER, zorder=4, edgecolor=T.canvas,
                   linewidth=1.5)
        for m, dy in ((OPUS, 0.2), (SONNET, -0.2)):
            vals = r[m]["rewards"]
            # stack identical values slightly so every attempt stays visible
            seen = {}
            for v in vals:
                k = round(v, 3)
                off = seen.get(k, 0)
                seen[k] = off + 1
                ax.scatter([v + 0.012 * off], [y + dy], s=120, color=COL[m], zorder=5,
                           edgecolor=T.canvas, linewidth=1.2)
            if len(vals) > 1:
                mean = sum(vals) / len(vals)
                ax.plot([mean, mean], [y + dy - 0.13, y + dy + 0.13], color=COL[m], linewidth=3,
                        zorder=3)
        mono(ax, 1.08, y, f"{r[OPUS]['gap']}/{r[OPUS]['n']} · {r[SONNET]['gap']}/{r[SONNET]['n']}",
             va="center", ha="left", fontsize=13.5, color=T.ink_text)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{TITLE[r['family']]}\n{nlab[r['family']]}" for r in rows], fontsize=12.5,
                       color=T.ink_text, fontfamily=FONT_BODY)
    ax.set_xlim(-0.04, 1.05)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlabel("reward per attempt (fraction of hidden cases acceptable; cohort 0 or 1)",
                  color=T.ink_text, fontsize=12)
    ax.xaxis.grid(True, color=T.rule, linewidth=0.8)
    ax.set_axisbelow(True)
    mono(ax, 1.08, len(rows) - 0.45, "gap shown\nOpus · Sonnet", va="bottom", ha="left",
         fontsize=11.5, color=T.muted_text)
    handles = [h("o", TURQUOISE, "Opus 5.5 (one dot per attempt)"),
               h("o", DEEPPINK, "Sonnet 5.5 (one dot per attempt)"),
               Line2D([], [], color=T.ink_text, linewidth=3, marker="|", linestyle="",
                      markersize=14, markeredgewidth=3, label="mean of 3 attempts"),
               h("D", AMBER, "Specialist, same hidden cases", ms=10)]
    legend_below(ax, handles, 2, anchor=(0.42, -0.13))
    save(fig, "fig_headline.png", {"sources": [rel(SUITE / "hosted-agents3.json"),
                                               rel(DATA / "seg_vessel_summary.json"),
                                               rel(SUITE / "task-manifest.json")],
                                   "rows": [{"family": r["family"], "specialist": r["spec"],
                                             "opus": r[OPUS], "sonnet": r[SONNET]} for r in rows]})


# ------------------------------------------------------------------ 3. fetal head per image, 6 attempts
def fig_hc18():
    r1o = att2("measure_hc18", OPUS)["gap"]["per_case"]
    r1s = att2("measure_hc18", SONNET)["gap"]["per_case"]
    r3 = {}
    for a in H3["attempts_round3"]:
        if a["family"] == "measure_hc18":
            r3[(a["model"], a["attempt"].split()[0])] = a["gap"]["per_case"]
    groups = [("Specialist", "spec", [(c["specialist_abs_err_mm"], c["specialist_acceptable"]) for c in r1o])]
    for m, r1 in ((OPUS, r1o), (SONNET, r1s)):
        for att in ("R1", "R2", "R3"):
            pc = r1 if att == "R1" else r3[(m, att)]
            groups.append((f"{NAME[m].split()[0]}\n{att}", m,
                           [(c["agent_abs_err_mm"], c["agent_acceptable"]) for c in pc]))
    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    style_ax(ax)
    floor = 0.1
    raw = {}
    xpos = [0, 1.3, 2.3, 3.3, 4.6, 5.6, 6.6]
    for x0, (lab, k, vals) in zip(xpos, groups):
        n = len(vals)
        xs = [x0 + ((j * 0.6180339) % 1 - 0.5) * 0.62 for j in range(n)]
        ok = [(x, max(v, floor)) for x, (v, a) in zip(xs, vals) if a]
        bad = [(x, max(v, floor)) for x, (v, a) in zip(xs, vals) if not a]
        c = COL[k]
        if ok:
            ax.scatter(*zip(*ok), s=20, color=c, edgecolor=T.canvas, linewidth=0.4, zorder=3)
        if bad:
            ax.scatter(*zip(*bad), s=28, facecolor=T.canvas, edgecolor=c, linewidth=1.4, zorder=4)
        n_ok = sum(a for _, a in vals)
        mono(ax, x0, 1000, f"{n_ok}/{n}", ha="center", va="center", fontsize=14, fontweight="bold",
             color=c)
        raw[lab.replace("\n", " ")] = {"n": n, "n_within_tolerance": int(n_ok),
                                       "abs_err_mm": [v for v, _ in vals],
                                       "within": [bool(a) for _, a in vals]}
    mono(ax, xpos[0], 560, "within\ntolerance", ha="center", va="center", fontsize=9.5,
         color=T.muted_text)
    ax.set_yscale("log")
    ax.set_ylim(floor * 0.8, 1800)
    ax.set_xlim(-0.6, 7.2)
    ax.set_xticks(xpos)
    ax.set_xticklabels([g[0] for g in groups], color=T.ink_text, fontsize=12, fontfamily=FONT_TITLE)
    ax.set_yticks([0.1, 1, 10, 100])
    ax.set_yticklabels(["≤0.1", "1", "10", "100"])
    ax.set_ylabel("|head circumference error| (mm, log scale)", color=T.ink_text)
    ax.yaxis.grid(True, color=T.rule, linewidth=0.8)
    ax.set_axisbelow(True)
    handles = [h("o", T.ink_text, "within 4.9 % of reference", ms=8),
               h("o", T.ink_text, "outside tolerance", filled=False, ms=8)]
    legend_below(ax, handles, 2, anchor=(0.5, -0.14))
    save(fig, "fig_hc18.png", {"sources": [rel(SUITE / "hosted-agents2.json") + " (R1)",
                                           rel(SUITE / "hosted-agents3.json") + " attempts_round3 (R2, R3)"],
                               "groups": raw})


# ------------------------------------------------------------------ 4. Opus fetal head timeline (run 2)
def fig_timeline():
    a = att2("measure_hc18", OPUS)
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
        ax.plot([x, x], [0.18 if yy > 0 else -0.62, yy], color=T.ink_text, linewidth=1.2)
        mono(ax, x, yy + (0.05 if yy > 0 else -0.05), s, ha=ha, va="bottom" if yy > 0 else "top",
             fontsize=12, color=T.ink_text, linespacing=1.3)
    mono(ax, (proc_end + limit) / 2 + 2.5, 0.0, f"{limit - end_turn:.1f} min unused after the answer",
         ha="center", va="center", fontsize=12, color=T.muted_text)
    save(fig, "fig_timeline.png", {"source": "hosted-agents2.json + hosted-agents2.md (measure_hc18 · Opus)",
                                   "first_runsh_min": first_runsh, "end_turn_min": end_turn,
                                   "process_end_min": proc_end, "limit_min": limit})


# ------------------------------------------------------------------ 5. elicitation: R vs K vs K2
def fig_elicitation():
    pts = []
    for a in HK["per_attempt"]:
        pts.append({"arm": a["arm"], "model": full(a["model"]), "attempt": a["attempt"],
                    "reward": a["rewards"]["reward"], "frac": a["session_fraction_used"]})
    pts += K2
    marker = {"R": "o", "K": "s", "K2": "^"}
    armlab = {"R": "R: unchanged instruction", "K": "K: + keep working while below the bar",
              "K2": "K2: + check the clock"}
    fig, ax = plt.subplots(figsize=(8.0, 5.4))
    style_ax(ax)
    ax.axhline(1.0, color=AMBER, linestyle=(0, (4, 3)), linewidth=1.6, zorder=1)
    mono(ax, 0.01, 1.008, "specialist 83/83", ha="left", va="bottom", fontsize=11.5, color=AMBER, bbox=BOX)
    ax.axhline(0.90, color=T.ink_text, linestyle=(0, (4, 3)), linewidth=1.2, zorder=1)
    mono(ax, 0.01, 0.908, "90 % bar", ha="left", va="bottom", fontsize=11.5, color=T.ink_text, bbox=BOX)
    for p in pts:
        ax.scatter([p["frac"]], [p["reward"]], marker=marker[p["arm"]], s=150, color=COL[p["model"]],
                   edgecolor=T.canvas, linewidth=1.2, zorder=5)
    for p in pts:
        if p["arm"] == "K2" and p["reward"] == 0:
            ax.annotate("reward 0: 2 images over the 10 s limit", (p["frac"], 0.0),
                        xytext=(p["frac"] - 0.62, 0.1), fontsize=11.5, color=T.ink_text,
                        arrowprops=dict(arrowstyle="-", color=T.muted_text, linewidth=1.0))
    ax.set_xlim(0, 1.0)
    ax.set_ylim(-0.05, 1.06)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0 %", "25 %", "50 %", "75 %", "100 %"])
    ax.set_xlabel("share of the 45-minute session used", color=T.ink_text)
    ax.set_ylabel("reward (fraction of 83 images within tolerance)", color=T.ink_text, fontsize=12)
    ax.grid(True, color=T.rule, linewidth=0.8)
    ax.set_axisbelow(True)
    arms = [a for a in ("R", "K", "K2") if any(p["arm"] == a for p in pts)]
    handles = [h("o", TURQUOISE, "Opus 5.5"), h("o", DEEPPINK, "Sonnet 5.5")]
    handles += [h(marker[a], T.ink_text, armlab[a], ms=10) for a in arms]
    legend_below(ax, handles, 2, anchor=(0.45, -0.13))
    save(fig, "fig_elicitation.png", {"sources": [rel(SUITE / "hosted-keepworking1.json")] +
                                      ([rel(SUITE / "hosted-clockcheck1.json")] if K2 else []),
                                      "k2_included": bool(K2), "points": pts})


# ------------------------------------------------------------------ 6. session use, every attempt
def fig_session():
    rows = []  # (label, [(model, frac)])
    lab = {"reg_resect": "Registration", "seg_spleen": "Spleen", "measure_hc18": "Fetal head",
           "ecg_ptbxl": "ECG", "risk_icu": "ICU risk"}
    for fam in ("reg_resect", "seg_spleen", "measure_hc18", "ecg_ptbxl", "risk_icu"):
        pts = [(full(a["model"]), a["session_fraction_used"]) for a in H3["per_attempt_including_run2"]
               if a["family"] == fam]
        rows.append((f"R · {lab[fam]}", pts))
    rows.append(("K · Fetal head", [(full(a["model"]), a["session_fraction_used"])
                                    for a in HK["per_attempt"] if a["arm"] == "K"]))
    if K2:
        rows.append(("K2 · Fetal head", [(p["model"], p["frac"]) for p in K2]))
    rows.append(("V · Vessel", [(full(a["model"]), a["session_s"] / VSUM["session_limit_s"])
                                for a in VSUM["attempts"]]))
    rows.append(("C · Causal", [(full(a["model"]), a["session_s"] / CSUM["session_limit_s"])
                                for a in CSUM["attempts"]]))
    rows.append(("T · Report labels", [(full(r["model"]), r["session_s"] / TSUM["session_limit_s"])
                                       for r in TSUM["rows"] if r.get("kind") == "agent"]))
    fig, ax = plt.subplots(figsize=(8.6, 6.4))
    style_ax(ax)
    n = len(rows)
    for i, (label, pts) in enumerate(rows):
        y = n - 1 - i
        ax.axhline(y, color=T.rule, linewidth=0.6, zorder=0)
        for m, dy in ((OPUS, 0.14), (SONNET, -0.14)):
            xs = sorted(f for mm, f in pts if mm == m)
            ax.scatter([100 * x for x in xs], [y + dy] * len(xs), s=95, color=COL[m],
                       edgecolor=T.canvas, linewidth=1.0, zorder=4)
    allf = [f for _, pts in rows for _, f in pts]
    ax.axvline(100, color=T.ink_text, linestyle=(0, (4, 3)), linewidth=1.2)
    mono(ax, 99, n - 0.45, "session limit", ha="right", va="bottom", fontsize=11, color=T.ink_text)
    ax.set_yticks([n - 1 - i for i in range(n)])
    ax.set_yticklabels([r[0] for r in rows], fontsize=12, color=T.ink_text, fontfamily=FONT_TITLE)
    ax.set_xlim(-2, 104)
    ax.set_ylim(-0.6, n - 0.2)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0 %", "25 %", "50 %", "75 %", "100 %"])
    ax.set_xlabel("share of the agent session used before the agent ended its turn", color=T.ink_text)
    ax.xaxis.grid(True, color=T.rule, linewidth=0.8)
    ax.set_axisbelow(True)
    legend_below(ax, [h("o", TURQUOISE, "Opus 5.5"), h("o", DEEPPINK, "Sonnet 5.5")], 2,
                 anchor=(0.4, -0.11))
    save(fig, "fig_session.png", {"sources": [rel(SUITE / "hosted-agents3.json"),
                                              rel(SUITE / "hosted-keepworking1.json"),
                                              rel(DATA / "seg_vessel_summary.json"),
                                              rel(DATA / "causal_ate_summary.json"),
                                              rel(DATA / "report_label_summary.json")],
                                  "k2_included": bool(K2), "max_fraction": max(allf),
                                  "rows": [{"row": r[0], "points": r[1]} for r in rows]})


# ------------------------------------------------------------------ 7. vessel per image
def fig_vessel():
    rows = vessel_rows()
    cases = sorted({r["case"] for r in rows})
    by = {(r["case"], r["system"]): r for r in rows}
    systems = [("specialist_unet", AMBER, "D", -0.22), ("opus", TURQUOISE, "o", 0.0),
               ("sonnet", DEEPPINK, "o", 0.22)]
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.2))
    raw = {}
    for ax, key, bar, lab in ((axes[0], "dice", "dice_bar_2ndHO", "Dice vs first observer"),
                              (axes[1], "cldice", "cldice_bar_2ndHO", "clDice vs first observer")):
        style_ax(ax)
        for x, c in enumerate(cases):
            b = float(by[(c, "specialist_unet")][bar])
            ax.plot([x - 0.36, x + 0.36], [b, b], color=T.ink_text, linewidth=2.4, zorder=2)
            for sysname, col, mk, dx in systems:
                r = by[(c, sysname)]
                v = float(r[key])
                ok = r["acceptable"] == "1"
                ax.scatter([x + dx], [v], marker=mk, s=95 if mk == "o" else 80, zorder=4,
                           facecolor=col if ok else T.canvas, edgecolor=col, linewidth=1.8)
                raw.setdefault(c, {}).setdefault(sysname, {})[key] = v
                raw[c][sysname]["acceptable"] = ok
            raw[c].setdefault("bar", {})[key] = b
        ax.set_xticks(range(len(cases)))
        ax.set_xticklabels([c.replace("hid_", "") for c in cases], fontsize=11, color=T.ink_text,
                           fontfamily=FONT_TITLE)
        ax.set_ylabel(lab, color=T.ink_text)
        ax.set_ylim(0.74, 0.90)
        ax.set_xlim(-0.6, len(cases) - 0.4)
        ax.yaxis.grid(True, color=T.rule, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_xlabel("hidden image", color=T.muted_text, fontsize=11)
    handles = [h("D", AMBER, "Specialist U-Net", ms=10), h("o", TURQUOISE, "Opus 5.5"),
               h("o", DEEPPINK, "Sonnet 5.5"), h("o", T.ink_text, "hollow = image not acceptable", filled=False),
               Line2D([], [], color=T.ink_text, linewidth=2.4, label="second observer (the bar)")]
    legend_below(fig, handles, 5, anchor=(0.5, 0.02), fontsize=11.5)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    save(fig, "fig_vessel.png", {"source": rel(DATA / "seg_vessel_per_image.csv"),
                                 "note": "Frangi rows omitted (Dice 0.37-0.50, off this scale)", "cases": raw})


# ------------------------------------------------------------------ 8. causal control
def fig_causal():
    g = CSUM["gate"]
    n = CSUM["n_hidden_datasets"]
    items = []
    for c in CSUM["comparators"]:
        short = {"Doubly robust ATT (specialist)": "Specialist (AIPW)",
                 "OLS regression adjustment": "OLS adjustment",
                 "Naive difference in means": "Naive difference"}[c["name"]]
        items.append((short, AMBER if "specialist" in c["name"] else BLUEVIOLET,
                      "D" if "specialist" in c["name"] else "s", c))
    for a in CSUM["attempts"]:
        m = full(a["model"])
        items.append((f"{NAME[m].split()[0]} {a['attempt']}", COL[m], "o", a))
    fig, axes = plt.subplots(1, 3, figsize=(12.4, 4.0), sharey=True)
    ys = list(range(len(items)))[::-1]
    panels = [("coverage", lambda d: d["coverage_n"] / n, g["coverage_min"], "≥ 0.85", (0.35, 1.03)),
              ("RMSE (outcome sd)", lambda d: d["rmse_sd"], g["rmse_max_sd"], "≤ 0.10", (0, 0.2)),
              ("mean interval length (sd)", lambda d: d["mean_length_sd"], g["mean_length_max_sd"], "≤ 0.50",
               (0, 0.55))]
    raw = []
    for ax, (lab, f, thr, thr_lab, xl) in zip(axes, panels):
        style_ax(ax)
        for y, (name, col, mk, d) in zip(ys, items):
            ax.scatter([f(d)], [y], marker=mk, s=110, color=col, edgecolor=T.canvas, linewidth=1.0, zorder=4)
        ax.axvline(thr, color=T.ink_text, linestyle=(0, (4, 3)), linewidth=1.3)
        mono(ax, thr, len(items) - 0.35, f"gate {thr_lab}", ha="center", va="bottom", fontsize=11,
             color=T.ink_text, bbox=BOX, zorder=6)
        ax.set_xlim(*xl)
        ax.set_xlabel(lab, color=T.ink_text)
        ax.xaxis.grid(True, color=T.rule, linewidth=0.8)
        ax.set_axisbelow(True)
    axes[0].set_yticks(ys)
    axes[0].set_yticklabels([i[0] for i in items], fontsize=11.5, color=T.ink_text, fontfamily=FONT_TITLE)
    axes[0].set_ylim(-0.6, len(items) + 0.2)
    for name, col, mk, d in items:
        raw.append({"name": name, "coverage": d["coverage_n"] / n, "coverage_n": d["coverage_n"],
                    "rmse_sd": d["rmse_sd"], "mean_length_sd": d["mean_length_sd"]})
    fig.tight_layout()
    save(fig, "fig_causal.png", {"source": rel(DATA / "causal_ate_summary.json"), "gate": g, "rows": raw})


# ------------------------------------------------------------------ 9. report labels
def fig_report_label():
    rows = TSUM["rows"]
    col = {"specialist": AMBER, "comparator": BLUEVIOLET}
    names = {"Specialist (TF-IDF char 2-5 + LR)": "Specialist\n(TF-IDF + LR)", "Keyword rules": "Keyword\nrules",
             "Opus 5.5": "Opus 5.5", "Sonnet 5.5": "Sonnet 5.5"}
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 4.6), gridspec_kw={"width_ratios": [1.6, 1]})
    ys = list(range(len(rows)))[::-1]
    ax = axes[0]
    style_ax(ax)
    for y, r in zip(ys, rows):
        c = COL[full(r["model"])] if r["kind"] == "agent" else col[r["kind"]]
        lo, hi = r["macro_f1_ci95"]
        ax.plot([lo, hi], [y, y], color=c, linewidth=3, zorder=3, solid_capstyle="round")
        ax.scatter([r["macro_f1"]], [y], s=130, color=c, marker="D" if r["kind"] == "specialist" else "o",
                   edgecolor=T.canvas, linewidth=1.2, zorder=4)
        mono(ax, r["macro_f1"], y - 0.3, f"{r['macro_f1']:.3f}", ha="center", va="center", fontsize=11.5,
             bbox=BOX, zorder=6)
    ax.axvline(TSUM["gate"]["macro_f1_min"], color=T.ink_text, linestyle=(0, (4, 3)), linewidth=1.3)
    mono(ax, 0.80, len(rows) - 0.45, "bar 0.80", ha="center", va="bottom", fontsize=11, bbox=BOX, zorder=6)
    ax.set_xlim(0.68, 0.86)
    ax.set_yticks(ys)
    ax.set_yticklabels([names[r["name"]] for r in rows], fontsize=12, color=T.ink_text, fontfamily=FONT_TITLE)
    ax.set_ylim(-0.6, len(rows) - 0.1)
    ax.set_xlabel("macro F1 (95 % CI)", color=T.ink_text)
    ax.xaxis.grid(True, color=T.rule, linewidth=0.8)
    ax.set_axisbelow(True)
    ax = axes[1]
    style_ax(ax)
    for y, r in zip(ys, rows):
        c = COL[full(r["model"])] if r["kind"] == "agent" else col[r["kind"]]
        ax.barh(y, r["min_kappa"], height=0.55, color=c)
        mono(ax, 0.02, y, f"{r['min_kappa']:.2f} {r['min_kappa_class']}", ha="left",
             va="center", fontsize=11, color="#0b0b0b" if c in (AMBER, TURQUOISE) else "#ffffff", zorder=6)
    ax.axvline(TSUM["gate"]["min_kappa_each_class"], color=T.ink_text, linestyle=(0, (4, 3)), linewidth=1.3)
    mono(ax, 0.60, len(rows) - 0.45, "bar 0.60", ha="center", va="bottom", fontsize=11, bbox=BOX, zorder=6)
    ax.set_xlim(0, 0.95)
    ax.set_yticks([])
    ax.set_ylim(-0.6, len(rows) - 0.1)
    ax.set_xlabel("worst-class kappa", color=T.ink_text)
    ax.xaxis.grid(True, color=T.rule, linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save(fig, "fig_report_label.png", {"source": rel(DATA / "report_label_summary.json"),
                                       "gate": TSUM["gate"],
                                       "rows": [{k: r.get(k) for k in ("name", "macro_f1", "macro_f1_ci95",
                                                                        "min_kappa", "min_kappa_class")}
                                                for r in rows]})


# ------------------------------------------------------------------ 10. reward keys, 30 attempts
def fig_reward_keys():
    keys = ["ran", "valid", "within_time", "clinically_acceptable", "quality", "vs_specialist", "reward"]
    fams = ["reg_resect", "seg_spleen", "measure_hc18", "ecg_ptbxl", "risk_icu"]
    short = {"reg_resect": "reg", "seg_spleen": "spleen", "measure_hc18": "fetal head",
             "ecg_ptbxl": "ECG", "risk_icu": "ICU"}
    cols = []
    for fam in fams:
        r = r3_attempts(fam)
        for m in (OPUS, SONNET):
            for att in ("R1", "R2", "R3"):
                cols.append((fam, m, att, r[(m, att)]["rewards"]))
    fig, ax = plt.subplots(figsize=(12.4, 4.6))
    ax.set_facecolor(T.canvas)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("brand", [T.surface, "#1f6f78", TURQUOISE])
    ax.grid(False)
    for j, (fam, m, att, rw) in enumerate(cols):
        for i, k in enumerate(keys):
            v = rw[k]
            ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor=cmap(v), edgecolor=T.canvas, linewidth=1.5))
            if k in ("clinically_acceptable", "quality", "vs_specialist", "reward") or v < 1:
                ax.text(j + 0.5, i + 0.5, f"{v:.2f}".replace("0.", ".").replace("1.00", "1"),
                        ha="center", va="center", fontsize=8.5, fontfamily=FONT_TITLE,
                        color="#0b0b0b" if v > 0.7 else "#f4f4f2")
    ax.set_xlim(0, len(cols))
    ax.set_ylim(len(keys), 0)
    ax.set_yticks([i + 0.5 for i in range(len(keys))])
    ax.set_yticklabels(keys, fontsize=11.5, color=T.ink_text, fontfamily=FONT_TITLE)
    ax.set_xticks([j + 0.5 for j in range(len(cols))])
    ax.set_xticklabels([c[2] for c in cols], fontsize=9, color=T.muted_text, fontfamily=FONT_TITLE)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    for g, fam in enumerate(fams):
        x0 = g * 6
        mono(ax, x0 + 3, len(keys) + 1.05, short[fam], ha="center", va="top", fontsize=12.5, fontweight="bold")
        mono(ax, x0 + 1.5, -0.25, "Opus", ha="center", va="bottom", fontsize=11, color=TURQUOISE)
        mono(ax, x0 + 4.5, -0.25, "Sonnet", ha="center", va="bottom", fontsize=11, color=DEEPPINK)
        if g:
            ax.plot([x0, x0], [-0.05, len(keys) + 0.05], color=T.ink_text, linewidth=2.0)
    for g in range(len(fams)):
        ax.plot([g * 6 + 3, g * 6 + 3], [0, len(keys)], color=T.canvas, linewidth=3.0)
    save(fig, "fig_reward_keys.png", {"source": rel(SUITE / "hosted-agents3.json") + " per_attempt_including_run2",
                                      "columns": [{"family": c[0], "model": c[1], "attempt": c[2],
                                                   "rewards": c[3]} for c in cols]})


# ------------------------------------------------------------------ 11. dataset filtering
def fig_funnel():
    # Counts from docs/research/suite/dataset-survey.md section 2 tables (Rating column, tallied
    # 2026-11-15): 50 rows; 13 "usable today", 21 "usable with care", 12 "not usable",
    # 3 "unverified", 1 "use RESECT itself". Section 4 ranked shortlist: 8 rows.
    # Families built: 9 (README families table: 6 on 14 Nov, plus vessel, causal, report labels in round 3).
    # Specialist passes its gate on the hidden cases: 7 of 9 (pharyngitis and report labels excluded).
    stages = [("50", "candidate rows\nvetted in the\ndataset survey", T.muted_text),
              ("34", "licence allows\nredistribution\n(13 usable,\n21 with care)", TURQUOISE),
              ("8", "ranked shortlist:\nclinical metric,\nbaseline, size", DEEPPINK),
              ("9", "families built\n(6, then 3 more\nin round 3)", AMBER),
              ("7", "specialist\npasses on\nhidden cases:\nscored or control", BLUEVIOLET)]
    fig, ax = plt.subplots(figsize=(12.4, 3.6))
    ax.set_xlim(0, 12.4)
    ax.set_ylim(0, 3.6)
    ax.axis("off")
    w, gap = 1.45, 0.24
    x = 0.05
    yc = 1.8
    for i, (num, lab, c) in enumerate(stages):
        hh = 3.3 - i * 0.22
        y0 = yc - hh / 2
        ax.add_patch(FancyBboxPatch((x, y0), w, hh, boxstyle="round,pad=0.02,rounding_size=0.06",
                                    facecolor=T.surface, edgecolor=c, linewidth=2.0))
        mono(ax, x + w / 2, y0 + hh - 0.5, num, ha="center", va="center", fontsize=24, fontweight="bold",
             color=c if c != T.muted_text else T.ink_text)
        ax.text(x + w / 2, yc - 0.3, lab, ha="center", va="center", fontsize=10,
                color=T.ink_text, fontfamily=FONT_BODY, linespacing=1.3)
        if i < len(stages) - 1:
            ax.add_patch(FancyArrowPatch((x + w + 0.03, yc), (x + w + gap - 0.01, yc), arrowstyle="-|>",
                                         mutation_scale=14, color=T.ink_text, linewidth=1.6, zorder=5))
        x += w + gap
    # side box: course and local datasets that failed on licence (survey section 1)
    bx = x + 0.1
    bw = 12.35 - bx
    ax.add_patch(FancyBboxPatch((bx, 0.15), bw, 3.3, boxstyle="round,pad=0.02,rounding_size=0.06",
                                facecolor=T.surface, edgecolor=DEEPPINK, linewidth=2.0))
    mono(ax, bx + 0.15, 3.15, "COURSE + LOCAL DATASETS", ha="left", va="center", fontsize=10.5,
         fontweight="bold", color=T.ink_text)
    lines = [("HAM10000", "CC BY-NC 4.0"), ("APTOS 2019", "Kaggle rules: NC,\nno redistribution"),
             ("Open-i", "CC BY-NC-ND 4.0\n(per mirrors)"), ("DRIVE/STARE", "no licence stated")]
    yy = 2.75
    for name, why in lines:
        mono(ax, bx + 0.15, yy, name, ha="left", va="top", fontsize=10.5, fontweight="bold", color=DEEPPINK)
        ax.text(bx + 1.75, yy, why, ha="left", va="top", fontsize=10.5, color=T.ink_text, fontfamily=FONT_BODY,
                linespacing=1.2)
        yy -= 0.5 if "\n" not in why else 0.72
    save(fig, "fig_funnel.png", {"source": "docs/research/suite/dataset-survey.md sections 1, 2, 4; README families table",
                                 "stages": [{"n": s[0], "label": s[1]} for s in stages],
                                 "course_and_local": lines})


# ------------------------------------------------------------------ 12. PCNSL attempt
def fig_pcnsl():
    # pcnsl/results/20261114-prediction-baselines/REPORT.md (logistic, 439 features, pooled OOF),
    # 20261114-tabpfn-pilot/REPORT.md (TabPFN v2.5 full OOF), 20261114-versa-pilot/REPORT.md (GPT-5.2,
    # fold 0 only; Opus 5.5 strict format failure), 20261114-hosted-release/REPORT.md (spatial logistic,
    # 10 FLAIR fractions, mean of 3 seeds, 63 patients).
    methods = [("Logistic, 439 features", 0.562, 0.347),
               ("TabPFN v2.5, 439 features", 0.420, 0.386),
               ("GPT-5.2, fold 0 only", 0.567, 0.361),
               ("Logistic, 10 FLAIR features\n(mean of 3 seeds)", 0.6684, 0.4434),
               ("Opus 5.5, fold 0", None, None)]
    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    style_ax(ax)
    ys = list(range(len(methods)))[::-1]
    for y, (name, myd, cd) in zip(ys, methods):
        if myd is None:
            mono(ax, 0.02, y, "response format failure (not scored)", va="center", ha="left",
                 fontsize=11.5, color=T.muted_text)
            continue
        ax.barh(y + 0.18, myd, height=0.34, color=TURQUOISE)
        ax.barh(y - 0.18, cd, height=0.34, color=DEEPPINK)
        mono(ax, myd + 0.01, y + 0.18, f"{myd:.2f}", va="center", ha="left", fontsize=11, bbox=BOX, zorder=6)
        mono(ax, cd + 0.01, y - 0.18, f"{cd:.2f}", va="center", ha="left", fontsize=11, bbox=BOX, zorder=6)
    ax.axvline(0.5, color=T.ink_text, linestyle=(0, (4, 3)), linewidth=1.3)
    mono(ax, 0.5, len(methods) - 0.45, "chance 0.5", ha="center", va="bottom", fontsize=11, bbox=BOX, zorder=6)
    ax.set_yticks(ys)
    ax.set_yticklabels([m[0] for m in methods], fontsize=11.5, color=T.ink_text, fontfamily=FONT_BODY)
    ax.set_xlim(0, 0.8)
    ax.set_ylim(-0.6, len(methods) - 0.1)
    ax.set_xlabel("AUROC, held-out folds", color=T.ink_text)
    ax.xaxis.grid(True, color=T.rule, linewidth=0.8)
    ax.set_axisbelow(True)
    legend_below(ax, [Line2D([], [], marker="s", linestyle="", markersize=11, color=TURQUOISE, label="MYD88"),
                      Line2D([], [], marker="s", linestyle="", markersize=11, color=DEEPPINK, label="CD79B")],
                 2, anchor=(0.4, -0.14))
    save(fig, "fig_pcnsl.png", {"sources": ["pcnsl/results/20261114-prediction-baselines/REPORT.md",
                                            "pcnsl/results/20261114-tabpfn-pilot/REPORT.md",
                                            "pcnsl/results/20261114-versa-pilot/REPORT.md",
                                            "pcnsl/results/20261114-hosted-release/REPORT.md"],
                                "rows": [{"method": m[0], "MYD88": m[1], "CD79B": m[2]} for m in methods]})


if __name__ == "__main__":
    for stale in ("fig_percase.png", "raw/fig_percase.json"):
        p = FIG / stale
        if p.exists():
            p.unlink()
    fig_contract()
    fig_headline()
    fig_hc18()
    fig_timeline()
    fig_elicitation()
    fig_session()
    fig_vessel()
    fig_causal()
    fig_report_label()
    fig_reward_keys()
    fig_funnel()
    fig_pcnsl()
    print("figures written to", FIG, "| K2 included:", bool(K2))
