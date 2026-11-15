"""Write handcrafted freeform slides + speaker notes into CLINICAL_SUITE.md.layout.json.

Every number on a slide is read from docs/research/suite/hosted-agents2.json (hosted run 2)
or copied from the cited document (hosted-agents2.md, hosted-agents1.md, pilot1-results.md,
hosted-oracle1.md, the README families table). Run after make_figs.py and
`build.py --plan-only --shake`, then build without --shake.

Run: ~/miniconda3/envs/vals-suite/bin/python results/suite-deck/src/make_layout.py
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

DECK = Path(__file__).resolve().parents[1]
REPO = DECK.parents[1]
SIDE = DECK / "CLINICAL_SUITE.md.layout.json"
H2 = json.loads((REPO / "docs/research/suite/hosted-agents2.json").read_text())
OPUS, SONNET = "anthropic/claude-opus-5-5", "anthropic/claude-sonnet-5-5"

plan = json.loads(SIDE.read_text())
plan["theme"] = "slate"  # figures are rendered on the slate canvas (#1E293B)


def att(fam, model):
    return next(a for a in H2["attempts"] if a["family"] == fam and a["model"] == model)


def ci(d, nd=2):
    f = f"{{:+.{nd}f}}" if nd else "{:+.0f}"
    g = lambda v: f.format(v).replace("+0.00", "0.00").replace("-", "−")
    return f"{g(d['difference'])} ({g(d['low'])} to {g(d['high'])})"


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


slides = {}
SRC2 = "Source: docs/research/suite/hosted-agents2.json · hosted run 2 · suite/clinical-v1@2 (instructions v3) · one attempt per task and model"

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

# ------------------------------------------------------------------ contract + tasks
tasks5 = [
    ("REGISTRATION", "MRI → US landmarks", "< 2.0 mm per case", "120 s / case", "specialist 4/6", "TURQUOISE_RGB"),
    ("SPLEEN", "CT mask + volume", "Dice ≥ 0.94; vol ≤ 10 %", "300 s / case", "TotalSegmentator 3/6", "DEEPPINK_RGB"),
    ("FETAL HEAD", "circumference (mm)", "≤ 4.9 % error; 90 % bar", "10 s / image", "U-Net 83/83", "AMBER_RGB"),
    ("ECG", "5 calibrated classes", "MI · ECE · subgroups", "560 s / cohort", "CNN 3/3 parts", "BLUEVIOLET_RGB"),
    ("ICU RISK", "calibrated mortality", "4-part gate", "300 s / cohort", "boosted trees 4/4", "TURQUOISE_RGB"),
]
code = IMG("figures/fig_contract.png", "body_l", "body_top", "body_w", 2.75)
cw = 12.3 / 5
for i, (h, d, thr, tl, sp, c) in enumerate(tasks5):
    x = f"body_l + {i * cw + 0.04:.2f}"
    y = "body_top + 2.9"
    code += R(x, y, round(cw - 0.12, 2), 2.05, "SURFACE_RGB")
    code += R(x, y, round(cw - 0.12, 2), 0.07, c)
    code += T(h, f"{x} + 0.15", f"{y} + 0.17", round(cw - 0.35, 2), 0.32, 13, c, "MONO_FONT", True)
    code += T(d, f"{x} + 0.15", f"{y} + 0.55", round(cw - 0.35, 2), 0.3, 12, ONS)
    code += T(thr, f"{x} + 0.15", f"{y} + 0.92", round(cw - 0.35, 2), 0.3, 10.5, ONS, "MONO_FONT")
    code += T(tl, f"{x} + 0.15", f"{y} + 1.25", round(cw - 0.35, 2), 0.3, 10.5, ONS, "MONO_FONT")
    code += T(sp, f"{x} + 0.15", f"{y} + 1.6", round(cw - 0.35, 2), 0.35, 11, ONS, italic=True)
code += FOOT("Public data: RESECT, MSD Task09, HC18, PTB-XL 1.0.3, PhysioNet/CinC 2012. Thresholds and sources: README families table. Specialist = result on the hidden cases.")
slides["h2-task-contract-and-the-five-scored-tasks"] = dict(
    title="Task contract and the five scored tasks",
    code=code,
    notes=("Here is how every task works, left to right. The agent, Claude Code with web tools removed, gets a workspace with a clinical README, development cases with their reference answers, and network access only to the model API. "
           "It has 30 to 60 minutes and one attempt. What it must leave behind is not an answer but a pipeline: a run.sh that takes an input folder and writes the clinical output, offline. "
           "A separate verifier, which the agent never sees, runs that pipeline on hidden cases under a clinical time limit, scores the output in clinical units against a published threshold, and compares it with a specialist system's stored outputs on the very same cases. "
           "The five tasks below span imaging and signals: registering brain MRI to intra-operative ultrasound, a CT spleen mask with its volume, fetal head circumference from ultrasound, a five-class 12-lead ECG model with calibration and subgroup checks, and ICU mortality risk. "
           "Each card shows the clinical bar, the time limit and how the specialist did; note the specialists are not perfect either, passing 4 of 6 and 3 of 6 cases on the two small imaging tasks. "
           "Transition: here is how the two frontier models did."),
)

# ------------------------------------------------------------------ headline
o_hc, s_hc = att("measure_hc18", OPUS), att("measure_hc18", SONNET)
o_rg, o_sp = att("reg_resect", OPUS), att("seg_spleen", OPUS)
blocks = [
    ("GAP · BOTH MODELS", "Fetal head: specialist 83/83, Opus 35/83, Sonnet 64/83 within tolerance. Paired difference "
     f"Opus {ci(o_hc['gap']['pass_diff'])}, Sonnet {ci(s_hc['gap']['pass_diff'])}.", "DEEPPINK_RGB"),
    ("MATCH · OPUS 5.5", f"Registration 4/6, mean TRE {o_rg['agent_metrics']['mean_mean_tre_mm']:.2f} mm vs "
     f"{o_rg['specialist']['mean_mean_tre_mm']:.2f} mm. Spleen 3/6, Dice {o_sp['agent_metrics']['mean_dice']:.3f} vs "
     f"{o_sp['specialist']['mean_dice']:.3f}. Only 4 and 3 cases: underpowered.", "TURQUOISE_RGB"),
    ("CONTROLS", "ECG and ICU: both models meet every gate part, as the specialists do.", "AMBER_RGB"),
]
fw = 7.9
code = IMG("figures/fig_headline.png", "body_l", "body_top + 0.05", fw, "body_h - 0.45")
rx, rw = f"body_l + {fw + 0.3}", round(12.3 - fw - 0.3, 2)
bh = 1.55
for i, (k, t, c) in enumerate(blocks):
    y = f"body_top + 0.05 + {i * (bh + 0.15):.2f}"
    code += R(rx, y, rw, bh, "SURFACE_RGB") + R(rx, y, 0.08, bh, c)
    code += T(k, f"{rx} + 0.25", f"{y} + 0.12", rw - 0.4, 0.3, 12, c, "MONO_FONT", True)
    code += T(t, f"{rx} + 0.25", f"{y} + 0.45", rw - 0.4, bh - 0.5, 12, ONS)
code += FOOT(SRC2 + " · runs 1f2e6208 (Opus) / 5110a198 (Sonnet)")
slides["h2-agent-vs-specialist-hosted-run-2-same-hidden-cases"] = dict(
    title="Agent vs specialist — hosted run 2, same hidden cases",
    code=code,
    notes=("This is the headline. Each row is one task; the horizontal position is the fraction of hidden cases that met the clinical bar. Turquoise is Claude Opus 5.5, pink is Claude Sonnet 5.5, and the yellow diamond is the specialist on the same cases. The counts on the right are Opus, Sonnet, specialist. "
           "Three things to say. One: on fetal head circumference, a measurement in millimetres, both models fall clearly short of the specialist. The specialist is within tolerance on all 83 hidden images, Opus on 35 and Sonnet on 64. The paired differences and their 95 % intervals are well below zero, so this is a gap under our rule. "
           "Two: Opus matches the specialist on registration and on the spleen; on registration its mean error is actually lower, 1.61 versus 3.03 millimetres. But with only 6 hidden cases, and 4 or 3 that the specialist passes, 'no gap' here means 'not enough data to show one', not proof of parity. "
           "Three: ECG and ICU risk are controls: everybody passes every part of the gate, which shows the harness is not simply too hard. "
           "One more fact for questions: every hidden case finished within its time limit, so all lost reward is clinical, not delivery failure. "
           "Transition: let us look at the fetal head gap image by image."),
)

# ------------------------------------------------------------------ hc18
fw = 7.6
code = IMG("figures/fig_hc18.png", "body_l", "body_top + 0.05", fw, "body_h - 0.45")
rx, rw = f"body_l + {fw + 0.35}", round(12.3 - fw - 0.35, 2)
stats = [
    (ci(o_hc["gap"]["pass_diff"]).split(" ")[0], "Opus 5.5 pass rate minus specialist", "95 % CI " + ci(o_hc["gap"]["pass_diff"]).split("(")[1].rstrip(")"),
     f"mean error {o_hc['agent_metrics']['mean_abs_err_mm']:.1f} mm (median {o_hc['agent_metrics']['median_abs_err_mm']:.1f})", "TURQUOISE_RGB"),
    (ci(s_hc["gap"]["pass_diff"]).split(" ")[0], "Sonnet 5.5 pass rate minus specialist", "95 % CI " + ci(s_hc["gap"]["pass_diff"]).split("(")[1].rstrip(")"),
     f"mean error {s_hc['agent_metrics']['mean_abs_err_mm']:.1f} mm (median {s_hc['agent_metrics']['median_abs_err_mm']:.1f})", "DEEPPINK_RGB"),
]
for i, (big, lab, cil, err, c) in enumerate(stats):
    y = f"body_top + 0.1 + {i * 1.75:.2f}"
    code += T(big, rx, y, rw, 0.7, 36, c, "MONO_FONT", True)
    code += T(lab, rx, f"{y} + 0.72", rw, 0.3, 12, PRI)
    code += T(cil + "  ·  " + err, rx, f"{y} + 1.02", rw, 0.5, 11, PRI, "MONO_FONT")
code += R(rx, "body_top + 3.75", rw, 1.1, "SURFACE_RGB") + R(rx, "body_top + 3.75", 0.08, 1.1, "AMBER_RGB")
code += T(f"Specialist U-Net: 83/83 within tolerance, mean error {o_hc['specialist']['mean_abs_err_mm']:.2f} mm. "
          "Sonnet's 5 worst misses are 221–275 mm under-estimates on large heads.",
          f"{rx} + 0.25", "body_top + 3.85", rw - 0.4, 0.95, 12, ONS)
code += FOOT(SRC2 + ". Per-image limit is 4.9 % of the hidden reference, not reproduced here.")
slides["h2-fetal-head-circumference-error-per-hidden-image"] = dict(
    title="Fetal head circumference — error per hidden image",
    code=code,
    notes=("Each dot is one of the 83 hidden ultrasound images; the vertical axis is the absolute error in head circumference in millimetres, on a log scale. Filled dots are within the clinical tolerance of 4.9 % of the true circumference, which comes from inter-observer limits between sonographers; hollow dots are outside it. "
           "The specialist, a U-Net trained on separate data, is within tolerance on every image, with a mean error of about 2 millimetres. "
           "Opus 5.5 built a pixel classifier with an ellipse fit; its errors are spread widely, and only 35 of 83 pass, so its pass rate is 58 points below the specialist's, with an interval from 47 to 67 points. "
           "Sonnet 5.5 is better in the middle, median error 3.3 millimetres, but it has five catastrophic under-estimates of more than 20 centimetres on large heads, where its output fell to its own clamp. It passes 64 of 83, 23 points below the specialist. "
           "The task's own bar is 90 % of images within tolerance; neither agent reaches it. "
           "Transition: the Opus trace shows how this happened."),
)

# ------------------------------------------------------------------ timeline failure
cards = [
    ("WHAT IT KNEW", "Its own 4-fold check: \"about 60% … well below the 90% target, so expect a headline score around 0.6\".", "AMBER_RGB"),
    ("WHAT IT DID", f"Ended its turn at {o_hc['session_minutes_to_first_answer_or_end']} of 45 minutes. Nothing in the instruction tells it to stop; the session limit was stated.", "TURQUOISE_RGB"),
    ("RESULT", f"Hidden: 35/83 within tolerance (42 %), below its own estimate. Specialist: 83/83.", "DEEPPINK_RGB"),
]
code = IMG("figures/fig_timeline.png", "body_l", "body_top + 0.05", "body_w", 2.75)
cw = 12.3 / 3
for i, (k, t, c) in enumerate(cards):
    x = f"body_l + {i * cw:.2f}"
    y = "body_top + 3.0"
    code += R(x, y, round(cw - 0.18, 2), 1.9, "SURFACE_RGB") + R(x, y, round(cw - 0.18, 2), 0.07, c)
    code += T(k, f"{x} + 0.22", f"{y} + 0.2", round(cw - 0.6, 2), 0.35, 13, c, "MONO_FONT", True)
    code += T(t, f"{x} + 0.22", f"{y} + 0.62", round(cw - 0.6, 2), 1.2, 13, ONS)
code += FOOT("Source: docs/research/suite/hosted-agents2.md, 'measure_hc18 · Opus'. Run 1f2e6208-f148-4aaa-b72f-5225bed3b745. Quotes are from the trace.")
slides["h2-one-trace-opus-5-5-on-fetal-head-stops-at-11-6-of-45-minutes"] = dict(
    title="One trace — Opus 5.5 on fetal head stops at 11.6 of 45 minutes",
    code=code,
    notes=("This is one concrete failure, read from the full trace. The bar is the 45-minute session. Opus did the right first thing: within seconds it wrote a baseline pipeline that outputs a constant perimeter, so it would never ship nothing. "
           "It then built a pixel classifier and ellipse fit, and checked itself with 4-fold cross-validation. Its own words: about 60 %, well below the 90 % target, expect a score around 0.6. "
           "And then, at 11.6 minutes, it ended its turn, with more than 30 minutes left. A background job woke it once more at 19.7 minutes and it said nothing changes. "
           "The hidden result was 42 %, worse than its own estimate, against 100 % for the specialist. "
           "The point is not that the model could not measure; it is that it knew it was below the clinical bar and stopped anyway. Our instruction did state the time limit, so this is not our bug. "
           "Transition: this was not a one-off."),
)

# ------------------------------------------------------------------ session use
fw = 7.6
code = IMG("figures/fig_session.png", "body_l", "body_top + 0.05", fw, "body_h - 0.45")
rx, rw = f"body_l + {fw + 0.35}", round(12.3 - fw - 0.35, 2)
code += T("10 / 10", rx, "body_top + 0.05", rw, 0.8, 40, "AMBER_RGB", "MONO_FONT", True)
code += T("attempts ended their own turn with 48–96 % of the session unused; none hit the limit", rx, "body_top + 0.9", rw, 0.7, 13, PRI)
quotes = [("Opus · fetal head", "\"about 60% … well below the 90% target\""),
          ("Sonnet · fetal head", "\"it probably won't reach the 90% bar\""),
          ("Sonnet · registration", "\"I stopped partway through the 45 minutes.\"")]
for i, (who, q) in enumerate(quotes):
    y = f"body_top + 1.8 + {i * 0.95:.2f}"
    code += R(rx, y, rw, 0.82, "SURFACE_RGB")
    code += T(who, f"{rx} + 0.2", f"{y} + 0.07", rw - 0.3, 0.28, 11, "AMBER_RGB", "MONO_FONT", True)
    code += T(q, f"{rx} + 0.2", f"{y} + 0.36", rw - 0.3, 0.42, 12, ONS, italic=True)
code += T("Open question: whether an instruction to use the remaining time changes this is untested.",
          rx, "body_top + 4.7", rw, 0.55, 11, MUT)
code += FOOT(SRC2 + ". Session limits: task timeouts (ECG 30, spleen 60, others 45 min).")
slides["h2-session-use-when-each-agent-ended-its-turn"] = dict(
    title="Session use — when each agent ended its turn",
    code=code,
    notes=("Each bar is one of the ten attempts. The full length is the session limit for that task, and the coloured part is how far in the agent ended its own turn. "
           "Every single attempt stopped early, with between 48 and 96 % of its time unused, and none was killed by the limit. On the easy control tasks that is fine: Sonnet solved ICU risk in under two minutes. "
           "On the hard tasks it is the failure: three agents said in their own words that they were below the clinical bar or had stopped partway, and stopped anyway. "
           "Claude Code in headless mode simply ends when the model ends its turn, and nothing in our instruction says to stop. "
           "We have not tested whether telling the agent to use its remaining time would change the result; that would be a new task version, and we did not change the task after seeing results. "
           "Transition: where the agents did match the specialist."),
)

# ------------------------------------------------------------------ per case + controls
e_o, e_s = att("ecg_ptbxl", OPUS), att("ecg_ptbxl", SONNET)
i_o, i_s = att("risk_icu", OPUS), att("risk_icu", SONNET)
code = IMG("figures/fig_percase.png", "body_l", "body_top", "body_w", 3.85)
ctrl = [
    ("ECG · CONTROL", f"Gate 3/3 for both. Macro AUROC Opus {e_o['agent_metrics']['macro_auroc']:.3f}, Sonnet {e_s['agent_metrics']['macro_auroc']:.3f}, "
     f"specialist {e_o['specialist']['macro_auroc']:.3f}. MI sensitivity Opus {e_o['agent_metrics']['mi_sensitivity_at_spec']:.3f} (bar 0.70).", "BLUEVIOLET_RGB"),
    ("ICU RISK · CONTROL", f"Gate 4/4 for both. AUROC Opus {i_o['agent_metrics']['auroc']:.3f}, Sonnet {i_s['agent_metrics']['auroc']:.3f}, "
     f"specialist {i_o['specialist']['auroc']:.3f}. Calibration slope {i_o['agent_metrics']['cal_slope']:.2f} / {i_s['agent_metrics']['cal_slope']:.2f}.", "AMBER_RGB"),
]
for i, (k, t, c) in enumerate(ctrl):
    x = f"body_l + {i * 6.15:.2f}"
    y = "body_top + 3.95"
    code += R(x, y, 6.0, 1.05, "SURFACE_RGB") + R(x, y, 0.08, 1.05, c)
    code += T(k, f"{x} + 0.25", f"{y} + 0.08", 5.6, 0.3, 12, c, "MONO_FONT", True)
    code += T(t, f"{x} + 0.25", f"{y} + 0.4", 5.6, 0.6, 11.5, ONS)
code += FOOT(SRC2 + ". Cohort raw metrics from local regrade of the saved pipelines.")
slides["h2-registration-and-spleen-per-case-ecg-and-icu-controls"] = dict(
    title="Registration and spleen per case; ECG and ICU controls",
    code=code,
    notes=("Left: the six hidden registration cases. The vertical axis is target registration error, the average distance between where expert landmarks should be and where the pipeline put them; the dashed line is the 2 millimetre clinical bar. Yellow diamonds are the specialist, turquoise Opus, pink Sonnet; hollow means the case fails. "
           "Opus passes four cases, like the specialist, including one the specialist fails, and misses another by one hundredth of a millimetre. Sonnet's points sit exactly at the uncorrected error, because it shipped a pipeline that copies the landmarks unchanged; that is in the backup. "
           "Right: the six spleen CT scans, by Dice overlap. Opus trained a small U-Net from scratch on CPU in about half an hour and passes exactly the specialist's three cases. Sonnet mislocalised the organ on two scans. "
           "Bottom: ECG and ICU risk, where both models meet every part of the gate, including calibration and the worst-subgroup check, as the specialists do. These are our controls. "
           "Caveat to say out loud: with 6 hidden cases, matching the specialist is encouraging but statistically weak. "
           "Transition: the limits."),
)

# ------------------------------------------------------------------ limits + how to run
lims = [
    ("ONE ATTEMPT", "One attempt per task and model; no run-to-run variance. Fetal head moved between rounds (Opus 0.928 earlier, 0.422 here)."),
    ("SMALL HIDDEN SETS", "6 cases for registration and spleen, so their intervals are wide; no-gap results there are underpowered."),
    ("SETTINGS", "Claude Code default effort, not high. Raw values come from local regrades (match hosted rewards in 9 of 10; tenth differs by 0.0002 in quality)."),
    ("PUBLIC DATA", "Contamination risk. No recalled labels, no web use; Opus showed method-level familiarity with ICU data quirks."),
]
code = ""
for i, (k, t) in enumerate(lims):
    y = f"body_top + 0.05 + {i * 1.2:.2f}"
    code += R("body_l", y, 0.08, 1.02, "DEEPPINK_RGB")
    code += T(k, "body_l + 0.25", y, 5.5, 0.3, 12, "DEEPPINK_RGB", "MONO_FONT", True)
    code += T(t, "body_l + 0.25", f"{y} + 0.32", 5.6, 0.75, 12.5, PRI)
cx, cwid = "body_l + 6.25", 6.05
cmd = ("V=.venv-valkyrie/bin/valkyrie\n"
       "$V dataset push suite/clinical-v1 \\\n  dist/suite-tasks-v3 --tag instr2\n"
       "$V agent push agents/claude_code_noweb\n"
       "$V run start \\\n  --agent claude_code_noweb-v1.0.0 \\\n  --dataset suite/clinical-v1@2 \\\n"
       "  --model anthropic/claude-opus-5-5 \\\n  --provider modal --concurrency 3 \\\n"
       "  -s ANTHROPIC_API_KEY anthropic-api-key")
code += T("HOW TO RUN", cx, "body_top + 0.05", cwid, 0.3, 12, "TURQUOISE_RGB", "MONO_FONT", True)
code += R(cx, "body_top + 0.45", cwid, 3.0, "SURFACE_RGB")
code += T(cmd, f"{cx} + 0.25", "body_top + 0.6", cwid - 0.4, 3.6, 11.5, ONS, "MONO_FONT")
code += T("Tasks in Harbor format; verifier, specialist outputs and hidden cases stay on the verifier side. Full steps, data sources and licences: README 'How to run'.",
          cx, "body_top + 3.65", cwid, 0.6, 12, PRI)
code += FOOT("Sources: README 'Limitations' and 'How to run'; docs/research/suite/hosted-agents2.md 'Our bugs and limitations'.")
slides["h2-limits-and-how-to-run"] = dict(
    title="Limits and how to run",
    code=code,
    notes=("Be direct about the limits. Each task and model had one attempt, so we have no variance estimate, and the fetal head score for the same model moved a lot between rounds, although instructions and sandbox also changed. "
           "Registration and spleen have only six hidden cases, so 'no gap' there is underpowered. "
           "The hosted agent ran at Claude Code's default effort, not high. Valkyrie does not keep our grader's detailed metrics file, so raw millimetre and AUROC values come from regrading each saved pipeline locally; those regrades match the hosted rewards exactly in 9 of 10 attempts and within 0.0002 of quality in the tenth. "
           "All data are public, so contamination is possible; we saw no recalled labels and no web use, but Opus did know the ICU dataset's unit quirks before looking. "
           "On the right is how anyone can rerun it on Valkyrie: push the dataset, push the no-web Claude Code agent, start a run. Everything is in the README. "
           "Close with thanks."),
)

# ------------------------------------------------------------------ backups
order = ["reg_resect", "seg_spleen", "measure_hc18", "ecg_ptbxl", "risk_icu"]
short = {"reg_resect": "reg", "seg_spleen": "spleen", "measure_hc18": "fetal head", "ecg_ptbxl": "ECG", "risk_icu": "ICU"}
rows = [["Task · model", "S", "Agent in S", "Pass diff (95 % CI)", "Raw diff on S (95 % CI)", "Verdict"]]
raw_txt = {("reg_resect", OPUS): "TRE −0.20 mm (−0.55 to +0.08)", ("reg_resect", SONNET): "TRE +3.69 mm (+2.36 to +5.02)",
           ("seg_spleen", OPUS): "Dice 0.000 (−0.005 to +0.007)", ("seg_spleen", SONNET): "Dice −0.068 (−0.189 to +0.001)",
           ("measure_hc18", OPUS): "+14.1 mm (+9.8 to +18.7)", ("measure_hc18", SONNET): "+15.9 mm (+5.4 to +29.0)"}
verdict = {("reg_resect", OPUS): "no gap shown (n = 4)", ("reg_resect", SONNET): "gap shown (no-op)",
           ("seg_spleen", OPUS): "no gap", ("seg_spleen", SONNET): "no gap shown (n = 3)",
           ("measure_hc18", OPUS): "gap shown", ("measure_hc18", SONNET): "gap shown"}
for fam in order[:3]:
    for m in (OPUS, SONNET):
        g = att(fam, m)["gap"]
        pdiff = "−1.00 (degenerate)" if g["pass_diff"]["low"] == g["pass_diff"]["high"] == -1.0 else ci(g["pass_diff"])
        rows.append([f"{short[fam]} · {'Opus' if m == OPUS else 'Sonnet'}", str(g["n_S"]), str(g["agent_passes_in_S"]),
                     pdiff, raw_txt[(fam, m)], verdict[(fam, m)]])
rows.append(["ECG · both", "–", "–", "–", "gate 3/3 vs 3/3", "no gap (control)"])
rows.append(["ICU · both", "–", "–", "–", "gate 4/4 vs 4/4", "no gap (control)"])
code = TABLE(rows, [1.9, 0.6, 1.2, 2.6, 3.3, 2.7], "body_l", "body_top + 0.05", 0.5)
code += T("S = hidden cases the specialist passes. Paired bootstrap, agent minus specialist, 2,000 resamples, seed 20261114, 95 % percentile interval. "
          "Gap shown when the agent fails a case in S and the interval lies below 0. Cohort tasks: gap if the agent misses any gate part the specialist meets.",
          "body_l", "body_top + 4.7", "body_w", 0.6, 11, PRI)
code += FOOT("Source: docs/research/suite/hosted-agents2.md 'Gap verdicts'; DESIGN.md gap rule, fixed before launch.")
slides["h1-backup/h2-gap-verdicts-paired-differences-on-specialist-passed-cases"] = dict(
    title="Gap verdicts — paired differences on specialist-passed cases",
    code=code,
    notes=("The exact gap rule and every verdict. For the per-case tasks we take only the hidden cases the specialist passes, called S, and compute agent minus specialist pass rate with a paired bootstrap interval. "
           "A gap is claimed only when the agent fails at least one of those cases and the whole interval is below zero. Fetal head shows a gap for both models with intervals far from zero. "
           "Registration for Sonnet is a gap because it failed all four; the interval is degenerate at minus one. "
           "Opus registration and Sonnet spleen fail some specialist-passed cases but, with 4 and 3 cases, the interval reaches zero, so we say 'no gap shown' and call it underpowered rather than reassuring."),
)

rows = [["Task", "Model", "reward", "ran", "valid", "in time", "clin. acc.", "quality", "vs spec.", "Agent time", "API $"]]
for fam in order:
    for m in (OPUS, SONNET):
        a = att(fam, m)
        r = a["rewards"]
        rows.append([short[fam], "Opus" if m == OPUS else "Sonnet", f"{r['reward']:.3f}", f"{r['ran']:.0f}", f"{r['valid']:.0f}",
                     f"{r['within_time']:.0f}", f"{r['clinically_acceptable']:.3f}", f"{r['quality']:.3f}", f"{r['vs_specialist']:.3f}",
                     f"{a['trace']['agent_process_wall_s']:.0f} s", f"{a['trace']['cost_usd']:.3f}"])
code = TABLE(rows, [1.35, 1.0, 1.0, 0.75, 0.8, 0.95, 1.2, 1.05, 1.15, 1.45, 1.0], "body_l", "body_top + 0.05", 0.42, "AMBER_RGB", 11)
code += FOOT(SRC2 + ". Keys are hosted grades; agent time is the agent process wall time; cost is Claude Code total_cost_usd at list price.")
slides["h1-backup/h2-reward-keys-for-every-attempt-hosted-run-2"] = dict(
    title="Reward keys for every attempt — hosted run 2",
    code=code,
    notes=("All seven reward keys for all ten attempts, as graded on Valkyrie. Ran, valid and within-time are 1 everywhere, so every pipeline delivered a valid output in time and all lost reward is clinical acceptability. "
           "Reward equals the clinically acceptable fraction when the delivery keys are all 1. Quality maps the primary metric to 0 to 1, and vs-specialist is quality divided by the specialist's, capped at 1. "
           "Valkyrie's final score is the mean reward times 100: 71.77 for Opus and 58.76 for Sonnet."),
)

s_rg = att("reg_resect", SONNET)
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
code += T("FROM THE TRACE", f"{qx} + 0.25", "body_top + 0.2", qw - 0.4, 0.3, 12, "DEEPPINK_RGB", "MONO_FONT", True)
code += T("\"Conservative fallback: image-based rigid registration … was consistently WORSE than the navigation alignment, so landmarks are passed through.\"",
          f"{qx} + 0.25", "body_top + 0.6", qw - 0.45, 1.5, 13, ONS, italic=True)
code += T("\"I didn't try deformable registration … I stopped partway through the 45 minutes.\"",
          f"{qx} + 0.25", "body_top + 2.2", qw - 0.45, 1.1, 13, ONS, italic=True)
code += T(f"Ended after 7 turns and {s_rg['session_minutes_to_first_answer_or_end']} minutes. Its grid search may map world shifts to array shifts with a wrong sign (our inference, not verified).",
          qx, "body_top + 3.7", qw, 0.9, 11.5, PRI)
code += T("Mean TRE in mm per hidden case (hosted values). ✓ = under 2.0 mm and below the uncorrected error.",
          "body_l", "body_top + 3.7", 6.8, 0.6, 11, PRI)
code += FOOT("Source: docs/research/suite/hosted-agents2.md 'reg_resect · Sonnet' and per-case table. Run 5110a198-2582-414a-a9fd-81cc15103cdd.")
slides["h1-backup/h2-sonnet-5-5-on-registration-a-no-op-pipeline-after-3-minutes"] = dict(
    title="Sonnet 5.5 on registration — a no-op pipeline after 3 minutes",
    code=code,
    notes=("A second concrete failure. Sonnet tried rigid registration with several similarity measures on the four development cases, found them worse than doing nothing, and shipped a pipeline that copies the MRI landmarks unchanged. "
           "So its hidden errors equal the uncorrected column exactly, mean 6.18 millimetres, and it fails all four cases the specialist passes. It stopped after three minutes of a 45-minute session, saying itself that it had not tried deformable registration. "
           "Opus, on the same task, used modality-independent features plus a deformable step and matched the specialist. "
           "A sign or axis error in Sonnet's grid search would explain why its registrations were worse than none; that is our reading of the trace, not verified."),
)

trust = [
    ("HIDDEN CASES", "Hidden inputs, references and specialist outputs exist only in the verifier sandbox; the exporter refuses to write if any would reach the agent.", "TURQUOISE_RGB"),
    ("ORACLE CHECK", "Each task's reference solution run on Valkyrie reproduced its expected reward on all five tasks (run 15fc4349).", "AMBER_RGB"),
    ("NETWORK", "Agent network limited to api.anthropic.com (PyPI and the web unreachable); WebFetch and WebSearch removed; zero web requests in all ten traces.", "DEEPPINK_RGB"),
    ("PRESPECIFIED", "Thresholds from the literature or declared before any agent result; one attempt each, nothing rerun; gap rule fixed before launch.", "BLUEVIOLET_RGB"),
]
code = ""
for i, (k, t, c) in enumerate(trust):
    x = f"body_l + {(i % 2) * 6.2:.2f}"
    y = f"body_top + 0.1 + {(i // 2) * 2.45:.2f}"
    code += R(x, y, 6.0, 2.25, "SURFACE_RGB") + R(x, y, 6.0, 0.07, c)
    code += T(k, f"{x} + 0.3", f"{y} + 0.25", 5.4, 0.35, 15, c, "MONO_FONT", True)
    code += T(t, f"{x} + 0.3", f"{y} + 0.75", 5.4, 1.4, 14, ONS)
code += FOOT("Sources: docs/research/suite/hosted-oracle1.md, instructions-v3.md, hosted-agents2.md 'Trace findings'; DESIGN.md.")
slides["h1-backup/h2-why-the-numbers-can-be-trusted"] = dict(
    title="Why the numbers can be trusted",
    code=code,
    notes=("If asked how we know the scores are real. The hidden cases never reach the agent: the exporter checks this and refuses to write a task that would leak them. "
           "Before any agent ran, the reference solution of every task was run on Valkyrie and reproduced its locally measured reward, so image, artifact carry and verifier work. "
           "The agent could only reach the Anthropic API, we confirmed PyPI and the open web were unreachable, we removed Claude Code's web tools, and none of the ten traces made a web request. "
           "Thresholds were fixed before seeing results and nothing was rerun for a better number."),
)

code = ""
panels = [
    ("HOSTED RUN 1 · instructions v2 · suite/clinical-v1@1",
     "Session limit not stated. The limit killed 5 of 10 attempts (registration and spleen for both models, fetal head for Opus), classed not interpretable under the rule fixed before results. "
     "ECG and ICU were controls. Only interpretable gap: Sonnet fetal head 72/83, pass diff −0.133 (−0.205 to −0.060). Runs 0ae696de / 1a4037a0.", "AMBER_RGB"),
    ("LOCAL PILOT 1 · instructions v1 · bubblewrap, effort high",
     "Fetal head: Opus 0.928, Sonnet 0.819, both gaps shown. Registration: both 0, a delivery failure at the deadline (Opus wrote run.sh 2.5 minutes before the end and never ran it), not an accuracy gap.", "BLUEVIOLET_RGB"),
    ("THE FIX · instructions v3 · suite/clinical-v1@2",
     "One added section states the session limit and that the pipeline is graded as found. In hosted run 2 no attempt reached the limit and 8 of 10 had a working run.sh within 3 minutes.", "TURQUOISE_RGB"),
]
for i, (k, t, c) in enumerate(panels):
    y = f"body_top + 0.05 + {i * 1.75:.2f}"
    code += R("body_l", y, "body_w", 1.6, "SURFACE_RGB") + R("body_l", y, 0.08, 1.6, c)
    code += T(k, "body_l + 0.3", f"{y} + 0.15", 11.6, 0.3, 13, c, "MONO_FONT", True)
    code += T(t, "body_l + 0.3", f"{y} + 0.55", 11.7, 1.0, 13, ONS)
code += FOOT("Sources: docs/research/suite/hosted-agents1.md, pilot1-results.md, instructions-v3.md, hosted-agents2.md. Rounds are never pooled.")
slides["h1-backup/h2-earlier-runs-the-session-limit-bug-and-its-fix"] = dict(
    title="Earlier runs — the session-limit bug and its fix",
    code=code,
    notes=("Our own bug, stated plainly. The first two rounds did not tell the agent how long its session was, or that whatever pipeline existed at the end would be graded. Agents planned work that could not fit and were killed mid-task, so we classed those attempts as not interpretable rather than as model failures. "
           "Instructions v3 added one section fixing this, published as dataset version 2, and hosted run 2 is the headline. "
           "The earlier rounds are still informative: Sonnet's fetal head gap appeared in every round, while Opus scored 0.928 in two earlier rounds and 0.422 here, which is why we stress one attempt is one draw."),
)

rows = [["What", "Run id", "Dataset"],
        ["Agents, hosted run 2, Opus 5.5", H2["runs"]["opus"]["run_id"], "suite/clinical-v1@2"],
        ["Agents, hosted run 2, Sonnet 5.5", H2["runs"]["sonnet"]["run_id"], "suite/clinical-v1@2"],
        ["Oracle, instructions v3", "15fc4349-028e-42dc-982f-feccff226b7c", "suite/clinical-v1@2"],
        ["Agents, hosted run 1, Opus 5.5", "0ae696de-4237-44bf-be49-25b90940772b", "suite/clinical-v1@1"],
        ["Agents, hosted run 1, Sonnet 5.5", "1a4037a0-e1a9-4670-aee0-ceda221c6264", "suite/clinical-v1@1"]]
code = TABLE(rows, [3.6, 5.2, 3.5], "body_l", "body_top + 0.05", 0.48, "TURQUOISE_RGB", 12)
cost = H2["api_cost_usd"]
stats = [(f"${cost['total']:.2f}", "API, hosted run 2 (10 attempts)"),
         (f"${cost['by_model'][OPUS]:.2f}", "Opus 5.5"),
         (f"${cost['by_model'][SONNET]:.2f}", "Sonnet 5.5"),
         ("n/a", "Modal: not reported by Valkyrie (about 2.5 h sandbox time)")]
for i, (v, lab) in enumerate(stats):
    x = f"body_l + {i * 3.1:.2f}"
    code += T(v, x, "body_top + 3.35", 2.9, 0.7, 30, "AMBER_RGB", "MONO_FONT", True)
    code += T(lab, x, "body_top + 4.1", 2.9, 0.6, 12, PRI)
code += FOOT("Sources: docs/research/suite/hosted-agents2.md 'Cost'; README 'Run identifiers'. API cost is Claude Code total_cost_usd at list price.")
slides["h1-backup/h2-cost-and-run-identifiers"] = dict(
    title="Cost and run identifiers",
    code=code,
    notes=("Run identifiers for anyone who wants to inspect the traces on Valkyrie; the headline runs are the first two rows. "
           "The whole headline round cost 3.77 dollars in API usage at list price, 2.75 for Opus and 1.02 for Sonnet, partly because every agent stopped early. "
           "Valkyrie does not report Modal sandbox cost; the ten tasks used about two and a half hours of sandbox time."),
)

rows = [["Task", "Clinical threshold", "Source", "Time limit"],
        ["Registration", "mean TRE < 2.0 mm and below initial error", "Gerard et al. 2021; AAPM TG-132", "120 s per case"],
        ["Spleen", "Dice ≥ 0.94 and volume error ≤ 10 %", "Humpire-Mamani 2020; 10 % our convention", "300 s per case"],
        ["Fetal head", "error ≤ 4.9 % of reference; bar ≥ 90 % of images", "Sarris et al. 2012; bar our convention", "10 s per image"],
        ["ECG", "MI sens. ≥ 0.70 at spec. 0.90; ECE ≤ 0.05; subgroup gap ≤ 0.05", "Willems 1991; others our convention", "560 s per cohort"],
        ["ICU risk", "event-1 ≥ SAPS-I + 0.05; calibration; net benefit at 0.20; worst subgroup", "Silva 2012; Vickers and Elkin 2006", "300 s per cohort"]]
code = TABLE(rows, [1.7, 5.0, 3.9, 1.7], "body_l", "body_top + 0.05", 0.62, "BLUEVIOLET_RGB", 11.5)
code += T("All thresholds were fixed before any agent result and not tuned afterwards. Pharyngitis triage was built and excluded: no comparator meets its gate, and its labels are physician votes.",
          "body_l", "body_top + 4.0", "body_w", 0.7, 12, PRI)
code += FOOT("Source: README 'Task families' table; docs/research/suite/metrics-review.md; each family document.")
slides["h1-backup/h2-clinical-thresholds-and-their-sources"] = dict(
    title="Clinical thresholds and their sources",
    code=code,
    notes=("Where each clinical bar comes from. Registration and spleen bars come from published clinical accuracy and inter-observer studies; the fetal head tolerance is the inter-observer limit between sonographers; the ECG myocardial infarction operating point comes from the classic CSE study; the ICU bar is the challenge's own score against the SAPS-I baseline. "
           "Where no published number existed, for example the 90 % family bar or the calibration bounds, we declared our own convention before any agent ran and say so."),
)

DIVIDER_NOTES = {"divider-h1-backup": "Backup slides for questions: gap verdicts, all reward keys, the Sonnet registration trace, trust checks, earlier runs, cost and thresholds."}

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
SIDE.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
print("wrote", SIDE)
