"""Write handcrafted freeform slides + speaker notes into CLINICAL_SUITE.md.layout.json.

Every number on a slide is read from a tracked result file or copied from the cited document:
  docs/research/suite/hosted-agents2.json   hosted run 2 (= attempt R1), per-case values
  docs/research/suite/hosted-agents3.json   three attempts per task and model (R1-R3), pooled verdicts
  docs/research/suite/hosted-keepworking1.json   keep-working instruction test (K) against R
  docs/research/suite/hosted-clockcheck1.json    clock-check instruction test (K2), when present
  docs/research/suite/data/*.json|csv       vessel, causal and report-label aggregates
  README.md, round3-results.md, causal_ate.md, seg_vessel.md, label_ptbxl_reports.md,
  dataset-survey.md, pcnsl/results/*/REPORT.md   for quoted text and costs
Run after make_figs.py and `build.py --plan-only --shake`, then build without --shake.

Run: ~/miniconda3/envs/vals-suite/bin/python results/suite-deck/src/make_layout.py
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

DECK = Path(__file__).resolve().parents[1]
REPO = DECK.parents[1]
DOCS = REPO / "docs/research/suite"
SIDE = DECK / "CLINICAL_SUITE.md.layout.json"
H2 = json.loads((DOCS / "hosted-agents2.json").read_text())
H3 = json.loads((DOCS / "hosted-agents3.json").read_text())
KW = json.loads((DOCS / "hosted-keepworking1.json").read_text())
K2_PATH = DOCS / "hosted-clockcheck1.json"
K2 = json.loads(K2_PATH.read_text()) if K2_PATH.exists() else None
VES = json.loads((DOCS / "data/seg_vessel_summary.json").read_text())
CAU = json.loads((DOCS / "data/causal_ate_summary.json").read_text())
RL = json.loads((DOCS / "data/report_label_summary.json").read_text())
OPUS, SONNET = "anthropic/claude-opus-5-5", "anthropic/claude-sonnet-5-5"
O5, S5 = "claude-opus-5-5", "claude-sonnet-5-5"

plan = json.loads(SIDE.read_text())
plan["theme"] = "slate"  # figures are rendered on the slate canvas (#1E293B)


def att2(fam, model):
    return next(a for a in H2["attempts"] if a["family"] == fam and a["model"] == model)


def pooled(fam, model):
    return next(p for p in H3["pooled_3_attempts"] if p["family"] == fam and p["model"] == model)


def per_attempt(fam, model):
    return [a for a in H3["per_attempt_including_run2"] if a["family"] == fam and a["model"] == model]


def kw_summary(model, arm):
    return next(s for s in KW["summary"] if s["model"] == model and s["arm"] == arm)


def m(v):
    return f"{v:+.3f}".replace("-", "−") if v < 0 else f"{v:+.3f}"


def ci(d, nd=3):
    f = f"{{:+.{nd}f}}"
    g = lambda v: f.format(v).replace("-", "−").replace("+0.000", "0.000").replace("+0.00", "0.00")
    return f"{g(d['difference'])} ({g(d['low'])} to {g(d['high'])})"


def rw(x):
    return f"{x:.3f}"


PRI = "_text_on(CANVAS_BG_RGB)"
_MUTFILL = "_rgb('#94A3B8')"
ONS = "_text_on(SURFACE_RGB)"
MUT = "_rgb('#94A3B8')"


def T(text, l, t, w, h, size, color=PRI, font="SANS_FONT", bold=False, align="LEFT", anchor="TOP",
      italic=False):
    return (f"_add_text(slide, {text!r}, left={l}, top={t}, width={w}, height={h}, size={size}, "
            f"color_rgb={color}, font={font}, bold={bold}, italic={italic}, align=PP_ALIGN.{align}, "
            f"anchor=MSO_ANCHOR.{anchor})\n")


def R(l, t, w, h, fill):
    return f"_add_rect(slide, left={l}, top={t}, width={w}, height={h}, fill_rgb={fill})\n"


def IMG(path, l, t, w, h):
    return f"_fit_image(slide, {path!r}, left={l}, top={t}, max_w={w}, max_h={h})\n"


def FOOT(text):
    return T(text, "body_l", "body_bottom - 0.28", "body_w", 0.3, 9, MUT)


def TABLE(rows, widths, l, t, row_h, header="TURQUOISE_RGB", size=11, first_mono=True):
    """Flat table: header row on an accent fill, body rows alternating surface / canvas."""
    code = ""
    x0 = 0.0
    xs = []
    for w in widths:
        xs.append(x0)
        x0 += w
    total = x0
    for i, row in enumerate(rows):
        y = f"{t} + {i * row_h:.3f}"
        if i == 0:
            code += R(l, y, total, row_h, header)
            col = f"_text_on({header})"
        elif i % 2 == 1:
            code += R(l, y, total, row_h, "SURFACE_RGB")
            col = ONS
        else:
            col = PRI
        for j, cell in enumerate(row):
            font = "MONO_FONT" if (i == 0 or (j == 0 and first_mono)) else "SANS_FONT"
            code += T(cell, f"{l} + {xs[j] + 0.10:.3f}", y, round(widths[j] - 0.16, 3), row_h,
                      size, col, font, bold=(i == 0), anchor="MIDDLE")
    return code


def side_cards(cards, rx, rw_, top, bh, gap=0.15, size=12.5, head=12):
    code = ""
    for i, (k, t, c) in enumerate(cards):
        y = f"{top} + {i * (bh + gap):.2f}"
        code += R(rx, y, rw_, bh, "SURFACE_RGB") + R(rx, y, 0.08, bh, c)
        code += T(k, f"{rx} + 0.25", f"{y} + 0.12", rw_ - 0.4, 0.3, head, c, "MONO_FONT", True)
        code += T(t, f"{rx} + 0.25", f"{y} + 0.45", rw_ - 0.4, bh - 0.5, size, ONS)
    return code


slides = {}
SRC3 = ("Source: docs/research/suite/hosted-agents3.json · R1 = hosted run 2, R2–R3 = round 3 · "
        "suite/clinical-v1@2 (instructions v3) · vessel: docs/research/suite/seg_vessel.md")

# ------------------------------------------------------------------ derived numbers
hc_o, hc_s = pooled("measure_hc18", O5), pooled("measure_hc18", S5)
rg_o, rg_s = pooled("reg_resect", O5), pooled("reg_resect", S5)
sp_o, sp_s = pooled("seg_spleen", O5), pooled("seg_spleen", S5)
ec_o, ec_s = pooled("ecg_ptbxl", O5), pooled("ecg_ptbxl", S5)
ic_o, ic_s = pooled("risk_icu", O5), pooled("risk_icu", S5)
hc_n = {mo: [round(r * 83) for r in pooled("measure_hc18", mo)["rewards"]] for mo in (O5, S5)}
ves_o = next(a for a in VES["attempts"] if a["model"] == O5)
ves_s = next(a for a in VES["attempts"] if a["model"] == S5)
K2_ATT = [a for a in (K2 or {}).get("per_attempt", []) if a.get("arm") == "K2"]
n_session_attempts = len(H3["per_attempt_including_run2"]) + 6 + len(K2_ATT) + len(VES["attempts"]) + len(CAU["attempts"]) + 2
_cands = [(a["session_fraction_used"], f"{'Opus' if 'opus' in a['model'] else 'Sonnet'}, {a['family']} {a['attempt'].split()[0]}")
          for a in H3["per_attempt_including_run2"]]
_cands += [(a["session_fraction_used"], f"{'Opus' if 'opus' in a['model'] else 'Sonnet'}, fetal head {a['attempt']}") for a in K2_ATT]
max_used, max_who = max(_cands)
max_who = max_who.replace("measure_hc18", "fetal head")
k_o, k_s = kw_summary(O5, "K"), kw_summary(S5, "K")
r_o, r_s = kw_summary(O5, "R"), kw_summary(S5, "R")


def arrow(seq):
    return " → ".join(f"{v:.3f}" for v in seq)


# K2 text: filled from hosted-clockcheck1.json when it exists, otherwise marked pending.
def k2_lines():
    if K2 is None:
        return None
    out = {}
    for s in K2.get("summary", []):
        if str(s.get("arm", "")).upper() == "K2":
            out[s["model"]] = s
    return out or None


K2S = k2_lines()

# ------------------------------------------------------------------ overview slot (Jin)
slides["h2-overview"] = dict(
    title="Overview",
    code=(
        R("body_l", "body_top + 0.3", "body_w", "body_h - 0.9", "SURFACE_RGB")
        + R("body_l", "body_top + 0.3", 0.10, "body_h - 0.9", "AMBER_RGB")
        + T("RESERVED", "body_l + 0.45", "body_top + 0.65", 6, 0.4, 14, "AMBER_RGB", "MONO_FONT", True)
        + T("Jin's overview, in his own words.", "body_l + 0.45", "body_top + 1.3", "body_w - 0.9", 0.8,
            28, ONS, "MONO_FONT", True)
        + T("This slide is intentionally left for the presenter. Replace this text with the overview "
            "before the demo.", "body_l + 0.45", "body_top + 2.3", "body_w - 0.9", 0.8, 16, ONS)
    ),
    notes=("Reserved for Jin's own overview. Nothing here has been drafted on his behalf. "
           "Transition: from the overview into why clinical evaluation needs more than a benchmark score."),
)

# ------------------------------------------------------------------ problem
rows3 = [
    ("IN UNITS", "Is the registration within 2 mm? Is the spleen volume within 10 %? Is the risk calibrated?", "TURQUOISE_RGB"),
    ("IN TIME", "Does the pipeline finish inside a clinical limit: 120 s per scan, 10 s per ultrasound image?", "AMBER_RGB"),
    ("AGAINST A SPECIALIST", "Does it match a specialist system run on the same hidden cases, case by case?", "DEEPPINK_RGB"),
]
code = (
    R("body_l", "body_top + 0.75", 3.6, 3.9, "SURFACE_RGB")
    + R("body_l", "body_top + 0.75", 0.10, 3.9, _MUTFILL)
    + T("A GENERIC BENCHMARK", "body_l + 0.35", "body_top + 0.95", 3.1, 0.4, 13, ONS, "MONO_FONT", True)
    + T("asks for an answer and reports one score", "body_l + 0.35", "body_top + 1.45", 3.0, 0.9, 18, ONS, "SANS_FONT")
    + T("accuracy, pass rate, leaderboard rank", "body_l + 0.35", "body_top + 2.55", 3.0, 0.8, 14, ONS, "MONO_FONT")
    + T("no units · no deadline · no clinical comparator", "body_l + 0.35", "body_top + 3.55", 3.0, 0.8, 14, ONS, "SANS_FONT", italic=True)
    + "_add_flat_shape(slide, MSO_SHAPE.RIGHT_ARROW, left=body_l + 3.8, top=body_top + 2.4, width=0.7, height=0.6, fill_rgb=_rgb(\"#94A3B8\"))\n"
    + T("A CLINICAL DELIVERABLE IS JUDGED", "body_l + 4.75", "body_top + 0.2", 7.4, 0.4, 13, MUT, "MONO_FONT", True)
)
for i, (lab, body, c) in enumerate(rows3):
    y = f"body_top + 0.75 + {i * 1.35:.2f}"
    code += R("body_l + 4.75", y, "body_w - 4.75", 1.2, "SURFACE_RGB")
    code += R("body_l + 4.75", y, 0.10, 1.2, c)
    code += T(lab, "body_l + 5.05", f"{y} + 0.15", 6.5, 0.35, 15, c, "MONO_FONT", True)
    code += T(body, "body_l + 5.05", f"{y} + 0.55", "body_w - 5.5", 0.6, 15, ONS)
code += FOOT("Metric choices follow docs/research/suite/metrics-review.md (TRE for registration; Dice plus volume; calibration and net benefit, not AUROC alone).")
slides["h2-clinical-evaluation-what-a-generic-benchmark-score-leaves-out"] = dict(
    title="Clinical evaluation — what a generic benchmark score leaves out",
    code=code,
    notes=("This is the problem the benchmark addresses. Most benchmark scores ask whether the model produced the right answer and report a single number. "
           "In a clinic, the deliverable is judged three other ways. First, in physical units: a registration of the pre-operative MRI to the ultrasound is only useful if landmarks line up within about 2 millimetres; an organ mask matters because of the volume in millilitres; a risk score has to be calibrated, meaning a predicted 20 % risk should come true about 20 % of the time. "
           "Second, in time: a pipeline that needs an hour per scan cannot be used during surgery. "
           "Third, against a specialist: the fair bar is the dedicated system a hospital would use, run on the same hidden cases, not a leaderboard from another dataset. "
           "Transition: so we built tasks that measure all three."),
)

# ------------------------------------------------------------------ contract + seven families
fams7 = [
    ("REGISTRATION", "MRI → ultrasound", "< 2.0 mm / case", "spec. 4/6", "scored", "TURQUOISE_RGB"),
    ("SPLEEN", "CT mask + mL", "Dice≥0.94·vol≤10%", "spec. 3/6", "scored", "TURQUOISE_RGB"),
    ("FETAL HEAD", "circumference, mm", "≤ 4.9 %, bar 90 %", "spec. 83/83", "scored", "TURQUOISE_RGB"),
    ("VESSELS", "retinal mask", "≥ 2nd observer", "spec. 6/8", "scored · new", "DEEPPINK_RGB"),
    ("ECG", "5 calibrated classes", "MI·ECE·subgroup", "spec. 3/3 parts", "control", "AMBER_RGB"),
    ("ICU RISK", "calibrated mortality", "4-part gate", "spec. 4/4 parts", "control", "AMBER_RGB"),
    ("TREATMENT", "effect + 95 % CI", "coverage ≥ 0.85", "spec. 4/4 parts", "control · new", "BLUEVIOLET_RGB"),
]
code = IMG("figures/fig_contract.png", "body_l", "body_top", "body_w", 2.6)
cw = 12.3 / 7
for i, (h, d, thr, sp, role, c) in enumerate(fams7):
    x = f"body_l + {i * cw + 0.03:.2f}"
    y = "body_top + 2.75"
    w = round(cw - 0.1, 2)
    code += R(x, y, w, 2.05, "SURFACE_RGB")
    code += R(x, y, w, 0.07, c)
    code += T(h, f"{x} + 0.12", f"{y} + 0.15", round(w - 0.2, 2), 0.32, 11, c, "MONO_FONT", True)
    code += T(d, f"{x} + 0.12", f"{y} + 0.52", round(w - 0.2, 2), 0.3, 11, ONS)
    code += T(thr, f"{x} + 0.12", f"{y} + 0.86", round(w - 0.2, 2), 0.3, 10, ONS, "MONO_FONT")
    code += T(sp, f"{x} + 0.12", f"{y} + 1.2", round(w - 0.2, 2), 0.3, 10, ONS, "MONO_FONT")
    code += T(role, f"{x} + 0.12", f"{y} + 1.58", round(w - 0.2, 2), 0.3, 11, c, "MONO_FONT", True)
code += FOOT("Public data: RESECT, MSD Task09, HC18, CHASE_DB1, PTB-XL, PhysioNet/CinC 2012. Built and excluded as worked examples: report labels and pharyngitis triage (no comparator passes).")
slides["h2-task-contract-and-the-seven-task-families"] = dict(
    title="Task contract and the seven task families",
    code=code,
    notes=("Here is how every task works, left to right. The agent, Claude Code with web tools removed, gets a workspace with a clinical README, development cases with their reference answers, and network access only to the model API. "
           "It has 30 to 60 minutes. What it must leave behind is not an answer but a pipeline: a run.sh that takes an input folder and writes the clinical output, offline. "
           "A separate verifier, which the agent never sees, runs that pipeline on hidden cases under a clinical time limit, scores the output in clinical units, and compares it with a specialist system's stored outputs on the very same cases. "
           "The seven families span imaging, signals and statistics: registering brain MRI to intra-operative ultrasound, a CT spleen mask with its volume, fetal head circumference from ultrasound, retinal vessel segmentation judged against a second human reader, a calibrated ECG classifier, ICU mortality risk, and a treatment-effect estimate with a confidence interval. "
           "The last three turned out to be controls: tasks both the specialist and the agents pass, which shows the harness is not simply too hard. "
           "Two more families were built and excluded because no comparator could pass their bar; they are in the backup. "
           "Transition: here is how the two frontier models did across three attempts each."),
)

# ------------------------------------------------------------------ pooled headline
fw = 7.7
code = IMG("figures/fig_headline.png", "body_l", "body_top + 0.05", fw, "body_h - 0.45")
rx, rwid = f"body_l + {fw + 0.3}", round(12.3 - fw - 0.3, 2)
cards = [
    ("GAP IN 3 OF 3 ATTEMPTS", f"Fetal head, both models: {min(hc_n[O5] + hc_n[S5])}–{max(hc_n[O5] + hc_n[S5])} of 83 images within tolerance; specialist 83 of 83. "
     f"Registration, Sonnet: {arrow(rg_s['rewards'])}.", "DEEPPINK_RGB"),
    ("DEPENDS ON THE ATTEMPT", f"Opus registration {arrow(rg_o['rewards'])}; Opus spleen {arrow(sp_o['rewards'])}. "
     "Gap shown in 1 of 3 each; 6 hidden cases.", "TURQUOISE_RGB"),
    ("NO GAP SHOWN", f"Vessels: Opus {ves_o['n_acceptable']}/8, Sonnet {ves_s['n_acceptable']}/8, specialist 6/8. "
     "ICU 6 of 6 attempts pass; ECG 5 of 6 (Opus once at MI sensitivity 0.693, bar 0.70).", "AMBER_RGB"),
]
code += side_cards(cards, rx, rwid, "body_top + 0.05", 1.55, size=12)
code += FOOT(SRC3)
slides["h2-agent-vs-specialist-three-attempts-per-task-and-model"] = dict(
    title="Agent vs specialist — three attempts per task and model",
    code=code,
    notes=("This is the headline. Each row is one task. The horizontal position is the reward: the fraction of hidden cases that met the clinical bar, or for the two cohort tasks, 1 if every part of the gate was met and 0 if not. "
           "Each turquoise dot is one Opus 5.5 attempt and each pink dot one Sonnet 5.5 attempt; the yellow diamond is the specialist on the same cases. We ran every task three times per model, from scratch, on the same task version. "
           "Three things to say. One: fetal head circumference is the stable result. In all six attempts the agents fall short of a specialist that gets all 83 images right, with intervals far from zero, and none reaches the 90 % bar. Sonnet also shows a gap on registration every time. "
           "Two: registration and spleen depend on the attempt. Opus matched the specialist on registration in its first attempt and scored zero in its third. One attempt per task, which is what we reported yesterday, would have been misleading. "
           "Three: on the new retinal vessel task, ICU risk and ECG, the agents are close to or level with the specialist. "
           "Transition: let us look at the fetal head gap image by image."),
)

# ------------------------------------------------------------------ hc18 per image, six attempts
fw = 7.9
code = IMG("figures/fig_hc18.png", "body_l", "body_top + 0.05", fw, "body_h - 0.45")
rx, rwid = f"body_l + {fw + 0.3}", round(12.3 - fw - 0.3, 2)
code += T("PASS RATE MINUS SPECIALIST · 95 % CI", rx, "body_top + 0.05", rwid, 0.3, 11, MUT, "MONO_FONT", True)
lines = []
for mo, lab, col in ((O5, "Opus", "TURQUOISE_RGB"), (S5, "Sonnet", "DEEPPINK_RGB")):
    for a in per_attempt("measure_hc18", mo):
        lines.append((f"{lab} {a['attempt'].split()[0]}", ci(a["pass_diff"]), col))
for i, (lab, txt, col) in enumerate(lines):
    y = f"body_top + 0.42 + {i * 0.40:.2f}"
    code += T(lab, rx, y, 1.3, 0.35, 12, col, "MONO_FONT", True)
    code += T(txt, f"{rx} + 1.3", y, rwid - 1.3, 0.35, 12, PRI, "MONO_FONT")
code += R(rx, "body_top + 3.0", rwid, 1.35, "SURFACE_RGB") + R(rx, "body_top + 3.0", 0.08, 1.35, "AMBER_RGB")
code += T(f"Specialist U-Net: 83/83 within 4.9 %, mean error {att2('measure_hc18', OPUS)['specialist']['mean_abs_err_mm']:.2f} mm. "
          "Agents: mean error 6.6 to 18.0 mm; no attempt reaches the 90 % family bar. "
          "The best attempt, Sonnet R3, is 74/83.",
          f"{rx} + 0.25", "body_top + 3.1", rwid - 0.4, 1.2, 12, ONS)
code += FOOT("Source: docs/research/suite/hosted-agents2.json (R1) and hosted-agents3.json (R2, R3); suite/clinical-v1@2. Per-image limit: 4.9 % of the hidden reference.")
slides["h2-fetal-head-circumference-error-per-hidden-image-six-attempts"] = dict(
    title="Fetal head circumference — error per hidden image, six attempts",
    code=code,
    notes=("Each column is one system; each dot one of the 83 hidden ultrasound images. The vertical axis is the absolute error in head circumference in millimetres, on a log scale. Filled dots are within the clinical tolerance, 4.9 % of the true circumference, which is the limit of agreement between two sonographers; hollow dots are outside it. "
           "The specialist, a U-Net trained on separate images, is within tolerance on every image, with a mean error of about 2 millimetres. "
           "The six agent attempts pass between 35 and 74 of 83. On the right are the paired differences in pass rate against the specialist, with 95 % intervals: all six are clearly below zero, so every attempt shows a gap under our rule. For example, minus 0.145 means about 15 fewer images out of 100 within tolerance. "
           "The agents mostly built pixel classifiers plus an ellipse fit from 152 labelled images in under half an hour on a CPU; the failures are gross misses on some images rather than small biases. "
           "Transition: why do they stop there? One trace shows it."),
)

# ------------------------------------------------------------------ timeline failure
o_hc = att2("measure_hc18", OPUS)
k_below = sum(s["stopped_below_bar_by_own_estimate"] for s in KW["summary"] if s["arm"] == "K")
cards = [
    ("WHAT IT KNEW", "Its own 4-fold check: \"about 60% … well below the 90% target, so expect a headline score around 0.6\".", "AMBER_RGB"),
    ("WHAT IT DID", f"Ended its turn at {o_hc['session_minutes_to_first_answer_or_end']} of 45 minutes. Hidden result: 35/83 (42 %); specialist 83/83.", "TURQUOISE_RGB"),
    ("NOT A ONE-OFF", f"11 of 12 new per-case attempts in R, {k_below} of 6 in K and 6 of 6 in K2 (told to check the clock) ended with their own estimate below the bar.", "DEEPPINK_RGB"),
]
code = IMG("figures/fig_timeline.png", "body_l", "body_top + 0.05", "body_w", 2.75)
cw = 12.3 / 3
for i, (k, t, c) in enumerate(cards):
    x = f"body_l + {i * cw:.2f}"
    y = "body_top + 3.0"
    code += R(x, y, round(cw - 0.18, 2), 1.9, "SURFACE_RGB") + R(x, y, round(cw - 0.18, 2), 0.07, c)
    code += T(k, f"{x} + 0.22", f"{y} + 0.2", round(cw - 0.6, 2), 0.35, 13, c, "MONO_FONT", True)
    code += T(t, f"{x} + 0.22", f"{y} + 0.62", round(cw - 0.6, 2), 1.2, 13, ONS)
code += FOOT("Sources: hosted-agents2.md 'measure_hc18 · Opus' (run 1f2e6208-f148-4aaa-b72f-5225bed3b745); hosted-agents3.md; hosted-keepworking1.md; hosted-clockcheck1.md. Quotes are from the trace.")
slides["h2-one-trace-opus-5-5-on-fetal-head-stops-at-11-6-of-45-minutes"] = dict(
    title="One trace — Opus 5.5 on fetal head stops at 11.6 of 45 minutes",
    code=code,
    notes=("This is one concrete failure, read from the full trace. The bar is the 45-minute session. Opus did the right first thing: within seconds it wrote a baseline pipeline that outputs a constant perimeter, so it would never ship nothing. "
           "It then built a pixel classifier and ellipse fit, and checked itself with 4-fold cross-validation. Its own words: about 60 %, well below the 90 % target, expect a score around 0.6. "
           "And then, at 11.6 minutes, it ended its turn, with more than 30 minutes left. The hidden result was 42 %, worse than its own estimate, against 100 % for the specialist. "
           "The point is not that the model could not measure; it is that it knew it was below the clinical bar and stopped anyway. The instruction states the time limit, so this is not our bug. "
           "And it repeats: in round 3, 11 of the 12 new attempts on the per-case tasks said they were below the bar when they stopped. "
           "Transition: many of them also said they had run out of time, which they had not."),
)

# ------------------------------------------------------------------ out of time + K / K2
fw = 6.9
code = IMG("figures/fig_elicitation.png", "body_l", "body_top + 0.05", fw, "body_h - 0.45")
rx, rwid = f"body_l + {fw + 0.3}", round(12.3 - fw - 0.3, 2)
quotes = [("Opus · fetal head R3", "\"I stopped there because of the session limit.\"", "8.1 / 45 min"),
          ("Sonnet · fetal head K3", "\"… which I ran out of session time for.\"", "11.0 / 45 min"),
          ("Opus · registration R2", "\"I ran out of session time before closing it.\"", "14.5 / 45 min")]
for i, (who, q, tm) in enumerate(quotes):
    y = f"body_top + 0.05 + {i * 0.82:.2f}"
    code += R(rx, y, rwid, 0.72, "SURFACE_RGB")
    code += T(who, f"{rx} + 0.18", f"{y} + 0.05", rwid - 1.8, 0.28, 10.5, "AMBER_RGB", "MONO_FONT", True)
    code += T(tm, f"{rx} + {rwid - 1.6:.2f}", f"{y} + 0.05", 1.45, 0.28, 10.5, "AMBER_RGB", "MONO_FONT", True, align="RIGHT")
    code += T(q, f"{rx} + 0.18", f"{y} + 0.34", rwid - 0.3, 0.36, 11.5, ONS, italic=True)
k_txt = (f"K · \"keep working while below the bar\": all 6 still stopped below it. Mean reward Opus {k_o['mean_reward']:.3f} "
         f"(R {r_o['mean_reward']:.3f}), Sonnet {k_s['mean_reward']:.3f} (R {r_s['mean_reward']:.3f}): within attempt-to-attempt spread.")
if K2S:
    ko2, ks2 = K2S.get(O5), K2S.get(S5)
    k2_txt = ("K2 · \"check the clock\": all 6 read it and stated the time correctly, then still stopped below "
              f"the bar with 8–31 min left. Mean reward Opus {ko2['mean_reward']:.3f}, Sonnet {ks2['mean_reward']:.3f} "
              "(one 0: 2 images over the 10 s limit).")
else:
    k2_txt = "K2 · \"run date and check the time\": 3 attempts per model, results pending."
code += R(rx, "body_top + 2.55", rwid, 0.95, "SURFACE_RGB") + R(rx, "body_top + 2.55", 0.08, 0.95, "TURQUOISE_RGB")
code += T(k_txt, f"{rx} + 0.22", "body_top + 2.61", rwid - 0.35, 0.85, 11.5, ONS)
code += R(rx, "body_top + 3.65", rwid, 0.95, "SURFACE_RGB") + R(rx, "body_top + 3.65", 0.08, 0.95, "BLUEVIOLET_RGB")
code += T(k2_txt, f"{rx} + 0.22", "body_top + 3.71", rwid - 0.35, 0.85, 11.5, ONS)
code += FOOT("Sources: hosted-agents3.md 'Session use, endings and time'; hosted-keepworking1.md; hosted-clockcheck1.md. K and K2 are separate task versions, never pooled with R.")
slides["h2-stated-time-pressure-early-endings-and-two-instruction-tests"] = dict(
    title="Stated time pressure — early endings and two instruction tests",
    code=code,
    notes=("The chart shows every fetal head attempt: how much of the 45-minute session it used, left to right, against the share of hidden images within tolerance, bottom to top. Circles are the three normal attempts per model; squares and triangles are attempts with extra instruction paragraphs. The dashed line is the 90 % bar. "
           "On the right are things agents wrote when they stopped. 'I stopped there because of the session limit', at 8 of 45 minutes. 'I ran out of session time', at 11 and at 14 minutes. Claude Code shows the agent no clock, the instruction gives the limit but not the start time, and no fetal head attempt in R or K checked the clock. "
           "We tested two fixes as separate task versions, each registered before its own runs and never pooled with the main results. K, the squares, adds a paragraph saying that being below the bar is a reason to keep working. It did not change the ending: all six agents read it, said they were below the bar, and stopped anyway. "
           "K2, the triangles, also tells the agent to run the date command at the start and before stopping. It worked as an instruction: every agent read the clock, stated the remaining time correctly, and none claimed to be out of time. Sessions got longer, and Opus scored a little higher and more consistently. "
           "But all six still stopped below the bar, now knowingly, with 8 to 31 minutes left: 'I stopped with about 18 of the 45 minutes left rather than make untested changes to a working pipeline.' One Sonnet attempt scored zero because a last-minute speed change pushed two images past the 10-second limit. "
           "So the belief about time was real, but fixing it does not remove the early stopping. With three attempts per arm, the reward differences are descriptive. "
           "Transition: one task where the agents came close to the specialist."),
)

# ------------------------------------------------------------------ vessel
code = IMG("figures/fig_vessel.png", "body_l", "body_top", "body_w", 3.55)
tiles = [(f"{ves_o['n_acceptable']}/8", "Opus 5.5", f"Dice {ves_o['mean_dice']:.3f} · clDice {ves_o['mean_cldice']:.3f}", "TURQUOISE_RGB"),
         (f"{ves_s['n_acceptable']}/8", "Sonnet 5.5", f"Dice {ves_s['mean_dice']:.3f} · clDice {ves_s['mean_cldice']:.3f}", "DEEPPINK_RGB"),
         (f"{VES['specialist']['n_acceptable']}/8", "Specialist U-Net", f"Dice {VES['specialist']['mean_dice']:.3f} · clDice {VES['specialist']['mean_cldice']:.3f}", "AMBER_RGB")]
for i, (big, who, sub, c) in enumerate(tiles):
    x = f"body_l + {i * 2.55:.2f}"
    code += T(big, x, "body_top + 3.65", 2.4, 0.6, 28, c, "MONO_FONT", True)
    code += T(who, x, "body_top + 4.25", 2.4, 0.3, 12, PRI, "MONO_FONT", True)
    code += T(sub, x, "body_top + 4.55", 2.5, 0.3, 10.5, PRI, "MONO_FONT")
code += R("body_l + 7.75", "body_top + 3.65", 4.55, 1.2, "SURFACE_RGB") + R("body_l + 7.75", "body_top + 3.65", 0.08, 1.2, "BLUEVIOLET_RGB")
code += T("On the 6 images the specialist passes, every agent miss is a clDice shortfall under 0.02: thin vessels left disconnected. No gap can be shown unless 3 of 6 fail. One attempt per model.",
          "body_l + 7.98", "body_top + 3.72", 4.2, 1.1, 11.5, ONS)
code += FOOT("Source: docs/research/suite/seg_vessel.md section 7; per-image values docs/research/suite/data/seg_vessel_per_image.csv. Runs 123e97b9 (Opus), 8c5fa3ce (Sonnet).")
slides["h2-retinal-vessels-near-parity-with-the-specialist"] = dict(
    title="Retinal vessels — near-parity with the specialist",
    code=code,
    notes=("A new task this round: segment the blood vessels in 8 hidden retinal photographs of children's eyes. The bar on each image is set by a second human expert: the pipeline must agree with the first expert at least as well as the second expert did, on two measures. Dice is plain overlap; clDice, centreline Dice, checks whether thin vessels stay connected. "
           "In the chart, each column is one hidden image; the short black tick is the second expert's score, which is the bar; the diamond is the specialist and the dots are the agents. Hollow means that image failed. "
           "Both agents trained a small U-Net from scratch on the 20 development images, on a CPU, in about 20 to 35 minutes. On average their overlap is higher than the second human's, 0.83 against 0.78. Opus passes 5 of 8 images, Sonnet 4 of 8, against 6 of 8 for a specialist trained on a GPU. On the two hardest images, which the specialist also fails, they miss on both measures; on the six the specialist passes, every miss is on connectivity, by less than 0.02. "
           "So this is near-parity, not a demonstrated gap; with 6 images the specialist passes, we could only show a gap if an agent failed at least 3 of them. "
           "Transition: the limits of all this."),
)

# ------------------------------------------------------------------ limits + how to run
lims = [
    ("FEW ATTEMPTS", f"Three per task and model; one for vessels. The spread is large: Opus fetal head {min(hc_o['rewards']):.2f} to {max(hc_o['rewards']):.2f}."),
    ("SMALL HIDDEN SETS", "6 cases for registration and spleen, 8 for vessels, so 'no gap shown' there is underpowered, not parity."),
    ("SETTINGS", "Claude Code default effort, not high. Raw mm and Dice come from local regrades (28 of 30 match every hosted key)."),
    ("PUBLIC DATA", "Contamination risk. No recalled labels, no web use; Opus knew ICU data quirks before looking."),
]
code = ""
for i, (k, t) in enumerate(lims):
    y = f"body_top + 0.05 + {i * 1.2:.2f}"
    code += R("body_l", y, 0.08, 1.02, "DEEPPINK_RGB")
    code += T(k, "body_l + 0.25", y, 5.5, 0.3, 12, "DEEPPINK_RGB", "MONO_FONT", True)
    code += T(t, "body_l + 0.25", f"{y} + 0.32", 5.6, 0.75, 12.5, PRI)
cx, cwid = "body_l + 6.25", 6.05
cmd = ("V=.venv-valkyrie/bin/valkyrie\n"
       "$V agent push agents/claude_code_noweb\n"
       "$V run start \\\n  --agent claude_code_noweb-v1.0.0 \\\n  --dataset suite/clinical-v1@instr2 \\\n"
       "  --model anthropic/claude-opus-5-5 \\\n  --provider modal --concurrency 3 \\\n"
       "  -s ANTHROPIC_API_KEY anthropic-api-key\n"
       "# also: suite/vessel-v1@1, suite/causal-v1@1")
code += T("HOW TO RUN", cx, "body_top + 0.05", cwid, 0.3, 12, "TURQUOISE_RGB", "MONO_FONT", True)
code += R(cx, "body_top + 0.45", cwid, 2.65, "SURFACE_RGB")
code += T(cmd, f"{cx} + 0.25", "body_top + 0.6", cwid - 0.4, 3.0, 11.5, ONS, "MONO_FONT")
code += T("Tasks in Harbor format; hidden cases and specialist outputs stay on the verifier side. Data sources, licences and every run ID: README.",
          cx, "body_top + 3.3", cwid, 0.6, 12, PRI)
code += FOOT("Sources: README 'Limitations' and 'How to run'; docs/research/suite/round3-results.md (deviations from the preregistration).")
slides["h2-limits-and-how-to-run"] = dict(
    title="Limits and how to run",
    code=code,
    notes=("Be direct about the limits. Three attempts per task and model is better than one, but it is not a variance estimate, and the spread is large: the same model on the same fetal head task scored anywhere from 0.42 to 0.86. "
           "Registration, spleen and vessels have only six to eight hidden cases, so 'no gap shown' there means not enough data, not proof of parity. "
           "The hosted agent ran at Claude Code's default effort, not high. Valkyrie does not keep our grader's detailed metrics file, so raw millimetre and Dice values come from regrading each saved pipeline locally; those regrades match every hosted reward key in 28 of 30 headline attempts, and the two exceptions are explained in the README. "
           "All data are public, so contamination is possible; we saw no recalled labels and no web use. "
           "On the right is how anyone can rerun it on Valkyrie: push the no-web Claude Code agent, start a run on the dataset. Everything, including every run ID, is in the README. "
           "Close with thanks; the slides after this are backup for questions."),
)

# ------------------------------------------------------------------ backups
short = {"reg_resect": "reg", "seg_spleen": "spleen", "measure_hc18": "fetal head", "ecg_ptbxl": "ECG", "risk_icu": "ICU"}
S_n = {"reg_resect": 4, "seg_spleen": 3, "measure_hc18": 83}


def vtext(fam, a):
    v = a["gap_verdict"]
    if fam in ("ecg_ptbxl", "risk_icu"):
        return "gap: misses MI part" if v.startswith("gap") else "no gap (all parts)"
    failed = v.split("(")[1].split(" of ")[0] if "(" in v and " of " in v else "0"
    if fam == "measure_hc18":
        return "gap " + ci(a["pass_diff"])
    if v.startswith("gap"):
        return f"gap · {failed}/{S_n[fam]} failed"
    if v.startswith("no gap shown"):
        return f"no gap shown · {failed}/{S_n[fam]} failed"
    return "no gap · 0 failed"


rows = [["Task · model", "R1", "R2", "R3", "Gap shown"]]
for fam in ("measure_hc18", "reg_resect", "seg_spleen", "ecg_ptbxl", "risk_icu"):
    for mo in (O5, S5):
        ats = per_attempt(fam, mo)
        rows.append([f"{short[fam]} · {'Opus' if mo == O5 else 'Sonnet'}"] + [vtext(fam, a) for a in ats]
                    + [f"{pooled(fam, mo)['gap_shown_in']} of 3"])
rows.append(["vessel · Opus", "no gap shown · 1/6 failed", "–", "–", "0 of 1"])
rows.append(["vessel · Sonnet", "no gap shown · 2/6 failed", "–", "–", "0 of 1"])
code = TABLE(rows, [2.0, 2.95, 2.95, 2.95, 1.45], "body_l", "body_top + 0.0", 0.355, "TURQUOISE_RGB", 10)
code += T("S = hidden cases the specialist passes (reg 4, spleen 3, fetal head 83, vessel 6). Paired bootstrap, agent minus specialist, 2,000 resamples, seed 20261114. "
          "Gap shown when the agent fails a case in S and the 95 % interval lies below 0; fetal head cells give the pass-rate difference and interval. Cohort tasks: gap if a gate part the specialist meets is missed.",
          "body_l", "body_top + 4.68", "body_w", 0.55, 10, PRI)
code += FOOT("Source: docs/research/suite/hosted-agents3.json pooled_3_attempts and per_attempt_including_run2; seg_vessel.md section 7; DESIGN.md gap rule.")
slides["h1-backup/h2-gap-verdicts-every-attempt-specialist-passed-cases"] = dict(
    title="Gap verdicts — every attempt, specialist-passed cases",
    code=code,
    notes=("The exact gap rule and every verdict. For the per-case tasks we take only the hidden cases the specialist passes, called S, and compute agent minus specialist pass rate with a paired bootstrap interval. "
           "A gap is claimed only when the agent fails at least one of those cases and the whole interval is below zero. Fetal head shows a gap in all six attempts, with intervals far from zero. "
           "Registration and spleen have S of 4 and 3, so a gap can only be shown when an agent fails most of them; 'no gap shown' there means the interval reaches zero, which is underpowered rather than reassuring. "
           "For ECG and ICU, the cohort rule applies: a gap if the agent misses a gate part the specialist meets. Opus missed the heart-attack sensitivity part once, at 0.693 against 0.70."),
)

code = IMG("figures/fig_reward_keys.png", "body_l", "body_top", "body_w", "body_h - 0.4")
code += FOOT("Source: docs/research/suite/hosted-agents3.json per_attempt_including_run2 (hosted grades). Reward = clinically_acceptable when ran, valid and within_time are all 1.")
slides["h1-backup/h2-reward-keys-for-every-headline-attempt"] = dict(
    title="Reward keys for every headline attempt",
    code=code,
    notes=("All seven reward keys for all 30 headline attempts, as graded on Valkyrie. Ran, valid and within-time are 1 almost everywhere, so pipelines delivered a valid output in time and the lost reward is clinical acceptability. "
           "The one exception is Opus registration attempt 3: one hidden case put landmarks more than 10 millimetres outside the ultrasound image, so valid is 0.833 and the reward is 0. "
           "Quality maps each family's primary metric to 0 to 1, and vs-specialist is quality divided by the specialist's, capped at 1."),
)

fw = 7.6
code = IMG("figures/fig_session.png", "body_l", "body_top + 0.05", fw, "body_h - 0.45")
rx, rwid = f"body_l + {fw + 0.35}", round(12.3 - fw - 0.35, 2)
code += T(f"0 / {n_session_attempts}", rx, "body_top + 0.05", rwid, 0.8, 40, "AMBER_RGB", "MONO_FONT", True)
code += T("attempts reached their session limit; every one ended its own turn", rx, "body_top + 0.9", rwid, 0.7, 13, PRI)
code += T(f"{max_used * 100:.0f} %", rx, "body_top + 1.85", rwid, 0.8, 40, "TURQUOISE_RGB", "MONO_FONT", True)
code += T(f"the longest session used ({max_who})", rx, "body_top + 2.7", rwid, 0.5, 13, PRI)
code += R(rx, "body_top + 3.4", rwid, 1.3, "SURFACE_RGB") + R(rx, "body_top + 3.4", 0.08, 1.3, "DEEPPINK_RGB")
code += T("Ending early is fine on the controls (ICU in under 5 minutes). On fetal head, registration and spleen, agents stopped below the bar.",
          f"{rx} + 0.25", "body_top + 3.5", rwid - 0.4, 1.15, 12, ONS)
code += FOOT("Sources: hosted-agents3.json, hosted-keepworking1.json, hosted-clockcheck1.json, data/seg_vessel_summary.json, data/causal_ate_summary.json, data/report_label_summary.json.")
slides["h1-backup/h2-session-use-every-attempt-in-every-workstream"] = dict(
    title="Session use — every attempt in every workstream",
    code=code,
    notes=("Each dot is one attempt, placed by the share of its session it used before it ended its own turn. None was ever stopped by the limit; the longest used " + f"{max_used * 100:.0f}" + " %. "
           "On the control tasks this is fine: Sonnet solved ICU risk in under two minutes and every causal attempt passed in under 12 minutes. "
           "On the hard tasks it is the failure we keep seeing: agents stop with most of the time unused while saying they are below the bar."),
)

s_rg = att2("reg_resect", SONNET)
o_rg = att2("reg_resect", OPUS)
rows = [["Case", "Uncorrected", "Specialist", "Opus 5.5", "Sonnet 5.5"]]
unc = {"c18b03": "6.39", "c57eed": "3.39", "c65c1b": "5.68", "cb06b4": "4.55", "cdd96a": "10.06", "ce4785": "7.01"}
for co, cs in zip(o_rg["gap"]["per_case"], s_rg["gap"]["per_case"]):
    rows.append([co["case"], unc[co["case"]],
                 f"{co['specialist_mean_tre_mm']:.2f}" + (" ✓" if co["specialist_acceptable"] else ""),
                 f"{co['agent_mean_tre_mm']:.2f}" + (" ✓" if co["agent_acceptable"] else ""),
                 f"{cs['agent_mean_tre_mm']:.2f}" + (" ✓" if cs["agent_acceptable"] else "")])
code = TABLE(rows, [1.3, 1.45, 1.4, 1.3, 1.35], "body_l", "body_top + 0.05", 0.5, "DEEPPINK_RGB", 12)
qx, qw = "body_l + 7.2", 5.1
code += R(qx, "body_top + 0.05", qw, 3.45, "SURFACE_RGB") + R(qx, "body_top + 0.05", 0.08, 3.45, "DEEPPINK_RGB")
code += T("FROM THE TRACE (R1)", f"{qx} + 0.25", "body_top + 0.2", qw - 0.4, 0.3, 12, "DEEPPINK_RGB", "MONO_FONT", True)
code += T("\"Conservative fallback: image-based rigid registration … was consistently WORSE than the navigation alignment, so landmarks are passed through.\"",
          f"{qx} + 0.25", "body_top + 0.6", qw - 0.45, 1.5, 13, ONS, italic=True)
code += T("\"I didn't try deformable registration … I stopped partway through the 45 minutes.\"",
          f"{qx} + 0.25", "body_top + 2.2", qw - 0.45, 1.1, 13, ONS, italic=True)
code += T(f"R2 and R3: rewards {rg_s['rewards'][1]:.3f} and {rg_s['rewards'][2]:.3f}; R3 ended at 2.1 minutes with landmarks essentially uncorrected. Gap shown in 3 of 3.",
          qx, "body_top + 3.7", qw, 0.9, 11.5, PRI)
code += T("R1 (hosted run 2): mean TRE in mm per hidden case. ✓ = under 2.0 mm and below the uncorrected error.",
          "body_l", "body_top + 3.7", 6.8, 0.6, 11, PRI)
code += FOOT("Sources: hosted-agents2.md 'reg_resect · Sonnet' (run 5110a198-2582-414a-a9fd-81cc15103cdd); hosted-agents3.md 'Registration'.")
slides["h1-backup/h2-sonnet-5-5-on-registration-a-no-op-pipeline-after-3-minutes"] = dict(
    title="Sonnet 5.5 on registration — a no-op pipeline after 3 minutes",
    code=code,
    notes=("A second concrete failure. Sonnet tried rigid registration with several similarity measures on the four development cases, found them worse than doing nothing, and shipped a pipeline that copies the MRI landmarks unchanged. "
           "So its hidden errors equal the uncorrected column exactly, mean 6.18 millimetres, and it fails all four cases the specialist passes. It stopped after three minutes of a 45-minute session, saying itself that it had not tried deformable registration. "
           "In its two repeat attempts it shipped translation-only pipelines that were no better: one case passed once, and the third attempt ended after about two minutes. A gap in three of three. "
           "A sign or axis error in its search would explain why its registrations were worse than none; that is our reading of the trace, not verified."),
)

trust = [
    ("HIDDEN CASES", "Hidden inputs, references and specialist outputs exist only in the verifier sandbox; the exporter refuses to write if any would reach the agent.", "TURQUOISE_RGB"),
    ("ORACLE CHECK", "Before any agent run, each dataset's reference solution reproduced its expected reward on Valkyrie: six datasets, every one matched.", "AMBER_RGB"),
    ("NETWORK", "Agent network limited to api.anthropic.com (PyPI and the web unreachable); WebFetch and WebSearch removed; zero web requests in every trace read.", "DEEPPINK_RGB"),
    ("PRESPECIFIED", "Thresholds fixed before any agent result; round 3 preregistered, every deviation listed in round3-results.md; nothing rerun for a better number.", "BLUEVIOLET_RGB"),
]
code = ""
for i, (k, t, c) in enumerate(trust):
    x = f"body_l + {(i % 2) * 6.2:.2f}"
    y = f"body_top + 0.1 + {(i // 2) * 2.45:.2f}"
    code += R(x, y, 6.0, 2.25, "SURFACE_RGB") + R(x, y, 6.0, 0.07, c)
    code += T(k, f"{x} + 0.3", f"{y} + 0.25", 5.4, 0.35, 15, c, "MONO_FONT", True)
    code += T(t, f"{x} + 0.3", f"{y} + 0.75", 5.4, 1.4, 14, ONS)
code += FOOT("Sources: hosted-oracle1.md, README 'Hosted checks of the reference solutions', hosted-agents3.md 'Trace findings', round3-prereg.md, round3-results.md.")
slides["h1-backup/h2-why-the-numbers-can-be-trusted"] = dict(
    title="Why the numbers can be trusted",
    code=code,
    notes=("If asked how we know the scores are real. The hidden cases never reach the agent: the exporter checks this and refuses to write a task that would leak them. "
           "Before any agent ran on a dataset, its reference solution was run on Valkyrie and reproduced its locally measured reward, for all six datasets, so image, artifact carry and verifier work. "
           "The agent could only reach the Anthropic API, we confirmed PyPI and the open web were unreachable, we removed Claude Code's web tools, and no trace made a web request. "
           "Round 3 was preregistered before any run, and every change after that is listed with its time and reason."),
)

code = ""
panels = [
    ("HOSTED RUN 1 · instructions v2 · suite/clinical-v1@1",
     "Session limit not stated. The limit killed 5 of 10 attempts (registration and spleen for both models, fetal head for Opus), classed not interpretable under the rule fixed before results. "
     "ECG and ICU were controls. Only interpretable gap: Sonnet fetal head 72/83, pass diff −0.133 (−0.205 to −0.060). Runs 0ae696de / 1a4037a0.", "AMBER_RGB"),
    ("LOCAL PILOT 1 · instructions v1 · bubblewrap, effort high",
     "Fetal head: Opus 0.928, Sonnet 0.819, both gaps shown. Registration: both 0, a delivery failure at the deadline (Opus wrote run.sh 2.5 minutes before the end and never ran it), not an accuracy gap.", "BLUEVIOLET_RGB"),
    ("THE FIX · instructions v3 · suite/clinical-v1@2",
     "One added section states the session limit and that the pipeline is graded as found. Since then no attempt, in run 2 or round 3, has reached its limit.", "TURQUOISE_RGB"),
]
for i, (k, t, c) in enumerate(panels):
    y = f"body_top + 0.05 + {i * 1.75:.2f}"
    code += R("body_l", y, "body_w", 1.6, "SURFACE_RGB") + R("body_l", y, 0.08, 1.6, c)
    code += T(k, "body_l + 0.3", f"{y} + 0.15", 11.6, 0.3, 13, c, "MONO_FONT", True)
    code += T(t, "body_l + 0.3", f"{y} + 0.55", 11.7, 1.0, 13, ONS)
code += FOOT("Sources: docs/research/suite/hosted-agents1.md, pilot1-results.md, instructions-v3.md. Earlier rounds are never pooled with the headline.")
slides["h1-backup/h2-earlier-runs-the-session-limit-bug-and-its-fix"] = dict(
    title="Earlier runs — the session-limit bug and its fix",
    code=code,
    notes=("Our own bug, stated plainly. The first two rounds did not tell the agent how long its session was, or that whatever pipeline existed at the end would be graded. Agents planned work that could not fit and were killed mid-task, so we classed those attempts as not interpretable rather than as model failures. "
           "Instructions v3 added one section fixing this, published as dataset version 2; that version is the headline. "
           "The earlier rounds agree on fetal head: Sonnet showed a gap in every round. Opus scored 0.928 in both earlier rounds and 0.42 to 0.86 in the headline attempts, though instructions, sandbox and effort differed."),
)

rl = {r["name"].split(" (")[0].split(" =")[0]: r for r in RL.get("rows", RL.get("labellers", []))} if isinstance(RL, dict) else {}
fw = 6.6
code = IMG("figures/fig_report_label.png", "body_l", "body_top + 0.05", fw, "body_h - 0.45")
rx, rwid = f"body_l + {fw + 0.3}", round(12.3 - fw - 0.3, 2)
cards = [
    ("NOT A PASS, NOT SCORED", "Opus 5.5 macro F1 0.790 vs specialist 0.735: +0.055 (+0.025 to +0.086). It met the kappa part but missed F1 0.80 by 0.0099. No comparator passes, so the family is excluded.", "TURQUOISE_RGB"),
    ("LABEL CEILING", "Identical report text carries different labels in 6.7 % of repeated development texts: a validating cardiologist could change codes without changing the report.", "AMBER_RGB"),
    ("DELEGATED TO API CALLS", "Opus sent hidden reports in batches to claude-opus-5-5; Sonnet had claude-haiku-5-5 tag all 2,500. That spend is not in Claude Code's cost (Opus: \"about $0.16\", unverified).", "DEEPPINK_RGB"),
]
code += side_cards(cards, rx, rwid, "body_top + 0.05", 1.5, size=11.5, head=11.5)
code += FOOT("Source: docs/research/suite/label_ptbxl_reports.md sections 2–4; data/report_label_summary.json. Runs 60111604 (Opus), e1d46b7a (Sonnet), oracle 72b3ac93.")
slides["h1-backup/h2-report-labelling-excluded-from-scoring-worked-example"] = dict(
    title="Report labelling — excluded from scoring, worked example",
    code=code,
    notes=("This family asked agents to read 500 free-text ECG reports, mostly German, and assign five diagnostic classes. It was meant as a control, and its bar was fixed before any result: Cohen's kappa, an agreement measure that corrects for chance, of at least 0.60 in every class, and macro F1 of at least 0.80. "
           "Neither comparator reached it, so we excluded the family before any agent ran, as the preregistration required. The reason is in the data: the same report text carries different labels in about 7 % of repeated texts, so no method can be fully right. "
           "The agents ran anyway, reported descriptively. Opus beat the specialist by 5.5 F1 points with an interval clear of zero, but missed the F1 bar by one hundredth. "
           "The interesting behaviour: neither agent read the reports itself. Both wrote scripts that called the model API from inside the sandbox, Opus calling Opus and Sonnet calling Haiku. The rules allow that host, but the cost of those calls is not in the cost Claude Code reports."),
)

code = IMG("figures/fig_causal.png", "body_l", "body_top", "body_w", 3.3)
cards = [
    ("CONTROL", "Specialist covers the true effect in 47 of 48 datasets; all 6 agent attempts in 48 of 48, RMSE 0.039–0.043 sd. All four gate parts met by everyone.", "AMBER_RGB"),
    ("METHOD NAMED", "The instruction names the specialist's estimator (cross-fitted doubly robust, AIPW), as every family names its comparator. All six attempts built it.", "TURQUOISE_RGB"),
    ("TUNED ON DEV", "All six widened their intervals by a factor picked on the development data (×1.3 to ×1.9). Sonnet changed it last and never re-ran: \"the final version is untested\".", "DEEPPINK_RGB"),
]
cw = 12.3 / 3
for i, (k, t, c) in enumerate(cards):
    x = f"body_l + {i * cw:.2f}"
    y = "body_top + 3.4"
    code += R(x, y, round(cw - 0.18, 2), 1.55, "SURFACE_RGB") + R(x, y, round(cw - 0.18, 2), 0.07, c)
    code += T(k, f"{x} + 0.2", f"{y} + 0.15", round(cw - 0.5, 2), 0.3, 12, c, "MONO_FONT", True)
    code += T(t, f"{x} + 0.2", f"{y} + 0.48", round(cw - 0.5, 2), 1.05, 11.5, ONS)
code += FOOT("Source: docs/research/suite/causal_ate.md; data/causal_ate_summary.json. Dataset suite/causal-v1@1; oracle 11115f4f. Gate after Dorie et al. 2019 (ACIC 2016).")
slides["h1-backup/h2-treatment-effect-a-control-family"] = dict(
    title="Treatment effect — a control family",
    code=code,
    notes=("A new family in round 3: estimate the effect of a treatment on the treated, with a 95 % confidence interval, on 48 hidden semi-synthetic datasets where we know the true effect. The covariates are real ICU patients; the treatment and outcome are generated by our own process modelled on the 2016 causal inference competition, because the competition's own data cannot be redistributed. "
           "The three panels show coverage, how often the interval contains the truth; root mean squared error; and interval width, each with its gate line. "
           "Everyone passes, so this is a control. Two honest caveats: the instruction names the specialist's method, and the agents widened their intervals by factors tuned on the development data, so their intervals are 25 to 75 % wider than the specialist's. Sonnet also changed that factor as its last edit and never re-checked it."),
)

fw = 6.7
code = IMG("figures/fig_pcnsl.png", "body_l", "body_top + 0.05", fw, "body_h - 0.45")
rx, rwid = f"body_l + {fw + 0.3}", round(12.3 - fw - 0.3, 2)
cards = [
    ("THE FIRST QUESTION", "Can frontier models predict mutation status in primary CNS lymphoma from imaging features? Public UCSF release: 64 patients with genomic records, 439 features.", "BLUEVIOLET_RGB"),
    ("NOTHING BEAT CHANCE RELIABLY", "Logistic regression MYD88 0.562 (permutation p = 0.27); TabPFN v2.5 0.420 / 0.386; GPT-5.2 on one fold 0.567 / 0.361; Opus 5.5 failed the response format.", "AMBER_RGB"),
    ("WHY THE SUITE MOVED", "With no comparator that succeeds, a frontier gap cannot be shown. The suite uses tasks where a specialist provably passes.", "TURQUOISE_RGB"),
]
code += side_cards(cards, rx, rwid, "body_top + 0.05", 1.5, size=11.5, head=11.5)
code += FOOT("Sources: pcnsl/results/20261114-{prediction-baselines,permutation,tabpfn-pilot,versa-pilot,hosted-release}/REPORT.md. Patient-level data stayed on UCSF servers.")
slides["h1-backup/h2-pcnsl-mutation-prediction-no-method-above-chance"] = dict(
    title="PCNSL mutation prediction — no method above chance",
    code=code,
    notes=("Where this project started. The original question was whether frontier models can predict gene mutations in primary central nervous system lymphoma from MRI features. On the public UCSF release, 64 patients with genetic records and 439 imaging features, no method gave reliable evidence of signal: AUROC, where 0.5 is a coin flip, stayed near or below 0.5 for TabPFN, a strong tabular model, and for GPT-5.2; a simple logistic model reached 0.56 for MYD88 with a permutation p-value of 0.27. "
           "The one higher number, 0.67 for a ten-feature model, is a descriptive internal cross-validation without a confidence interval. "
           "If nothing passes, a failure by frontier models cannot be told apart from a task that is impossible with these data. So we moved to tasks where a specialist provably succeeds, which is the design of this suite. All patient-level data stayed on UCSF servers."),
)

code = IMG("figures/fig_funnel.png", "body_l", "body_top", "body_w", 3.5)
code += R("body_l", "body_top + 3.7", "body_w", 0.85, "SURFACE_RGB") + R("body_l", "body_top + 3.7", 0.08, 0.85, "AMBER_RGB")
code += T("APTOS: Kaggle rules per a secondary source; Open-i: licence per third-party mirrors (official page down). "
          "The retinal vessel task uses CHASE_DB1 (CC BY 4.0) instead of DRIVE or STARE.",
          "body_l + 0.3", "body_top + 3.78", 11.8, 0.7, 12, ONS)
code += FOOT("Source: docs/research/suite/dataset-survey.md sections 1, 4 and 5. Valkyrie runs on Modal, a commercial service, so non-commercial and no-derivatives licences were excluded.")
slides["h1-backup/h2-dataset-selection-licence-clinical-bar-specialist-size"] = dict(
    title="Dataset selection — licence, clinical bar, specialist, size",
    code=code,
    notes=("How the datasets were chosen. The survey rated 50 candidate entries, some of them variants of one source, in four steps. First the licence: the task image is uploaded to a commercial platform, so the data must allow redistribution, which means CC BY, CC BY-SA or ODC-By; anything non-commercial or no-derivatives is out. Second, a clinical measure with a published bar. Third, a specialist that actually passes that bar on our hidden cases. Fourth, a size that fits in a task image. "
           "Most of the datasets from Jin's course material failed at the first step: the skin-lesion set HAM10000 is non-commercial, the APTOS retina set is under Kaggle's competition rules, the Open-i chest X-ray reports are non-commercial no-derivatives, and the DRIVE and STARE vessel sets state no licence at all. That is why the vessel task uses CHASE_DB1, which is CC BY."),
)

cost_rows = [["Round", "Runs", "Attempts", "API cost"],
             ["Hosted run 2 = R1", "1f2e6208 · 5110a198", "10", "$3.77"],
             ["Round 3 · R2, R3", "7db8faca · 39d574d3 · a3525e04 · 5378cf20", "20", "$6.60"],
             ["Round 3 · K (keep working)", "f8a4f7b6 · 0e58cc29 · 7a155d74 · 6c5f28d3 · …", "6", "$2.73"],
             ["Round 3 · K2 (clock check)", "42343602 · 964a63e9 · 6d6a9980 · …", "6", "$5.11"],
             ["Round 3 · vessel", "123e97b9 · 8c5fa3ce", "2", "$1.01"],
             ["Round 3 · causal", "bd885935 · f0c183b4 · c5bfb9c1 · c4e354b9 · …", "6", "$1.26"],
             ["Round 3 · report labels", "60111604 · e1d46b7a", "2", "$0.39 + sandbox calls"],
             ["Hosted run 1 (v2) + smoke", "0ae696de · 1a4037a0 · cea5e542", "11", "≈ $7.30"]]
code = TABLE(cost_rows, [3.3, 5.4, 1.2, 2.4], "body_l", "body_top + 0.05", 0.42, "TURQUOISE_RGB", 11)
code += T("≈ $28.16", "body_l", "body_top + 3.95", 3.4, 0.7, 30, "AMBER_RGB", "MONO_FONT", True)
code += T("hosted API total at list price, 63 attempts, without the report-label agents' own model calls. Modal sandbox cost is not reported by Valkyrie.",
          "body_l + 3.5", "body_top + 4.0", 8.8, 0.7, 12, PRI)
code += FOOT("Sources: README 'Cost' and 'Run identifiers' (full run IDs); hosted-agents1/2/3.md, hosted-keepworking1.md, seg_vessel.md, causal_ate.md, label_ptbxl_reports.md, hosted-clockcheck1.md.")
slides["h1-backup/h2-cost-and-run-identifiers"] = dict(
    title="Cost and run identifiers",
    code=code,
    notes=("Run identifiers for anyone who wants to inspect the traces on Valkyrie, shortened here; the README has every full ID. "
           "The cost is the Claude Code figure at list price. All hosted agent runs together cost about 28 dollars, partly because every agent stopped early. Two things are not in that number: the model calls the report-label agents made themselves from inside the sandbox, and Modal's sandbox cost, which Valkyrie does not report. Round 3 stayed far under its preregistered 60-dollar stop rule."),
)

rows = [["Task", "Clinical threshold", "Source", "Time limit"],
        ["Registration", "mean TRE < 2.0 mm and below initial error", "Gerard et al. 2021; AAPM TG-132", "120 s per case"],
        ["Spleen", "Dice ≥ 0.94 and volume error ≤ 10 %", "Humpire-Mamani 2020; 10 % our convention", "300 s per case"],
        ["Fetal head", "error ≤ 4.9 % of reference; bar ≥ 90 % of images", "Sarris et al. 2012; bar our convention", "10 s per image"],
        ["Vessels", "Dice and clDice ≥ second observer on each image", "Fraz et al. 2012; Shit et al. 2021", "60 s per image"],
        ["ECG", "MI sens. ≥ 0.70 at spec. 0.90; ECE ≤ 0.05; subgroup gap ≤ 0.05", "Willems 1991; others our convention", "560 s per cohort"],
        ["ICU risk", "event-1 ≥ SAPS-I + 0.05; calibration; net benefit at 0.20; worst subgroup", "Silva 2012; Vickers and Elkin 2006", "300 s per cohort"],
        ["Treatment effect", "coverage ≥ 0.85; RMSE ≤ 0.10 sd; bias ≤ 0.05 sd; length ≤ 0.50 sd", "Dorie et al. 2019 (ACIC 2016)", "960 s for 48 datasets"],
        ["Report labels", "kappa ≥ 0.60 in every class; macro F1 ≥ 0.80", "Landis and Koch; McHugh 2012; F1 our convention", "45-min session"]]
code = TABLE(rows, [1.9, 4.9, 3.8, 1.7], "body_l", "body_top + 0.05", 0.48, "BLUEVIOLET_RGB", 11)
code += T("All thresholds were fixed before any agent result and not tuned afterwards. Report labels and pharyngitis triage were built and excluded: no comparator meets their gates.",
          "body_l", "body_top + 4.45", "body_w", 0.5, 12, PRI)
code += FOOT("Source: README 'Task families' table; docs/research/suite/metrics-review.md; each family document.")
slides["h1-backup/h2-clinical-thresholds-and-their-sources"] = dict(
    title="Clinical thresholds and their sources",
    code=code,
    notes=("Where each clinical bar comes from. Registration and spleen bars come from published clinical accuracy and inter-observer studies; the fetal head tolerance is the inter-observer limit between sonographers; the vessel bar is a second human expert's own agreement on each image; the ECG heart-attack operating point comes from the classic CSE study; the ICU bar is the challenge's own score against the SAPS-I baseline; the treatment-effect gate follows the published analysis of the 2016 causal inference competition. "
           "Where no published number existed, for example the 90 % family bar or the calibration bounds, we declared our own convention before any agent ran and say so."),
)

DIVIDER_NOTES = {"divider-h1-backup": "Backup slides for questions: gap verdicts, reward keys, session use, the Sonnet registration trace, trust checks, earlier runs, report labels, the causal control, the PCNSL attempt, dataset selection, cost and thresholds."}

for s in plan["slides"]:
    sid = s["slide_id"]
    if sid in slides:
        d = slides[sid]
        ast.parse(d["code"])
        s["kind"] = "freeform"
        s["params"] = {"title": d["title"], "lede": "", "section_label": "", "code": d["code"],
                       "notes": d["notes"], "_provenance": "agent"}
    elif sid in DIVIDER_NOTES:
        s["params"]["notes"] = DIVIDER_NOTES[sid]
missing = [s["slide_id"] for s in plan["slides"] if s["slide_id"] not in slides and s["kind"] != "section-divider"]
assert not missing, missing
extra = [k for k in slides if k not in {s["slide_id"] for s in plan["slides"]}]
assert not extra, extra
SIDE.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
print("wrote", SIDE, "K2 included:", bool(K2S))
