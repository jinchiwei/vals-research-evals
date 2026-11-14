"""Copy SPEAKER_NOTES.md sections into PPTX notes by slide-title prefix.

Usage: python add_notes.py DECK.pptx SPEAKER_NOTES.md
Prints a JSON summary (slides with notes / without) for build-status.json.
"""
import json
import re
import sys

from pptx import Presentation

deck, notes_md = sys.argv[1], sys.argv[2]
sections = {}
for block in re.split(r"^## ", open(notes_md, encoding="utf-8").read(), flags=re.M)[1:]:
    head, _, body = block.partition("\n")
    sections[head.strip()] = body.strip()

prs = Presentation(deck)
used, matched, unmatched = set(), [], []
for idx, slide in enumerate(prs.slides, 1):
    texts = [sh.text_frame.text.strip() for sh in slide.shapes if sh.has_text_frame and sh.text_frame.text.strip()]
    hit = None
    for key, body in sections.items():
        if key in used:
            continue
        if any(t.replace("\n", " ").replace("\v", " ").startswith(key) for t in texts):
            hit = key
            break
    if hit:
        used.add(hit)
        slide.notes_slide.notes_text_frame.text = sections[hit]
        matched.append({"slide": idx, "notes_key": hit})
    else:
        unmatched.append({"slide": idx, "first_text": texts[0][:60] if texts else ""})
prs.save(deck)
print(json.dumps({"slides": len(prs.slides), "with_notes": matched, "without_notes": unmatched,
                  "unused_sections": [k for k in sections if k not in used]}, indent=1))
