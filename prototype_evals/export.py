"""Export self-contained Harbor task folders, the dataset format Valkyrie supports."""
import json
from pathlib import Path


def export_case(case, destination):
    root = destination / case['id']
    root.mkdir(parents=True, exist_ok=False)
    for name in ('environment', 'tests', 'solution'):
        (root / name).mkdir()
    (root / 'instruction.md').write_text(case['instruction'] + '\n', encoding='utf-8')
    (root / 'task.toml').write_text('''schema_version = "1.4"
[metadata]
category = "scientific-reasoning"
tags = ["synthetic", "research", "agentic"]
[agent]
timeout_sec = 600.0
[verifier]
timeout_sec = 30.0
[environment]
cpus = 1
memory_mb = 1024
storage_mb = 2048
''')
    (root / 'environment' / 'input.json').write_text(json.dumps(case['public'], indent=2))
    (root / 'environment' / 'Dockerfile').write_text(
        'FROM python:3.12-slim\nWORKDIR /workspace\nCOPY input.json /workspace/input.json\n')
    (root / 'tests' / 'expected.json').write_text(json.dumps(case['expected'], indent=2))
    (root / 'tests' / 'grade.py').write_text(Path(__file__).with_name('grade.py').read_text())
    (root / 'tests' / 'test.sh').write_text(
        '#!/bin/sh\nset -eu\npython3 /tests/grade.py /tests/expected.json /workspace/answer.json /logs/verifier\n')
    # Only the reference-solution component receives the reference implementation.
    package = root / 'solution' / 'prototype_evals'
    package.mkdir()
    for name in ('__init__.py', 'metrics.py', 'solve.py', 'challenge.py', 'cases.py'):
        (package / name).write_text(Path(__file__).with_name(name).read_text())
    (root / 'solution' / 'solve.sh').write_text('''#!/bin/sh
set -eu
PYTHONPATH=/solution python3 - <<'PY'
import json
from pathlib import Path
from prototype_evals.solve import solve
from prototype_evals.challenge import normalize
p = Path('/workspace')
(p / 'answer.json').write_text(json.dumps(solve(normalize(json.loads((p / 'input.json').read_text())))))
PY
''')
    return root
