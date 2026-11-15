"""Post-build pass: speaker notes for the auto-generated cover and Thank-You slides.

Run after build.py: ~/miniconda3/envs/vals-suite/bin/python results/suite-deck/src/finalize.py
"""
from pathlib import Path

from pptx import Presentation

DECK = Path(__file__).resolve().parents[1] / "CLINICAL_SUITE.pptx"
prs = Presentation(DECK)
slides = list(prs.slides)
slides[0].notes_slide.notes_text_frame.text = (
    "Title slide. Name the track (Vals AI, Build Your Own Eval) and hand over to the overview on the next slide.")
slides[-1].notes_slide.notes_text_frame.text = (
    "Closing slide. In the 3-minute demo, stop after 'Limits and how to run' (slide 11); the slides between the Backup divider and this one are for questions.")
prs.save(DECK)
print("notes added to cover and closing slides:", DECK)

# Rebuild the presenter-handout PDF so it carries the cover and closing notes too.
import sys  # noqa: E402
sys.path.insert(0, str(Path.home() / ".claude/skills/build-pptx"))
from notes_pdf import build_notes_pdf  # noqa: E402
print("notes PDF:", build_notes_pdf(DECK))
