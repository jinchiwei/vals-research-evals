"""Reproduce saved agent programs on their original inputs in a fresh sandbox.

No answer, reference code, credential, repository or network is exposed to the
submitted program. The host grades the resulting artifact only after execution.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_evals.cases import generate
from research_evals.challenge import complicate
from research_evals.grade import grade
from research_evals.pilot import sandbox_command

rows = []
for run in sorted((ROOT / 'results').glob('*')):
    manifest_path = run / 'manifest.json'
    if not manifest_path.exists():
        continue
    manifest = json.loads(manifest_path.read_text())
    cases = generate(manifest['seed'])
    if manifest.get('workflow'):
        cases = [complicate(c) for c in cases]
    for case in cases:
        original = run / case['id'] / 'workspace'
        analysis = original / 'analysis.py'
        if not analysis.exists():
            continue
        data = json.loads((original / 'input.json').read_text())
        if data != case['public']:
            raise SystemExit(f'Input changed or generator drift: {run.name}/{case["id"]}')
        with tempfile.TemporaryDirectory() as h, tempfile.TemporaryDirectory() as w:
            workspace = Path(w)
            (workspace / 'input.json').write_text(json.dumps(data))
            (workspace / 'analysis.py').write_bytes(analysis.read_bytes())
            command = sandbox_command(workspace, Path(h), []) + [
                '--unshare-net', '/usr/bin/python3', '/workspace/analysis.py']
            proc = subprocess.run(command, capture_output=True, text=True, timeout=30)
            try:
                answer = json.loads((workspace / 'answer.json').read_text())
            except (OSError, ValueError):
                answer = None
            result = grade(case['expected'], answer)
            row = dict(run=run.name, case=case['id'], exit_code=proc.returncode,
                       input_reproduced=True, **result)
            rows.append(row)
            print(json.dumps(row))
(ROOT / 'results/replay-validation.json').write_text(json.dumps(rows, indent=2))
if any(r['exit_code'] or not r['resolved'] for r in rows):
    raise SystemExit(1)
print(f'{len(rows)} saved agent analyses reproduced in fresh network-isolated workspaces.')
