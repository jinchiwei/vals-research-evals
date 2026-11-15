"""Materialise reg_resect pipelines (each a self-contained folder with run.sh INPUT_DIR OUTPUT_DIR).

Kinds:
  specialist  MIND-feature rigid registration (pipeline_src/mind_reg.py + config.json); the baseline
  identity    do-nothing: the MRI landmark positions are returned unchanged (scores the initial error)
  oracle      grader self-check only: looks up the reference ultrasound landmarks by a hash of the
              case's landmarks_mri.csv in an embedded table built from the hidden references.
              NEVER ship it to an agent or into solution/ (it contains hidden references).
  slow        writes the oracle answer only after sleeping past the time limit (timeout check)
  lps         writes the oracle answer in ITK/LPS instead of RAS (wrong-frame check)
"""
import hashlib
import json
import shutil
from pathlib import Path

KINDS = ('specialist', 'identity', 'oracle', 'slow', 'lps')
SRC = Path(__file__).resolve().parent / 'pipeline_src'

RUN_PY = '''#!/bin/bash
# Entry point contract: run.sh INPUT_DIR OUTPUT_DIR (one case). Offline; python3 from the image venv.
set -euo pipefail
HERE="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
{pre}exec python3 -I "$HERE/{script}" "$1" "$2"{args}
'''

ORACLE_PY = '''"""Lookup pipeline for grader self-checks. Usage: oracle.py INPUT_DIR OUTPUT_DIR [ras|lps]"""
import hashlib, json, sys
from pathlib import Path
here = Path(__file__).resolve().parent
table = json.loads((here / "table.json").read_text())
key = hashlib.sha256((Path(sys.argv[1]) / "landmarks_mri.csv").read_bytes()).hexdigest()
text = table[key]
if len(sys.argv) > 3 and sys.argv[3] == "lps":
    lines = text.strip().splitlines()
    out = [lines[0]]
    for line in lines[1:]:
        i, x, y, z = line.split(",")
        out.append(f"{i},{-float(x):.4f},{-float(y):.4f},{float(z):.4f}")
    text = "\\n".join(out) + "\\n"
Path(sys.argv[2]).mkdir(parents=True, exist_ok=True)
(Path(sys.argv[2]) / "landmarks_us.csv").write_text(text)
'''


def landmark_key(input_dir):
    return hashlib.sha256((Path(input_dir) / 'landmarks_mri.csv').read_bytes()).hexdigest()


def oracle_table(hidden_root):
    """{sha256(input/landmarks_mri.csv): reference landmarks_us.csv text} for every hidden case."""
    table = {}
    for case in sorted(Path(hidden_root).iterdir()):
        table[landmark_key(case / 'input')] = (case / 'reference' / 'landmarks_us.csv').read_text()
    return table


def write_pipeline(kind, dest, *, hidden_root=None, config=None, sleep_seconds=None):
    """Write pipeline `kind` into dest (must not exist). Returns dest."""
    if kind not in KINDS:
        raise ValueError(f'unknown pipeline kind {kind!r}')
    dest = Path(dest)
    dest.mkdir(parents=True)
    if kind == 'specialist':
        shutil.copyfile(SRC / 'mind_reg.py', dest / 'mind_reg.py')
        (dest / 'config.json').write_text(json.dumps(config or {}, indent=2) + '\n')
        run = RUN_PY.format(pre='', script='mind_reg.py', args='')
    elif kind == 'identity':
        run = ('#!/bin/bash\n# Do-nothing pipeline: return the MRI landmark positions unchanged.\nset -euo pipefail\n'
               'mkdir -p "$2"\ncp "$1/landmarks_mri.csv" "$2/landmarks_us.csv"\n')
    else:
        if hidden_root is None:
            raise ValueError(f'{kind} needs hidden_root (it embeds the hidden references)')
        (dest / 'oracle.py').write_text(ORACLE_PY)
        (dest / 'table.json').write_text(json.dumps(oracle_table(hidden_root)))
        pre = f'sleep {float(sleep_seconds or 0)}\n' if kind == 'slow' else ''
        run = RUN_PY.format(pre=pre, script='oracle.py', args=' lps' if kind == 'lps' else '')
    (dest / 'run.sh').write_text(run)
    (dest / 'run.sh').chmod(0o755)
    return dest
