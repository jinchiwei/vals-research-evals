"""Bounded frontier repair pilots with hidden-fixture replay. Not a Valkyrie run."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prototype_evals.pilot import sandbox_command, model_response_ids

REPLAY_BOOTSTRAP = (
    "import resource,os; "
    "resource.setrlimit(resource.RLIMIT_CPU,(8,8)); "
    "resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2)); "
    "resource.setrlimit(resource.RLIMIT_FSIZE,(2000000,2000000)); "
    "resource.setrlimit(resource.RLIMIT_CORE,(0,0)); "
    "resource.setrlimit(resource.RLIMIT_NOFILE,(64,64)); "
    "os.execv('/usr/bin/python3',['python3','-B','/workspace/analysis.py',"
    "'/workspace/_evaluation_input.json','/workspace/_evaluation_output.json'])"
)


def strict_json(text):
    def constant(value):
        raise ValueError("Nonfinite JSON constant")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(text, parse_constant=constant, object_pairs_hook=unique)

def classify_trial(status, responded, passed):
    if status == "timeout":
        return "resource_limit"
    if status != "completed" or not responded:
        return "infrastructure_error"
    return "pass" if passed else "candidate_semantic_failure"


def evaluate_program(workspace, hidden, comparator, timeout=12):
    workspace = Path(workspace)
    members = list(workspace.rglob("*"))
    if any(p.is_symlink() for p in members):
        raise ValueError("Symlink in submitted workspace")
    if len(members) > 250 or sum(p.stat().st_size for p in members if p.is_file()) > 20_000_000:
        raise ValueError("Submitted workspace exceeds replay limits")
    checks = []
    # Probe the verifier runtime independently of submitted code so unavailable
    # namespaces/interpreters cannot be counted as model reasoning failures.
    with tempfile.TemporaryDirectory(prefix="vals-replay-probe-") as probe:
        base = Path(probe)
        work, agent_home = base / "workspace", base / "home"
        work.mkdir()
        agent_home.mkdir()
        command = sandbox_command(work, agent_home, []) + ["--unshare-net", "/usr/bin/python3", "-c", "print('ready')"]
        try:
            ready = subprocess.run(command, capture_output=True, text=True, timeout=10)
            runtime_ok = ready.returncode == 0 and ready.stdout.strip() == "ready"
        except (OSError, subprocess.TimeoutExpired):
            runtime_ok = False
        if not runtime_ok:
            return {"passed": False, "passed_fixtures": 0, "total_fixtures": len(hidden),
                    "checks": [], "infrastructure_error": "verifier_runtime_unavailable"}
    for index, fixture in enumerate(hidden):
        with tempfile.TemporaryDirectory(prefix="vals-hidden-replay-") as temporary:
            base = Path(temporary)
            work, agent_home = base / "workspace", base / "home"
            shutil.copytree(workspace, work)
            agent_home.mkdir()
            input_path, output_path = work / "_evaluation_input.json", work / "_evaluation_output.json"
            input_path.write_text(json.dumps(fixture["input"], allow_nan=False))
            if output_path.exists():
                output_path.unlink()
            cmd = sandbox_command(work, agent_home, []) + ["--unshare-net", "/usr/bin/python3", "-I", "-c", REPLAY_BOOTSTRAP]
            error, passed = None, False
            try:
                process = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                if process.returncode and process.stderr.startswith("bwrap:"):
                    return {"passed": False, "passed_fixtures": sum(c["passed"] for c in checks),
                            "total_fixtures": len(hidden), "checks": checks,
                            "infrastructure_error": "verifier_isolation_failed"}
                if process.returncode in {-signal.SIGXCPU, -signal.SIGXFSZ}:
                    error = "replay_resource_limit"
                elif process.returncode:
                    error = "program_error"
                elif output_path.is_symlink() or not output_path.is_file() or output_path.stat().st_size > 1_000_000:
                    error = "missing_or_invalid_output"
                else:
                    actual = strict_json(output_path.read_text())
                    comparison = comparator(fixture["expected"], actual)
                    passed = bool(comparison.get("passed", False)) if isinstance(comparison, dict) else bool(comparison)
                    if not passed:
                        error = "output_mismatch"
            except subprocess.TimeoutExpired:
                error = "replay_timeout"
            except (ValueError, OSError, TypeError):
                error = "invalid_output"
            checks.append({"fixture": index, "passed": passed, "error": error})
    return {"passed": bool(checks) and all(c["passed"] for c in checks),
            "passed_fixtures": sum(c["passed"] for c in checks), "total_fixtures": len(checks), "checks": checks}


def _execute(command, prompt, stdout, stderr, timeout):
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                               text=True, start_new_session=True)
    try:
        process.communicate(prompt, timeout=timeout)
        return "completed" if process.returncode == 0 else "runtime_error", process.returncode
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        return "timeout", process.returncode


def model_command(backend, model, effort, workspace, agent_home, budget):
    cmd = sandbox_command(workspace, agent_home, [])
    if backend == "claude":
        binary = Path(shutil.which("claude") or "/missing").resolve()
        credential = Path.home() / ".claude/.credentials.json"
        if not binary.is_file() or not credential.is_file():
            raise RuntimeError("Existing Claude binary/login required")
        (agent_home / ".claude").mkdir()
        original = Path.home() / ".claude.json"
        settings = json.loads(original.read_text()) if original.exists() else {}
        (agent_home / ".claude.json").write_text(json.dumps({"hasCompletedOnboarding": True,
            "oauthAccount": settings.get("oauthAccount", {}),
            "projects": {"/workspace": {"hasTrustDialogAccepted": True}}}))
        return cmd + ["--ro-bind", str(binary), "/opt/claude", "--ro-bind", str(credential),
            "/home/agent/.claude/.credentials.json", "/opt/claude", "-p", "--safe-mode",
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--model", model,
            "--effort", effort, "--permission-mode", "dontAsk", "--tools", "Read,Write,Edit,Bash",
            "--allowedTools", "Read,Write,Edit,Bash", "--no-session-persistence",
            "--max-budget-usd", str(budget), "--output-format", "stream-json", "--verbose"]
    if backend == "codex":
        wrapper = Path(shutil.which("codex") or "/missing").resolve()
        vendor = wrapper.parent.parent / "node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl"
        binary, credential = vendor / "bin/codex", Path.home() / ".codex/auth.json"
        if not binary.is_file() or not credential.is_file():
            raise RuntimeError("Existing native Codex binary/login required")
        (agent_home / ".codex").mkdir()
        return cmd + ["--ro-bind", str(vendor), "/opt/codex-runtime", "--ro-bind", str(credential),
            "/home/agent/.codex/auth.json", "/opt/codex-runtime/bin/codex", "exec",
            "--ignore-user-config", "--ignore-rules", "--ephemeral", "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox", "--model", model,
            "-c", f'model_reasoning_effort="{effort}"', "-c", 'web_search="disabled"', "--json", "-"]
    raise ValueError("Unknown backend")


def run_one(case, destination, backend, model, effort="high", timeout=600, budget=5):
    from repair_evals import compare
    destination.mkdir(parents=True, exist_ok=False)
    # Immutable private record allows exact replay even if generators evolve later.
    (destination / "case_private.json").write_text(json.dumps(case, indent=2))
    workspace = destination / "workspace"
    workspace.mkdir()
    for name, content in case["files"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe public filename")
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    prompt = case["instruction"] + (
        "\nWork in /workspace. Repair the submitted analysis.py and any needed local helpers. "
        "It must run as: python3 analysis.py INPUT.json OUTPUT.json. "
        "Your program will be evaluated on additional datasets drawn from the documented contract. "
        "Do not hardcode the visible example. Python standard library is available; package installation is unnecessary. "
        "Preserve scientifically correct behavior where the starter is already valid. "
        "Each hidden replay allows 8 CPU seconds, 12 wall-clock seconds, 512 MiB address space, "
        "2 MB per file write and 1 MB JSON output. Workspace limit: 250 entries and 20 MB. "
        "Write a concise findings.md describing your decisions and what remains uncertain.\n")
    (destination / "prompt.txt").write_text(prompt)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="vals-repair-agent-") as temporary:
        agent_home = Path(temporary)
        cmd = model_command(backend, model, effort, workspace.resolve(), agent_home, budget)
        with (destination / "trace.jsonl").open("w") as out, (destination / "stderr.txt").open("w") as err:
            status, returncode = _execute(cmd, prompt, out, err, timeout)
    actual_models, tools_used, final, responded = set(), [], {}, False
    for line in (destination / "trace.jsonl").read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        message = event.get("message", {})
        ids = model_response_ids([message.get("model"), event.get("model")])
        actual_models.update(ids)
        if ids:
            responded = True
        blocks = message.get("content", [])
        for block in blocks if isinstance(blocks, list) else []:
            if block.get("type") == "tool_use":
                tools_used.append(block.get("name"))
        item = event.get("item", {})
        if backend == "codex" and item.get("type") in {"agent_message", "reasoning", "command_execution"}:
            responded = True
            tools_used.append(item.get("type"))
        if event.get("type") in {"result", "turn.completed"}:
            final = event
    try:
        replay = evaluate_program(workspace, case["hidden"], compare)
    except ValueError:
        replay = {"passed": False, "passed_fixtures": 0, "total_fixtures": len(case["hidden"]), "error": "invalid_artifact"}
    result = {"id": case["id"], "family": case["family"], "seed": case["seed"], "variant": case["variant"],
        "backend": backend, "requested_model": model, "observed_model_ids": sorted(actual_models),
        "model_id_note": "CLI request is pinned; an empty observed list means the CLI did not emit a response model ID",
        "effort": effort, "status": status, "returncode": returncode, "model_responded": responded,
        "classification": classify_trial(status, responded, replay["passed"]),
        "elapsed_seconds": round(time.monotonic() - started, 2), "tools_used": tools_used,
        "usage": final.get("usage"), "usage_estimate_usd": final.get("total_cost_usd"),
        "agent_error": final.get("is_error"), "replay": replay,
        "evidence": "local isolated tool-agent pilot; not a Valkyrie execution"}
    if final.get("is_error"):
        result["classification"] = "agent_runtime_error"
    errors = {check.get("error") for check in replay.get("checks", [])}
    if status == "completed" and responded and not final.get("is_error"):
        if errors & {"replay_timeout", "replay_resource_limit"}:
            result["classification"] = "resource_limit"
        elif replay.get("error") == "invalid_artifact" or errors & {"missing_or_invalid_output", "invalid_output"}:
            result["classification"] = "invalid_submission"
        elif "program_error" in errors:
            result["classification"] = "candidate_execution_failure"
    if replay.get("infrastructure_error"):
        result["classification"] = "infrastructure_error"
    (destination / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in ["id", "backend", "classification", "elapsed_seconds", "replay"]}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--families", nargs="+", default=["endpoint", "claims", "geometry"])
    parser.add_argument("--variant", choices=["flawed", "valid"], default="flawed")
    parser.add_argument("--backends", nargs="+", choices=["claude", "codex"], default=["claude", "codex"])
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--budget", type=float, default=5)
    args = parser.parse_args()
    if args.timeout > 600 or not 0 < args.budget <= 5:
        raise ValueError("Pilot bounds exceeded")
    args.out.mkdir(parents=True, exist_ok=False)
    models = {"claude": "claude-opus-5-5", "codex": "gpt-6-astra"}
    sources = list((ROOT / "repair_evals").glob("*.py")) + [Path(__file__), ROOT / "prototype_evals/pilot.py"]
    manifest = {"seed": args.seed, "variant": args.variant, "families": args.families,
        "models": {b: models[b] for b in args.backends}, "effort": "high", "timeout_seconds": args.timeout,
        "claude_usage_cap_per_task_usd": args.budget, "codex_billing": "existing ChatGPT login; no API billing configured",
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "hosted_valkyrie_run": False, "data": "synthetic counterfactual fixtures only"}
    manifest["replay_limits"] = {"wall_seconds": 12, "cpu_seconds": 8,
        "memory_mib": 512, "output_bytes": 1_000_000, "file_write_bytes": 2_000_000,
        "workspace_entries": 250, "workspace_bytes": 20_000_000}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    snapshot = args.out / "source_snapshot"
    for path in sources:
        target = snapshot / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    # Import after the snapshot, and reject drift around case construction.
    from repair_evals import make_case
    cases = []
    for family in args.families:
        if family == "integrated":
            from repair_evals.integrated import make_case as make_integrated
            cases.append(make_integrated(args.seed, args.variant))
        else:
            cases.append(make_case(family, args.seed, args.variant))
    def source_drift():
        return [str(p.relative_to(ROOT)) for p in sources
                if hashlib.sha256(p.read_bytes()).hexdigest() != manifest["source_sha256"][str(p.relative_to(ROOT))]]
    if source_drift():
        raise RuntimeError("Source changed while freezing cases; use a new run directory")
    results = []
    for case in cases:
        if (args.out / "STOP").exists() or (ROOT / "STOP").exists() or (Path.home() / ".gstack/projects/vals-research-evals/autoresearch/STOP").exists():
            break
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run_one, case, args.out / (case["id"] + "-" + backend), backend,
                                   models[backend], "high", args.timeout, args.budget) for backend in args.backends]
            for future in futures:
                results.append(future.result())
        drift = source_drift()
        if drift:
            manifest["invalidated_by_source_changes"] = drift
            for row in results:
                row["classification"] = "invalidated_source_change"
        (args.out / "summary.json").write_text(json.dumps({"manifest": manifest, "results": results}, indent=2))
        if drift:
            break
        if any(r["classification"] == "infrastructure_error" for r in results[-len(args.backends):]):
            break
    print("Pilot complete", flush=True)


if __name__ == "__main__":
    main()
