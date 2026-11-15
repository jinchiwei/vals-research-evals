"""Materialise the ecg_ptbxl Harbor task from family_spec.json (no platform calls).

SUPERSEDED (2026-11-14 integration): the suite export is spec.py + suite.core.export (cohort grading,
tests/grade.py = the shared core grader). This legacy builder and its family-local grade.py entry point
are kept for the family self-check only; its tasks use the earlier fraction reward, not the cohort rule.

    conda run -n vals-suite-ecg_ptbxl python -I suite/families/ecg_ptbxl/build_task.py [--out DIR]

Writes DATA_ROOT/task/ecg_ptbxl-<hash>/ with task.toml, instruction.md, environment/ (agent image
context: Dockerfile + development data), tests/ (grader, hidden inputs and labels, specialist summary)
and solution/ (simple reference pipeline). Prints a manifest tagged by audience and checks that no
hidden record id or label file reaches the agent's build context.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

TOML = """schema_version = "1.4"
artifacts = [{{ source = "/workspace/output", exclude = ["*.tmp", "__pycache__", "*.pyc"] }}]

[metadata]
category = "clinical-ml"
family = "ecg_ptbxl"
tier = "build"
dataset = "PTB-XL 1.0.3 (PhysioNet, CC BY 4.0)"
n_hidden = {n_hidden}
runtime_budget_sec_total = {budget:.0f}
seed = 20261114

[agent]
timeout_sec = {agent_timeout:.1f}
network_mode = "allowlist"
allowed_hosts = {hosts}

[verifier]
timeout_sec = {verifier_timeout:.1f}
environment_mode = "separate"
network_mode = "no-network"

[verifier.environment]
cpus = {cpus}
memory_mb = {mem}

[environment]
cpus = {cpus}
memory_mb = {mem}
storage_mb = 20480
workdir = "/workspace"
build_timeout_sec = 1500.0
network_mode = "no-network"
env = {{ CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1", PIP_NO_INDEX = "1" }}
"""

DOCKERFILE = """FROM python:3.12-slim
RUN python3 -m venv /opt/benchmark-venv \\
 && /opt/benchmark-venv/bin/python -m pip install --no-cache-dir {pins} \\
 && /opt/benchmark-venv/bin/python -m pip install --no-cache-dir torch==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu
ENV PATH=/opt/benchmark-venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \\
    OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
RUN python3 -c "import sys, numpy, scipy, pandas, sklearn, torch; assert sys.prefix == '/opt/benchmark-venv'; assert not torch.cuda.is_available()" \\
 && command -v setpriv && command -v timeout
WORKDIR /workspace
COPY data/ /workspace/data/
RUN mkdir -p /workspace/output/pipeline /workspace/output/notes
"""

LICENSE_DATA = """# Data licence and attribution

The ECGs and labels in `dev/` are derived from **PTB-XL, version 1.0.3**:

Wagner, P., Strodthoff, N., Bousseljot, R., Samek, W., & Schaeffter, T. (2022). PTB-XL, a large publicly
available electrocardiography dataset (version 1.0.3). PhysioNet. https://doi.org/10.13026/kfzx-aw45
(Wagner et al., Scientific Data 7, 154, 2020; Goldberger et al., PhysioNet, Circulation 101(23), 2000.)

Licence: Creative Commons Attribution 4.0 International (https://creativecommons.org/licenses/by/4.0/).

Modifications: 100 Hz records only, re-packed losslessly as int16 microvolts; a stratified subsample of the
dataset's folds 1-8; random record and patient identifiers; ages over 89 (coded 300) written as 90; sex coded
M/F; SCP-ECG statements aggregated to five diagnostic superclasses.
"""


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    spec = json.loads((HERE / "family_spec.json").read_text())
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(spec["data_root"]))
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    work = a.root / "work"
    _g = __import__("importlib.util").util
    gs = _g.spec_from_file_location("ecg_grade_b", HERE / "grade.py")
    G = _g.module_from_spec(gs)
    gs.loader.exec_module(G)

    ref = work / "hidden" / "reference.csv"
    n_hidden = sum(1 for _ in open(ref)) - 1
    tag = hashlib.sha256((sha(ref) + sha(work / "dev" / "labels.csv") + sha(HERE / "grade.py")).encode()).hexdigest()[:10]
    out = (a.out or a.root / "task") / f"ecg_ptbxl-{tag}"
    shutil.rmtree(out, ignore_errors=True)
    r = spec["resources"]
    budget = G.time_budget(n_hidden)
    vt = max(r["verifier_timeout_sec"], budget * G.TIME_RULE["hard_kill_factor"] + 300)
    (out / "environment" / "data" / "dev").mkdir(parents=True)
    (out / "task.toml").write_text(TOML.format(n_hidden=n_hidden, budget=budget, agent_timeout=r["agent_timeout_sec"],
                                               hosts=json.dumps(r["agent_allowed_hosts"]), verifier_timeout=vt,
                                               cpus=r["cpus"], mem=r["memory_mb"]))
    readme = (HERE / "README.md").read_text()
    (out / "instruction.md").write_text(readme)
    pins = " ".join(l.strip() for l in (HERE / "image_requirements.txt").read_text().splitlines()
                    if l.strip() and not l.startswith("#"))
    (out / "environment" / "Dockerfile").write_text(DOCKERFILE.format(pins=pins))
    for f in spec["agent_visible"]["files"]:
        shutil.copy(work / "dev" / f, out / "environment" / "data" / "dev" / f)
    (out / "environment" / "data" / "README.md").write_text(readme)
    (out / "environment" / "data" / "LICENSE-DATA.md").write_text(LICENSE_DATA)

    tests = out / "tests"
    (tests / "hidden").mkdir(parents=True)
    shutil.copy(HERE / "grade.py", tests / "grade.py")
    shutil.copytree(work / "hidden" / "input", tests / "hidden" / "input")
    shutil.copy(ref, tests / "hidden" / "reference.csv")
    shutil.copy(work / "specialist.json", tests / "specialist.json")
    (tests / "test.sh").write_text("#!/usr/bin/env bash\n" + spec["verifier_only"]["test_sh"] + "\n")

    sol = out / "solution"
    shutil.copytree(work / "simple_pipeline", sol / "pipeline", ignore=shutil.ignore_patterns("__pycache__"))
    (sol / "solve.sh").write_text("#!/usr/bin/env bash\nset -euo pipefail\nmkdir -p /workspace/output\n"
                                  "rm -rf /workspace/output/pipeline\ncp -r /solution/pipeline /workspace/output/pipeline\n")
    for p in out.rglob("*.sh"):
        p.chmod(0o755)

    # leakage checks: no hidden id, no reference file, no crosswalk in the agent's build context or instruction
    hidden_ids = [l.split(",")[0] for l in open(ref).read().splitlines()[1:]]
    agent_files = [p for p in (out / "environment").rglob("*") if p.is_file()] + [out / "instruction.md"]
    for p in agent_files:
        if p.suffix in (".csv", ".md", ""):
            text = p.read_text(errors="ignore")
            assert not any(h in text for h in hidden_ids), f"hidden id leaked into {p}"
        assert p.name not in ("reference.csv", "crosswalk.csv", "specialist.json"), p
    manifest = {}
    for p in sorted(out.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(out))
            aud = "agent" if rel.startswith("environment/") or rel == "instruction.md" else (
                "verifier" if rel.startswith("tests/") else "oracle" if rel.startswith("solution/") else "platform")
            manifest[rel] = {"audience": aud, "bytes": p.stat().st_size, "sha256": sha(p)}
    (out.parent / f"{out.name}.manifest.json").write_text(json.dumps(manifest, indent=1))
    size = lambda aud: sum(v["bytes"] for v in manifest.values() if v["audience"] == aud) / 1e6
    print(json.dumps({"task": str(out), "agent_MB": round(size("agent"), 1), "verifier_MB": round(size("verifier"), 1),
                      "oracle_MB": round(size("oracle"), 1), "n_hidden": n_hidden, "budget_s": budget,
                      "verifier_timeout_s": vt}, indent=1))


if __name__ == "__main__":
    main()
