#!/usr/bin/env bash
# Rebuild figures, sidecar, PPTX, notes and previews. Run from repo root.
set -euo pipefail
D=results/pcnsl-frontier-deck
SKILL=/home/jkwei/arcadia/superstack/skills/build-pptx
export MPLCONFIGDIR=/tmp/pcnsl-deck-mpl
PY="env PYTHONPATH=/tmp/vals-deck-pydeps python3.12"
$PY $D/scripts/make_figures.py . $D/figures
(cd $D && $PY $SKILL/build.py --input PCNSL_FRONTIER.md --output PCNSL_FRONTIER.pptx --plan-only --use-blocks=never)
python3 $D/scripts/patch_sidecar.py $D/PCNSL_FRONTIER.md.layout.json
(cd $D && $PY $SKILL/build.py --input PCNSL_FRONTIER.md --output PCNSL_FRONTIER.pptx --use-blocks=never)
mkdir -p $D/qa && $PY $D/scripts/add_notes.py $D/PCNSL_FRONTIER.pptx $D/SPEAKER_NOTES.md > $D/qa/notes.json
rm -rf $D/previews && mkdir -p $D/previews /tmp/pcnsl-deck-lo
PATH=/tmp/lo-qa/bin:$PATH timeout 300 soffice -env:UserInstallation=file:///tmp/pcnsl-deck-lo --headless \
  --convert-to pdf --outdir $D/previews $D/PCNSL_FRONTIER.pptx
PATH=/tmp/lo-qa/bin:$PATH pdftoppm -r 110 -png $D/previews/PCNSL_FRONTIER.pdf $D/previews/slide
