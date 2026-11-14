"""Apply deliberate named-layout choices to the builder's default sidecar.

Run after `build.py --plan-only`. Only named layouts are used (no composition
or freeform). Content hashes are preserved so the builder replays these entries.
"""
import json
import sys
from pathlib import Path

p = Path(sys.argv[1])
plan = json.loads(p.read_text())
by_title = {}
for s in plan["slides"]:
    prm = s["params"]
    for key in ("image",):
        if isinstance(prm.get(key), str) and "/figures/" in prm[key]:
            prm[key] = "figures/" + prm[key].split("/figures/")[-1]
    if "images" in prm:
        prm["images"] = ["figures/" + i.split("/figures/")[-1] if "/figures/" in i else i for i in prm["images"]]
    by_title[prm.get("title", s["slide_id"])] = s


def get(prefix):
    hits = [s for t, s in by_title.items() if t.startswith(prefix)]
    assert len(hits) == 1, prefix
    return hits[0]


# 1. Ask slide: three cards + takeaway footer
s = get("The ask")
cards = s["params"]["cards"]
cards[2]["body"] = ("Tasks, controls and 16-archive package ready. Both tested models passed all 12 attempts "
                    "(10 frozen + 2 exploratory). Hosted run pending access.")
s["kind"] = "cards-with-takeaway"
s["params"]["callout"] = {"text": "Source: vals.ai/hackathon. Honest headline: a prepared eval with working controls "
                                  "— no demonstrated frontier failure yet.", "tone": "dark"}

# 2. Scoring principle: aside label
s = get("What we score")
s["params"]["aside"]["label"] = "Why"
s["params"]["aside"]["body"] = ("Low biological predictability is not an agent failure. A correct null or inconclusive "
                                "result earns full credit; a high AUROC from a leaked split or wrong endpoint earns none.")
s["params"]["alt"] = "Schematic two-by-two scoring matrix"

# 3. Hosted inventory: chart + stat tiles
s = get("Hosted v1.0 inventory")
s["kind"] = "stat-callouts-right"
s["params"] = {"title": s["params"]["title"], "lede": s["params"]["lede"], "section_label": s["params"]["section_label"],
               "image": "figures/fig_hosted_counts.png",
               "stats": [{"value": "150", "label": "patients; T1, CE-T1, FLAIR, ADC each"},
                         {"value": "64", "label": "patients with genomic records"},
                         {"value": "63", "label": "records + all 10 FLAIR features finite"},
                         {"value": "0", "label": "DSC/CBV files detected"}]}

# 4. Mechanism map: image is the point
s = get("Thirty candidate")
s["kind"] = "content-image-only"
s["params"] = {"title": s["params"]["title"], "lede": s["params"]["lede"], "section_label": s["params"]["section_label"],
               "images": ["figures/fig_mechanism_map.png"], "tables": []}

# 5. Families: four cards + takeaway
s = get("Three repair families")
s["kind"] = "cards-with-takeaway"
s["params"]["callout"] = {"text": "All four are synthetic counterfactual tasks with independent references: they test research "
                                  "behavior, not real PCNSL predictive accuracy.", "tone": "dark"}
s["params"]["cards"] = [c for c in s["params"]["cards"] if c["label"] != ""]
s["params"]["cards"][-1]["body"] = ("Endpoint cohort, transitive identities, artifact ancestry, permutation nulls and "
                                    "Holm claims in one synthetic repository.")
s["params"]["lede"] = ""

# 6. Protocol: image only with lede caption
s = get("How an attempt")
s["kind"] = "content-image-only"
s["params"] = {"title": s["params"]["title"], "section_label": s["params"]["section_label"],
               "lede": "Hidden new-cohort replay checks the repair; the clean twin checks for unnecessary damage.",
               "images": ["figures/fig_eval_protocol.png"], "tables": []}

# 7. Pilot results: chart + stat tiles
s = get("Pilot results")
s["kind"] = "stat-callouts-right"
s["params"] = {"title": s["params"]["title"], "lede": s["params"]["lede"], "section_label": s["params"]["section_label"],
               "image": "figures/fig_pilot_results.png",
               "stats": [{"value": "12/12", "label": "attempts passed this round, both models (10 frozen + 2 exploratory)"},
                         {"value": "10/10", "label": "frozen submissions re-passed strict replay: 40 fixtures, 0 new model calls"},
                         {"value": "12/12", "label": "separate earlier Opus-only round on original tasks; not pooled"},
                         {"value": "0", "label": "demonstrated frontier failures"}]}

# 8a. Hosted-release-only baseline (measured)
s = get("Hosted-release baseline")
s["params"]["aside"] = {"label": "Bounds", "icon": None,
                        "body": "Seed range is not a confidence interval. Label is reported qualifying alteration vs no "
                                "qualifying report, not biological wild type; IRF4 excluded (2 positives); scan–specimen "
                                "timing not clinically adjudicated. No score flipping; no external-validation, "
                                "clinical-utility or frontier-failure claim. Separate from the historical 33-patient baseline."}
s["params"]["alt"] = "Pooled out-of-fold AUROC by seed for MYD88 and CD79B with prevalence control"

# 8b. Historical endpoint schematic (appendix D)
s = get("Appendix D")
s["params"]["aside"] = {"label": "Lesson", "icon": None,
                        "body": "Endpoint definition is a gradeable agent decision. The 33-patient retrospective subset "
                                "supports no clinical-utility, generalization or frontier-failure claim."}
s["params"]["alt"] = "Schematic of 33 patients under two IRF4 label definitions"

# 9. Conclusions: sentence-case card bodies
s = get("Next steps")
for c in s["params"]["cards"]:
    c["body"] = c["body"][:1].upper() + c["body"][1:]

p.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
print("patched", p)
