"""Copy the exported Harbor tasks into tasks/ without any data.

The exported tasks under dist/ (git-ignored) hold the agent's development data
(environment/data), the hidden cases and references (tests/hidden) and the
specialist's stored outputs on those cases (tests/specialist). None of that goes
into Git. Everything else is copied: instruction.md, task.toml, the Dockerfile,
the reference solution and the grader code.

    ~/miniconda3/envs/vals-suite/bin/python scripts/publish_task_definitions.py
"""
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCES = {  # Valkyrie dataset -> exported folder
    "suite-clinical-v1@2": "dist/suite-tasks-v3",
    "suite-vessel-v1@1": "dist/suite-tasks-vessel-v1",
    "suite-causal-v1@1": "dist/suite-tasks-causal-v1",
    "suite-report-label-v1@1": "dist/suite-tasks-label-v1",
    "suite-hc18-keepworking-v1@1": "dist/suite-tasks-k1",
    "suite-hc18-clockcheck-v1@1": "dist/suite-tasks-k2",
}
EXCLUDE = {("environment", "data"), ("tests", "hidden"), ("tests", "specialist")}


def ignore(dirpath, names):
    rel = Path(dirpath)
    return [n for n in names if (rel.name, n) in EXCLUDE or n == "__pycache__"]


def main():
    out = REPO / "tasks"
    for dataset, src in SOURCES.items():
        for task_toml in sorted((REPO / src).rglob("task.toml")):
            task = task_toml.parent
            dest = out / dataset / task.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(task, dest, ignore=ignore)
            print(dataset, task.name)


if __name__ == "__main__":
    main()
