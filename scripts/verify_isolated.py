"""Run exported oracle and verifier phases; requires Linux bubblewrap."""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research_evals.pilot import sandbox_command

parser = argparse.ArgumentParser()
parser.add_argument('tasks', type=Path)
args = parser.parse_args()
passed = 0
for task in sorted(args.tasks.resolve().iterdir()):
    if not (task / 'task.toml').exists():
        continue
    with tempfile.TemporaryDirectory() as h, tempfile.TemporaryDirectory() as w, tempfile.TemporaryDirectory() as logs:
        home, work = Path(h), Path(w)
        (work / 'input.json').write_bytes((task / 'environment/input.json').read_bytes())
        for component, command in [('solution', 'solve.sh'), ('tests', 'test.sh')]:
            argv = sandbox_command(work, home, [])
            argv += ['--ro-bind', str(task / component), '/' + component]
            if component == 'tests':
                argv += ['--bind', logs, '/logs/verifier']
            argv += ['/bin/sh', '/' + component + '/' + command]
            result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise SystemExit(f'{task.name}: {result.stderr}')
        if float((Path(logs) / 'reward.txt').read_text()) != 1:
            raise SystemExit(f'{task.name}: oracle failed')
        passed += 1
print(f'{passed} isolated oracle/verifier roundtrips passed')
