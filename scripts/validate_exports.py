"""Run with .venv-valkyrie/bin/python; no network or uploads."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
from valkyrie.sdk.task_archive import find_task_folders, pack_task, task_problems

parser = argparse.ArgumentParser()
parser.add_argument('tasks', type=Path)
parser.add_argument('out', type=Path)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
rows = []
for name, task in find_task_folders(args.tasks).items():
    problems = task_problems(task)
    if problems:
        raise SystemExit(f'{name}: {problems}')
    archive = args.out / (name + '.zip')
    pack_task(task, archive)
    rows.append(dict(task=name, problems=problems,
                     archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
result = dict(cli=importlib.metadata.version('valkyrie-cli'),
              sdk=importlib.metadata.version('valkyrie-sdk'), hosted_run=False, tasks=rows)
(args.out / 'validation.json').write_text(json.dumps(result, indent=2))
print(f'Validated and packed {len(rows)} tasks; no uploads performed.')
