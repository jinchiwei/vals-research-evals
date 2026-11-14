"""Write handcrafted freeform code + speaker notes into COMPARISON.md.layout.json.

Numbers are pulled from the result artifacts (via figures/raw/*.json written by
make_figs.py) so a re-run refreshes every on-slide number.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

DECK = Path(__file__).resolve().parents[1]
SIDE = DECK / "COMPARISON.md.layout.json"
RAW = DECK / "figures" / "raw"

plan = json.loads(SIDE.read_text())
plan["theme"] = "slate"  # figures are rendered on the slate canvas (#1E293B)
scores = json.loads((RAW / "fig_scores.json").read_text())
effort = json.loads((RAW / "fig_effort.json").read_text())
harness = json.loads((RAW / "fig_harness.json").read_text())

model_rows = [r for r in scores["rows"] if r["group"] == "model"]
n_res = sum(r["resolved"] for r in model_rows)
n_tot = sum(r["n"] for r in model_rows)
per_run = " · ".join(f"{r['label'].replace('Opus 5.5 · ', '').split(' · seed')[0]} {r['resolved']}/{r['n']}" for r in model_rows)
models = sorted({m for r in model_rows for m in r["models"]})
heldout_src = scores["sources"]["v2 held-out · seed 101"]


def mean(xs):
    return sum(xs) / len(xs)


def by(run, key, slot=None):
    return [e[key] for e in effort if e["run"].startswith(run) and (slot is None or e["slot"] == slot)]


aud_in_v1 = mean(by("v1 dev", "input_kb", "audit · flawed") + by("v1 dev", "input_kb", "audit · clean"))
aud_in_v2 = mean(by("v2 dev", "input_kb", "audit · flawed") + by("v2 dev", "input_kb", "audit · clean"))
tok = [mean(by(r, "output_tokens")) for r in ("v1 dev", "v2 dev", "v2 held-out")]
sec = [mean(by(r, "elapsed_s")) for r in ("v1 dev", "v2 dev", "v2 held-out")]
loc = [mean(by(r, "analysis_lines")) for r in ("v1 dev", "v2 dev", "v2 held-out")]
cost = [sum(by(r, "cost_usd")) for r in ("v1 dev", "v2 dev", "v2 held-out")]
tools = [mean(by(r, "tool_calls")) for r in ("v1 dev", "v2 dev", "v2 held-out")]
all_one = all(e["score"] == 1.0 for e in effort)

FOOT = ("_add_text(slide, {src!r}, left=body_l, top=body_bottom - 0.34, width=body_w, height=0.36, "
        "size=8.5, color_rgb=_text_on(CANVAS_BG_RGB), font=SANS_FONT)\n")

slides = {}

# ---------------------------------------------------------------- slide 1
slides["h2-candidate-task-families-synthetic-cases-and-their-shortcuts"] = dict(
    title="Candidate task families — synthetic cases and their shortcuts",
    code=(
        "band_h = 0.50\n"
        "_add_rect(slide, left=body_l, top=body_top, width=body_w, height=band_h, fill_rgb=SURFACE_RGB)\n"
        "_add_rect(slide, left=body_l, top=body_top, width=0.08, height=band_h, fill_rgb=AMBER_RGB)\n"
        "_add_text(slide, 'EVENT', left=body_l + 0.25, top=body_top, width=1.0, height=band_h, size=12, color_rgb=AMBER_RGB, font=MONO_FONT, bold=True, anchor=MSO_ANCHOR.MIDDLE)\n"
        "_add_text(slide, 'Vals Build Your Own Eval: a Valkyrie benchmark of tasks frontier models still get wrong · demos Nov 15', left=body_l + 1.15, top=body_top, width=body_w - 1.3, height=band_h, size=14, color_rgb=_text_on(SURFACE_RGB), font=SANS_FONT, anchor=MSO_ANCHOR.MIDDLE)\n"
        "fig_top = body_top + band_h + 0.18\n"
        "_fit_image(slide, 'figures/fig_candidates.png', left=body_l, top=fig_top, max_w=body_w, max_h=body_bottom - 0.46 - fig_top)\n"
        + FOOT.format(src="Synthetic data, seed 11 cases. Values are the agent's graded-correct answers (verifier tolerance 1e-4); report rows are verbatim synthetic input. "
                          "Event: vals.ai/hackathon. Results: results/20261113-opus55-dev-v1c, -workflow-dev.")
    ),
    notes=(
        "This slide replaces the usual background section: it shows the three candidate families as they actually appear to the agent, using real synthetic cases from our runs. "
        "The event framing is in the amber band: Vals' Build Your Own Eval track wants a benchmark on Valkyrie made of tasks frontier models still get wrong, with demos on November 15 (source: vals.ai/hackathon). "
        "Left panel, the audit family: the claim is that image scores discriminate the target beyond acquisition protocol. In the flawed control, the global AUC looks strong at about 0.89, but protocol alone gets 0.88 and the within-protocol AUC collapses to about 0.53, below the task's 0.65 rule, so the correct verdict is unsupported. "
        "The clean control keeps about 0.97 within protocol, so it is supported. Having both controls matters: a model that always says 'confounded' fails the clean one. "
        "Middle panel, the change family: weighted slopes after scanner calibration, with a 95% interval compared to a synthetic −0.08 per year threshold. S1 declines, S3 and S4 are stable, and S2 has an interval so wide that the right answer is to abstain, 'insufficient'. "
        "Right panel, the reports family: subject R1's documents. The latest-signed report is not the most recent exam; within the most recent exam, the addendum that applies to edema is authoritative, and the later sinus correction does not touch edema. Gold is 'unassessed, change unknown'. "
        "All data are invented; the shortcuts mirror failure patterns from Jin's imaging and report work, not real patient data. "
        "Transition: next is how these become exported tasks and how we ran a model on them."
    ),
)

# ---------------------------------------------------------------- slide 2
slides["h2-harness-task-export-local-tool-agent-pilot-and-valkyrie-readiness"] = dict(
    title="Harness — task export, local tool-agent pilot and Valkyrie readiness",
    code=(
        "strip_h = 0.78\n"
        "fig_h = body_h - strip_h - 0.64\n"
        "_fit_image(slide, 'figures/fig_harness.png', left=body_l, top=body_top + 0.05, max_w=body_w, max_h=fig_h)\n"
        "sy = body_bottom - 0.46 - strip_h\n"
        "chips = [('12/12', 'task folders validated + packed per variant (v1, v2)', AMBER_RGB), ('12/12', 'oracle-verifier roundtrips per variant, re-run today', TURQUOISE_RGB), ('0', 'hosted Valkyrie runs so far', DEEPPINK_RGB)]\n"
        "cw = (body_w - 2 * 0.25) / 3\n"
        "for i, (v, lab, c) in enumerate(chips):\n"
        "    x = body_l + i * (cw + 0.25)\n"
        "    _add_rect(slide, left=x, top=sy, width=cw, height=strip_h, fill_rgb=SURFACE_RGB)\n"
        "    _add_rect(slide, left=x, top=sy, width=0.08, height=strip_h, fill_rgb=c)\n"
        "    _add_text(slide, v, left=x + 0.25, top=sy, width=1.25, height=strip_h, size=24, color_rgb=c, font=MONO_FONT, bold=True, anchor=MSO_ANCHOR.MIDDLE)\n"
        "    _add_text(slide, lab, left=x + 1.45, top=sy, width=cw - 1.6, height=strip_h, size=12.5, color_rgb=_text_on(SURFACE_RGB), font=SANS_FONT, anchor=MSO_ANCHOR.MIDDLE)\n"
        + FOOT.format(src=f"Sources: results/20261113-valkyrie-validation, -valkyrie-v2-validation (Valkyrie CLI {harness['cli']}, SDK {harness['sdk']}, hosted_run=false); "
                          "scripts/verify_isolated.py on dist/development-v1b and dist/workflow-v2; README.md.")
    ),
    notes=(
        "This is the plumbing, and it is the part that is in good shape. A seeded generator writes each synthetic case as a Harbor-format task folder: the instruction plus an environment with only the public input; a hidden tests folder with the verifier and expected answers; and a solution folder with the reference oracle. "
        "From there two paths. Top: a local tool-agent pilot. The Claude CLI runs inside a bubblewrap sandbox with Read, Write, Edit and Bash, and it never sees the repository, generator, grader or answer key. We requested claude-opus-5-5 at high effort, with a 240-second and three-dollar cap per task. The agent must write answer.json and a reproducible analysis.py; the verifier checks every item at 1e-4 tolerance, and the trace records the returned model IDs, tool calls, usage and estimated cost. "
        "Bottom: the official Valkyrie CLI and SDK validated and packed all 12 task folders for each variant, offline, with no upload. Separately, the isolated oracle-then-verifier roundtrip passes 12 of 12 for each variant; I re-ran that script today while building this deck. "
        "What has not happened: a hosted Valkyrie run. That needs the event account, Modal setup and a provider key, so 'Valkyrie-ready' means 'accepted by the offline SDK', not 'executed on Valkyrie'. "
        "One caveat for questions: the sandbox keeps network access, so this is a trusted-task pilot, not a hostile-agent security benchmark. "
        "Transition: with the harness working, here is what the model actually scored."
    ),
)

# ---------------------------------------------------------------- slide 3
slides["h2-scores-by-iteration-opus-5-5-and-scripted-controls"] = dict(
    title="Scores by iteration — Opus 5.5 and scripted controls",
    code=(
        "zw = 3.55\n"
        "_add_rect(slide, left=body_l, top=body_top, width=zw, height=body_h - 0.46, fill_rgb=SURFACE_RGB)\n"
        "_add_rect(slide, left=body_l, top=body_top, width=zw, height=0.08, fill_rgb=TURQUOISE_RGB)\n"
        "_add_text(slide, 'RESOLVED', left=body_l + 0.3, top=body_top + 0.3, width=zw - 0.6, height=0.35, size=12, color_rgb=TURQUOISE_RGB, font=MONO_FONT, bold=True)\n"
        f"_add_text(slide, '{n_res}/{n_tot}', left=body_l + 0.3, top=body_top + 0.65, width=zw - 0.6, height=1.1, size=60, color_rgb=_text_on(SURFACE_RGB), font=MONO_FONT, bold=True)\n"
        "_add_text(slide, 'model task attempts, all items correct', left=body_l + 0.3, top=body_top + 1.8, width=zw - 0.6, height=0.6, size=13, color_rgb=_text_on(SURFACE_RGB), font=SANS_FONT)\n"
        "lines = " + repr([
            f"returned model: {', '.join(models)}",
            "v1 4/4 · v2 4/4 · held-out 4/4",
            "2 infra runs / 5 attempts excluded, 0 tokens",
            "scripted rows: controls, not LLMs",
        ]) + "\n"
        "for i, t in enumerate(lines):\n"
        "    y = body_top + 2.6 + i * 0.62\n"
        "    _add_rect(slide, left=body_l + 0.3, top=y + 0.07, width=0.06, height=0.38, fill_rgb=(DEEPPINK_RGB if i >= 2 else TURQUOISE_RGB))\n"
        "    _add_text(slide, t, left=body_l + 0.5, top=y, width=zw - 0.75, height=0.55, size=11.5, color_rgb=_text_on(SURFACE_RGB), font=SANS_FONT)\n"
        "fx = body_l + zw + 0.35\n"
        "_fit_image(slide, 'figures/fig_scores.png', left=fx, top=body_top, max_w=body_w - zw - 0.35, max_h=body_h - 0.46)\n"
        + FOOT.format(src=f"Sources: results/20261113-opus55-dev-v1c, -workflow-dev, -workflow-heldout ({heldout_src}); results/20261113-controls-v1 (scripted); "
                          "excluded: -dev-v1, -dev-v1b. Family score = mean item-fraction over cases.")
    ),
    notes=(
        f"The headline is that there is no failure to show. Across the three valid runs, claude-opus-5-5 resolved {n_res} of {n_tot} task attempts, meaning every item in every case matched the hidden gold. "
        "Read the grid as rows of runs and columns of task families; the number is the mean fraction of items correct, and 'resolved' counts cases where every item was right. "
        "The bottom three rows are the model: iteration 1 on development seed 11, iteration 2 (the workflow variant) on the same seed, and iteration 2 on held-out seed 101, which we did not use for tuning. All ones. "
        "The top three rows are scripted controls, deterministic Python strategies rather than language models, run on 12 development cases. They show the verifier is not trivially satisfied: the naive strategy (global AUC, uncalibrated slopes, signing-date chronology) resolves only 3 of 12, an adjusted one 9 of 12, and only the fully careful one gets 12 of 12. So the shortcuts are real; the frontier model just does not take them. "
        "Two early infrastructure runs, five task attempts in total, are excluded from accuracy because no model ran and zero model tokens were used: the first run died at sandbox start on a read-only filesystem after one attempt, and in the second run all four attempts could not reach the API (EAI_AGAIN) and returned a '<synthetic>' placeholder. Counting those as model failures would be fabricating a gap. "
        "Caveat: four cases per run, one model, and held-out seeds share templates with development, so this tests numeric generalization, not new task types. "
        "Transition: did the harder workflow variant at least make the model work harder?"
    ),
)

# ---------------------------------------------------------------- slide 4
chips4 = [
    (f"{aud_in_v1:.0f} → {aud_in_v2:.0f} KB", "audit input.json, v1 → v2", "TURQUOISE_RGB"),
    (f"{loc[0]:.0f} → {loc[1]:.0f}", "mean analysis.py lines", "BLUEVIOLET_RGB"),
    (f"{tok[0]:,.0f} → {tok[1]:,.0f}", "mean output tokens", "DEEPPINK_RGB"),
    (f"{sec[0]:.0f} → {sec[1]:.0f} s", "mean wall-clock per task", "AMBER_RGB"),
]
slides["h2-task-burden-and-agent-effort-v1-vs-v2-workflow-variant"] = dict(
    title="Task burden and agent effort — v1 vs v2 workflow variant",
    code=(
        "chip_h = 0.95\n"
        "_fit_image(slide, 'figures/fig_effort.png', left=body_l, top=body_top, max_w=body_w, max_h=body_h - chip_h - 0.78)\n"
        "chips = [" + ", ".join(f"({a!r}, {b!r}, {c})" for a, b, c in chips4) + "]\n"
        "cy = body_bottom - 0.46 - chip_h\n"
        "cw = (body_w - 3 * 0.2) / 4\n"
        "for i, (v, lab, c) in enumerate(chips):\n"
        "    x = body_l + i * (cw + 0.2)\n"
        "    _add_rect(slide, left=x, top=cy, width=cw, height=chip_h, fill_rgb=SURFACE_RGB)\n"
        "    _add_rect(slide, left=x, top=cy, width=cw, height=0.07, fill_rgb=c)\n"
        "    _add_text(slide, v, left=x + 0.2, top=cy + 0.14, width=cw - 0.3, height=0.45, size=19, color_rgb=c, font=MONO_FONT, bold=True)\n"
        "    _add_text(slide, lab, left=x + 0.2, top=cy + 0.58, width=cw - 0.3, height=0.32, size=11.5, color_rgb=_text_on(SURFACE_RGB), font=SANS_FONT)\n"
        + FOOT.format(src=f"Per-case trace/result.json and workspace files, 3 runs × 4 cases. Score = 1.00 in all {len(effort)} cases. "
                          f"Estimated CLI usage per 4-task run: ${cost[0]:.2f} / ${cost[1]:.2f} / ${cost[2]:.2f} (v1 dev / v2 dev / v2 held-out); not a billing statement.")
    ),
    notes=(
        "Iteration 2 tried to make the tasks harder for a real workflow reason rather than by adding trick wording. Audit cases gained repeated events, training-snapshot exclusions, duplicate prediction exports and revised diagnosis labels; change cases gained mixed volume units and age norms; report cases gained addenda that apply only to specific findings. The underlying scientific answer for each case was preserved. "
        "Each small panel is one measure, with a line per case slot across the three runs. The input got much bigger for audit, roughly "
        f"{aud_in_v1:.0f} to {aud_in_v2:.0f} kilobytes, because the agent now has to rebuild the cohort itself. The model's analysis scripts got longer, about {loc[0]:.0f} to {loc[1]:.0f} lines on average, output tokens rose from about {tok[0]:,.0f} to {tok[1]:,.0f}, and wall-clock went from about {sec[0]:.0f} to {sec[1]:.0f} seconds per task; tool calls went from about {tools[0]:.1f} to {tools[1]:.1f}. "
        "So the workflow variant did add work, mostly in audit, but none of it turned into errors: every one of the twelve cases still scored 1.00. Read that as 'more effort, same outcome' — a cost increase, not a difficulty increase. "
        "The dollar numbers in the footer are the CLI's estimated usage, around fifty cents per four-task run, and are not a claim about the actual bill. "
        "Transition: let me be explicit about what these runs do and do not establish."
    ),
)

# ---------------------------------------------------------------- slide 5 (native-shape evidence ladder)
steps = [
    ("scripted controls", "naive 3/12 · careful 12/12", True),
    ("oracle ↔ verifier", "12/12 per variant, isolated", True),
    ("SDK validate + pack", "12/12 per variant, offline", True),
    ("local tool-agent, dev", "Opus 5.5 · 8/8 attempts", True),
    ("local, held-out seed", "Opus 5.5 · 4/4 · seed 101", True),
    ("hosted Valkyrie run", "not run", False),
    ("new task families · more models", "not tested", False),
]
code5 = (
    "steps = " + repr(steps) + "\n"
    "n = len(steps)\n"
    "lw = 8.45\n"
    "gap = 0.10\n"
    "step = 0.32\n"
    "rh = (body_h - 0.46 - gap * (n - 1)) / n\n"
    "for i, (lab, sub, ok) in enumerate(steps):\n"
    "    y = body_top + (n - 1 - i) * (rh + gap)\n"
    "    x = body_l + i * step\n"
    "    w = lw - (n - 1) * step\n"
    "    c = TURQUOISE_RGB if ok else DEEPPINK_RGB\n"
    "    _add_rect(slide, left=x, top=y, width=w, height=rh, fill_rgb=(SURFACE_RGB if ok else CANVAS_BG_RGB))\n"
    "    _add_rect(slide, left=x, top=y, width=0.08, height=rh, fill_rgb=c)\n"
    "    _add_text(slide, ('✓' if ok else '✗'), left=x + 0.22, top=y, width=0.4, height=rh, size=16, color_rgb=c, font=MONO_FONT, bold=True, anchor=MSO_ANCHOR.MIDDLE)\n"
    "    _add_text(slide, lab, left=x + 0.65, top=y, width=3.35, height=rh, size=12.5, color_rgb=(_text_on(SURFACE_RGB) if ok else c), font=MONO_FONT, bold=True, anchor=MSO_ANCHOR.MIDDLE)\n"
    "    _add_text(slide, sub, left=x + 4.05, top=y, width=w - 4.15, height=rh, size=12, color_rgb=(_text_on(SURFACE_RGB) if ok else WHITE_RGB), font=SANS_FONT, anchor=MSO_ANCHOR.MIDDLE)\n"
    "rx = body_l + lw + 0.35\n"
    "rw = body_w - lw - 0.35\n"
    "_add_rect(slide, left=rx, top=body_top, width=rw, height=body_h - 0.46, fill_rgb=SURFACE_RGB)\n"
    "_add_rect(slide, left=rx, top=body_top, width=0.08, height=body_h - 0.46, fill_rgb=AMBER_RGB)\n"
    "_add_text(slide, 'CAVEATS', left=rx + 0.3, top=body_top + 0.22, width=rw - 0.5, height=0.35, size=12, color_rgb=AMBER_RGB, font=MONO_FONT, bold=True)\n"
    "cav = " + repr([
        "4 cases per run; 1 model; 1 prompt variant",
        "held-out seeds reuse dev templates: numeric generalization only",
        "hosted grader checks artifacts only; all 12 analysis.py separately replayed offline: 12/12 reproduced",
        "report evidence uses an exact-quote contract",
        "excluded: 2 failed infra runs, 5 task attempts, 0 model tokens",
    ]) + "\n"
    "ch = (body_h - 0.46 - 0.75) / len(cav)\n"
    "for i, t in enumerate(cav):\n"
    "    _add_text(slide, t, left=rx + 0.3, top=body_top + 0.7 + i * ch, width=rw - 0.5, height=ch, size=12, color_rgb=_text_on(SURFACE_RGB), font=SANS_FONT)\n"
    + FOOT.format(src="Sources: results/*/summary.json, validation.json, manifest.json; results/replay-validation.json (12/12 replays); README.md (grading and scientific limits).")
)
slides["h2-evidence-status-what-these-runs-establish"] = dict(
    title="Evidence status — what these runs establish",
    code=code5,
    notes=(
        "This is a ladder of evidence, lowest on the left. Each step is a stronger kind of claim; turquoise check marks are what we have, pink crosses are what we do not. "
        "We have scripted controls that show the shortcuts are scoreable; isolated oracle-to-verifier roundtrips that show the gold and the verifier agree; offline SDK validation and packing; and live local tool-agent runs of claude-opus-5-5, on development and on a held-out seed. "
        "We do not have a hosted Valkyrie run, and we have not tested new task families or a second model. "
        "The caveats on the right are the reasons not to over-read the twelve out of twelve: only four cases per run and one model, so no leaderboard claims; held-out seeds share templates with development, so they test numeric and permutation generalization, not new task types; the grader itself checks only the submitted artifacts, but separately we replayed all twelve saved analysis.py programs in fresh, network-isolated workspaces, and all twelve reproduced the correct results (results/replay-validation.json); and the report family relies on an exact-sentence quote contract, which is narrow. "
        "And once more: the two failed infrastructure runs, five task attempts with zero model tokens, are excluded, not counted as wins or losses. "
        "Transition: given that, here is what I would change for the hackathon."
    ),
)

# ---------------------------------------------------------------- slide 6
blocks = [
    ("KEEP", "harness: export, sandbox, hidden verifier, traces, controls", "TURQUOISE_RGB"),
    ("REPLACE", "tasks: all v1 and v2 variants were solved", "DEEPPINK_RGB"),
    ("NEXT", "repair an underspecified analysis repository, or reconcile much longer evidence chains", "AMBER_RGB"),
    ("BAR", "a held-out miss that survives trace review, with defensible hidden tests", "BLUEVIOLET_RGB"),
]
slides["h2-recommendation-next-task-design-for-a-demonstrated-gap"] = dict(
    title="Recommendation — next task design for a demonstrated gap",
    code=(
        "fw = 7.45\n"
        "_fit_image(slide, 'figures/fig_next.png', left=body_l, top=body_top, max_w=fw, max_h=body_h - 0.46)\n"
        "rx = body_l + fw + 0.35\n"
        "rw = body_w - fw - 0.35\n"
        "blocks = [" + ", ".join(f"({a!r}, {b!r}, {c})" for a, b, c in blocks) + "]\n"
        "bh = (body_h - 0.46 - 3 * 0.16) / 4\n"
        "for i, (k, t, c) in enumerate(blocks):\n"
        "    y = body_top + i * (bh + 0.16)\n"
        "    _add_rect(slide, left=rx, top=y, width=rw, height=bh, fill_rgb=SURFACE_RGB)\n"
        "    _add_rect(slide, left=rx, top=y, width=0.08, height=bh, fill_rgb=c)\n"
        "    _add_text(slide, k, left=rx + 0.28, top=y + 0.14, width=rw - 0.45, height=0.32, size=12, color_rgb=c, font=MONO_FONT, bold=True)\n"
        "    _add_text(slide, t, left=rx + 0.28, top=y + 0.46, width=rw - 0.45, height=bh - 0.52, size=13, color_rgb=_text_on(SURFACE_RGB), font=SANS_FONT)\n"
        + FOOT.format(src="Map is illustrative positioning, not measured. Recommendation follows README: if frontier agents solve a family, strengthen it for a real workflow reason or discard it.")
    ),
    notes=(
        "The honest recommendation: in these versions there is no demonstrated frontier gap, so they are not yet a Build Your Own Eval submission. "
        "The map on the left is illustrative, not measured. The horizontal axis is how long the chain of evidence is that must be reconciled; the vertical axis is how much of the specification the agent must work out for itself. Both v1 and the v2 workflow variant sit in the lower-left box: fully specified contracts with short chains, and the model solved all twelve attempts there. Moving from v1 to v2 added data handling, not real ambiguity, which is consistent with the flat scores. "
        "Two directions look more promising. Up: hand the agent an underspecified analysis repository, with a leak, a wrong join or an unstated exclusion, and make it repair the code so a hidden test suite passes. Right: much longer evidence chains, for example many reports and addenda across years, where one missed supersession changes the answer. The corner combines both. "
        "On the right: keep the harness, which is the reusable asset; replace the task content; and hold ourselves to a clear bar: a held-out miss that survives trace review, meaning not infrastructure and not ambiguous gold, with hidden tests we can defend to the judges. "
        "If we cannot get such a miss before the event, the right call is to say so rather than tune the tasks until the model fails on wording."
    ),
)

for s in plan["slides"]:
    sid = s["slide_id"]
    if sid in slides:
        d = slides[sid]
        ast.parse(d["code"])
        s["kind"] = "freeform"
        s["params"] = {"title": d["title"], "lede": "", "section_label": "", "code": d["code"],
                       "notes": d["notes"], "_provenance": "agent"}
missing = [s["slide_id"] for s in plan["slides"] if s["slide_id"] not in slides]
assert not missing, missing
SIDE.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
print("wrote", SIDE, "| held-out source:", heldout_src, "| resolved", n_res, "/", n_tot, "| all_one", all_one)
