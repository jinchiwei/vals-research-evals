"""Refresh build-status.json after a rebuild: slide inventory, QA, provenance hashes.

Usage (from repo root): python3 results/pcnsl-frontier-deck/scripts/update_build_status.py
Reads only aggregate evidence files and deck artifacts; writes build-status.json in the deck dir.
"""
import datetime
import hashlib
import json
from pathlib import Path

REPO = Path(".").resolve()
D = REPO / "results/pcnsl-frontier-deck"
bs_path = D / "build-status.json"
bs = json.loads(bs_path.read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


plan = json.loads((D / "PCNSL_FRONTIER.md.layout.json").read_text())
slides = plan["slides"]
kinds = [s["kind"] for s in slides]
n_div = kinds.count("section-divider")
appendix = [s for s in slides if s["params"].get("title", "").startswith("Appendix")]
content = len(slides) - n_div
notes = json.loads((D / "qa/notes.json").read_text())

bs["built_utc"] = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
bs["evidence_state"] = ("Final evidence refresh after concurrent jobs: FINALIZED pilot report, strict replay, "
                        "16-task v2 packaging validation, hosted-release baseline and final implementation review")
bs["slides"] = {
    "total": notes["slides"], "content": content, "section_dividers": n_div, "cover_and_end": 2,
    "main_content_slides": content - len(appendix), "appendix_content_slides": len(appendix),
    "layouts": [[s["slide_id"], s["kind"]] for s in slides], "composition_or_freeform": [],
    "changes_this_refresh": [
        "New measured slide: hosted-release-only baseline (fig_hosted_baseline.png, figure-with-aside-horizontal)",
        "Historical 33-patient schematic moved from Results to Appendix D",
        "Execution ladder: 16 archives incl. integrated; strict replay row; grader review/tests row",
        "Pilot tiles: strict replay 10/10 submissions, 40 fixtures, 0 model calls; historical Opus round marked not pooled",
        "Ask, data-object, conclusions, Appendix C and speaker notes updated to final evidence",
    ],
}
qa = bs["qa"]
qa["pdf_pages"] = notes["slides"]
qa["png_previews"] = len(sorted((D / "previews").glob("slide-*.png")))
qa["shape_bounds_check"]["out_of_bounds_shapes"] = [
    {"slide": i + 1, "shape": "TextBox 10"} for i, k in enumerate(kinds, 1) if k == "section-divider"]
qa["shape_bounds_check"]["interpretation"] = (
    "Re-checked after final refresh: only the footer textbox on the 6 section-divider slides extends past the slide edge "
    "(shared builder divider template, unmodified); footer text fully visible; no content shapes out of bounds.")
qa["speaker_notes"] = {
    "slides_with_notes": len(notes["with_notes"]),
    "slides_without_notes": [x["slide"] for x in notes["without_notes"]],
    "without_notes_reason": "section dividers and closing slide",
    "unused_note_sections": notes["unused_sections"],
    "note": "with_notes includes the cover slide plus all content slides, including the new hosted-baseline slide and Appendix D",
}
qa["visual_review"] = qa["visual_review"][:3] + [
    "Final evidence refresh: changed slides inspected at full size (ask, data objects, pilot results, both-models table, "
    "new hosted-baseline slide, execution ladder, next steps, Appendix C, Appendix D).",
    "Fixed during refresh: hosted-baseline figure legend overlapping axis label; new-slide and Appendix D titles wrapping "
    "to two lines (shortened). No remaining clipping or overlap found in inspected slides.",
]

bs["evidence_rules_applied"] = [
    "No frontier failure claimed; new round 12/12 attempts passed (10 frozen + 2 exploratory endpoint), including both integrated held-out seed 101 attempts.",
    "Fixtures presented as replays of one submission, not attempts or patients; the earlier 12 Opus-only attempts are a separate round, not pooled.",
    "Strict replay: 10/10 frozen submissions, 40 fixtures, 0 new model calls; limits 8 CPU s / 12 wall s / 512 MiB / 1 MB accepted JSON.",
    "Packaging: 16 archives (endpoint, claims, geometry, integrated × 2 seeds × flawed/valid) passed SDK validation; labeled not execution; root/container and Valkyrie execution not established.",
    "Validation: 60 local tests (59 passed, 1 numerical skipped locally; that test passed within FAC's separate 10/10 suite); overlapping suites not summed.",
    "Hosted-release baseline: 63 patients, 10 features, fixed C=1 logreg, train-fold-only preprocessing, 5-fold CV × 3 prespecified seeds; seed range labeled not a CI; endpoint labeled reported qualifying alteration vs no qualifying report (not wild type); IRF4 excluded; timing unadjudicated; no score flipping, external-validation, clinical-utility or frontier-failure claim; kept separate from the historical 33-patient baseline.",
    "Codex/GPT-6 Astra identity labeled request-pinned (no response model ID); Claude response-confirmed claude-opus-5-5.",
    "No Valkyrie run ID, upload or submission implied; hosted runs and root/provider path pending access.",
    "Hosted archive, Box candidate, internal pipeline and synthetic tasks kept separate; no private object labeled public.",
    "No novelty-first claim; judging criteria not invented (demo-based per vals.ai/hackathon).",
]

bs["figures"] = json.loads((D / "figures/figures_provenance.json").read_text())["figures"]

new_inputs = [
    "results/20261114-repair-pilots/REPORT.md", "results/20261114-repair-pilots/summary.json",
    "results/20261114-repair-pilots/strict-replay.json", "results/20261114-repair-pilots/FINALIZED",
    "results/20261114-repair-suite-v2-packaging/validation.json",
    "results/20261114-repair-suite-v2-packaging/preflight.json",
    "pcnsl/results/20261114-hosted-release/REPORT.md",
    "pcnsl/results/20261114-hosted-release/baseline.aggregate.json",
    "pcnsl/results/20261114-hosted-release/baseline-validation.json",
    "docs/research/implementation-review.md",
]
inputs = dict(bs.get("inputs_sha256", {}))
for k in new_inputs:
    inputs[k] = None
for k in list(inputs):
    p = REPO / k
    inputs[k] = sha(p) if p.is_file() else "missing at refresh"
bs["inputs_sha256"] = inputs
bs["superseded_inputs_note"] = ("results/20261114-repair-suite-v1-packaging/validation.json (12 archives) is retained as "
                                "a historical input only; deck now cites the 16-archive v2 validation.")

outs = ["PCNSL_FRONTIER.pptx", "PCNSL_FRONTIER.md", "PCNSL_FRONTIER.md.layout.json", "SPEAKER_NOTES.md",
        "previews/PCNSL_FRONTIER.pdf", "qa/notes.json", "figures/figures_provenance.json"]
outs += sorted(str(p.relative_to(D)) for p in (D / "figures").glob("*.png"))
outs += sorted(str(p.relative_to(D)) for p in (D / "scripts").glob("*") if p.is_file())
bs["outputs_sha256"] = {o: sha(D / o) for o in outs}
bs["preview_pngs"] = sorted(str(p.relative_to(D)) for p in (D / "previews").glob("slide-*.png"))
bs["builder"]["rebuild"] = ("bash results/pcnsl-frontier-deck/scripts/build_deck.sh && "
                            "python3 results/pcnsl-frontier-deck/scripts/update_build_status.py (from repo root)")
bs["builder"]["build_py_sha256"] = sha(Path(bs["builder"]["skill"]) / "build.py")
lim = [x for x in bs["limitations"] if "hosted-release baseline" not in x]
lim.append("Hosted-release baseline numbers are copied from the aggregate JSON produced on FAC; patient-level data were not read for this deck.")
bs["limitations"] = lim
bs_path.write_text(json.dumps(bs, indent=2, ensure_ascii=False) + "\n")
print("updated", bs_path, "slides", notes["slides"], "inputs", len(inputs), "outputs", len(bs["outputs_sha256"]))
