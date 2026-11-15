"""Materialise the toy family's self-contained pipelines: run.sh + segment.py per directory."""
import shutil
from pathlib import Path

KINDS = ('oracle', 'specialist', 'slow', 'wrong_geometry', 'wrong_units')
SOURCE = Path(__file__).resolve().parent / 'pipeline_src' / 'segment.py'

RUN_SH = '''#!/bin/bash
# Entry point contract: run.sh INPUT_DIR OUTPUT_DIR (one case). Offline; uses python3 on PATH.
set -euo pipefail
HERE="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
exec python3 "$HERE/segment.py" "$1" "$2" {mode}
'''


def write_pipeline(kind, dest):
    """Write pipeline `kind` into dest (created; must not exist). Returns dest."""
    if kind not in KINDS:
        raise ValueError(f'unknown pipeline kind {kind!r}')
    dest = Path(dest)
    dest.mkdir(parents=True)
    shutil.copyfile(SOURCE, dest / 'segment.py')
    (dest / 'run.sh').write_text(RUN_SH.format(mode=kind))
    (dest / 'run.sh').chmod(0o755)
    return dest
