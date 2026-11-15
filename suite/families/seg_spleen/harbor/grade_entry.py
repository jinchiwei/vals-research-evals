"""Harbor verifier entry for seg_spleen. Copied to /tests/grade_entry.py by the exporter."""
import json
import os
import shutil
import sys
from pathlib import Path

TESTS = Path("/tests")
LOGS = Path("/logs/verifier")
PIPELINE = Path("/workspace/output/pipeline")

# Fail closed: an oracle bundle or solution in the verifier sandbox means a mis-built task.
if Path("/solution").exists() or Path("/bundle").exists():
    print("refusing to grade: /solution or /bundle present", flush=True)
    sys.exit(2)

sys.path.insert(0, str(TESTS))
import grader  # noqa: E402

cfg = json.loads((TESTS / "grading.json").read_text())
LOGS.mkdir(parents=True, exist_ok=True)
(LOGS / "reward.json").write_text(json.dumps(grader.zero_reward()))
os.chmod(TESTS, 0o700)
for root, dirs, files in os.walk(TESTS):
    for n in dirs + files:
        os.chmod(os.path.join(root, n), 0o700 if n in dirs else 0o600)
work = Path("/eval")
work.mkdir(exist_ok=True)
os.chmod(work, 0o755)
staged = work / "pipeline"
if PIPELINE.is_dir() and (PIPELINE / "run.sh").is_file():
    shutil.copytree(PIPELINE, staged, symlinks=False, dirs_exist_ok=True)
    for root, dirs, files in os.walk(staged):
        os.chmod(root, 0o755)
        for f in files:
            os.chmod(os.path.join(root, f), 0o755)
else:
    staged.mkdir(exist_ok=True)
    (staged / "run.sh").write_text("echo 'no pipeline submitted' >&2; exit 1\n")
specialist = json.loads((TESTS / "specialist.json").read_text())
reward, metrics = grader.grade(staged, TESTS / "hidden", work, specialist,
                               cfg["case_time_limit_sec"], cfg["threads"], unprivileged=True,
                               extra_env=cfg.get("pipeline_env", {}))
(LOGS / "metrics.json").write_text(json.dumps(metrics, default=float))
(LOGS / "reward.json").write_text(json.dumps(reward))
print(json.dumps({"summary": reward, "specialist_mean_dice": specialist.get("mean_dice"),
                  "specialist_acceptable": specialist.get("acceptable_fraction")}), flush=True)
