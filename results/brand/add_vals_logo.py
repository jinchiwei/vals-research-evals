"""Post-build pass: put the Vals logo badge on the deck's title slide (lower right).

build-pptx renders only the byline on the cover, so logos go on afterwards with
python-pptx, as its SKILL.md describes. The green logo has a contrast ratio of 1.6
on the slate cover, so the badge version (logo on an off-white rounded panel,
ratio 9.0) is used. Idempotent: an existing badge (shape name below) is replaced.

    ~/miniconda3/envs/vals-suite/bin/python results/brand/add_vals_logo.py \
        results/suite-deck/CLINICAL_SUITE.pptx
"""
import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.util import Emu, Inches

NAME = "vals-logo-badge"
BADGE = Path(__file__).resolve().parent / "vals-logo-badge.png"


def main(path):
    prs = Presentation(path)
    slide = prs.slides[0]
    for shape in list(slide.shapes):
        if shape.name == NAME:
            shape._element.getparent().remove(shape._element)
    w_px, h_px = Image.open(BADGE).size
    height = Inches(0.95)
    width = Emu(int(height * w_px / h_px))
    margin = Inches(0.5)
    left = prs.slide_width - width - margin
    top = prs.slide_height - height - margin
    pic = slide.shapes.add_picture(str(BADGE), left, top, width, height)
    pic.name = NAME
    prs.save(path)
    print(f"badge placed on slide 1 of {path}")


if __name__ == "__main__":
    main(sys.argv[1])
