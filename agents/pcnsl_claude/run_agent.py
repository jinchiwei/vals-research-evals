"""Single-attempt Claude Code wrapper for the PCNSL Valkyrie tasks (stdlib only).

Two subcommands:

* ``check`` (the contract's ``install_cmd``): verifies an already-prepared runtime.
  It installs and downloads nothing.
* ``run`` (the contract's ``run_cmd``): starts the preinstalled Claude Code CLI once,
  with no shell and no retries. It keeps the stream-json log and writes ``run.json``
  with the CLI's real exit status and usage.

The API key passes through the environment only. It never goes in argv or in any file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Version whose --help surface was read when this wrapper was written (local native
# build, 2026-11-14). The image recipe pins the same npm version; see docs/research/pcnsl-agent.md.
PINNED_CLI_VERSION = "2.1.325"
DEFAULT_AGENT_ENV = Path("/opt/agent-env")
DEFAULT_BENCHMARK_VENV = Path("/opt/benchmark-venv")
DEFAULT_LOG_DIR = Path("/logs/pcnsl-claude")
# Places a global or user-level install would put `claude`, including the registry
# claude_code setup (~/.local/bin, symlinked into /usr/local/bin).
GLOBAL_BIN_DIRS = ("/usr/local/bin", "/usr/bin", "/bin", "/root/.local/bin", "~/.local/bin")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
MAX_BUDGET_CAP_USD = 5.0
TASK_TIME_LIMIT_SEC = 1800  # agent_timeout set by the task's task.toml
DEFAULT_TIMEOUT_SEC = 1740  # leaves 60 s to write run.json before the task limit
KILL_GRACE_SEC = 10
TIMEOUT_EXIT = 124
API_KEY_ENV = "ANTHROPIC_API_KEY"
_MODEL_RE = re.compile(r"^claude-[A-Za-z0-9.\-]+(\[1m\])?$")


class RuntimeCheckError(Exception):
    pass


def claude_path(agent_env: Path) -> Path:
    return agent_env / "bin" / "claude"


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def check_runtime(agent_env: Path, benchmark_venv: Path, global_dirs=GLOBAL_BIN_DIRS,
                  expected_version: str = PINNED_CLI_VERSION, python_prefix: str | None = None) -> dict:
    """Raise RuntimeCheckError unless the prepared environment-only runtime is present."""
    agent_root = agent_env.resolve()
    exe = claude_path(agent_env)
    if not exe.exists():
        raise RuntimeCheckError(f"missing Claude executable {exe}; build the image from agents/pcnsl_claude/image")
    real = exe.resolve()
    if not _inside(real, agent_root):
        raise RuntimeCheckError(f"{exe} resolves to {real}, outside {agent_root}; global installs are not allowed")
    if not os.access(real, os.X_OK):
        raise RuntimeCheckError(f"{real} is not executable")
    node = agent_env / "bin" / "node"
    if node.exists() and not _inside(node.resolve(), agent_root):
        raise RuntimeCheckError(f"{node} resolves outside {agent_root}")
    for d in global_dirs:
        candidate = Path(os.path.expanduser(d)) / "claude"
        if candidate.exists() or candidate.is_symlink():
            raise RuntimeCheckError(f"global Claude install found at {candidate}; refuse to run beside it")
    prefix = Path(python_prefix if python_prefix is not None else sys.prefix).resolve()
    if prefix != benchmark_venv.resolve():
        raise RuntimeCheckError(f"wrapper Python prefix {prefix} is not {benchmark_venv}")
    proc = subprocess.run([str(real), "--version"], capture_output=True, text=True, timeout=60,
                          env=_child_env(agent_env, benchmark_venv, home=None, api_key=None))
    if proc.returncode != 0:
        raise RuntimeCheckError(f"`claude --version` exited {proc.returncode}")
    version = proc.stdout.strip().split()[0] if proc.stdout.strip() else ""
    if version != expected_version:
        raise RuntimeCheckError(f"Claude Code {version or '?'} found; wrapper was checked against {expected_version}")
    return {"claude": str(real), "version": version, "python_prefix": str(prefix)}


def cli_model(model: str) -> str:
    """Map Valkyrie's ``anthropic/<id>`` (or a bare ``claude-*`` id) to the CLI's --model."""
    provider, sep, name = model.partition("/")
    if sep:
        if provider != "anthropic":
            raise ValueError(f"model {model!r}: this harness only calls Anthropic models")
        model = name
    if not _MODEL_RE.fullmatch(model):
        raise ValueError(f"model {model!r} is not a Claude model id")
    return model


def _child_env(agent_env: Path, benchmark_venv: Path, home: Path | None, api_key: str | None) -> dict:
    # A fixed allowlist: nothing else from the sandbox environment reaches the CLI.
    env = {
        "PATH": os.pathsep.join([str(agent_env / "bin"), str(benchmark_venv / "bin"), "/usr/bin", "/bin"]),
        "LANG": "C.UTF-8",
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_TELEMETRY": "1",
        "DISABLE_ERROR_REPORTING": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "PIP_NO_INDEX": "1",
    }
    if home is not None:
        env["HOME"] = str(home)
        env["CLAUDE_CONFIG_DIR"] = str(home / ".claude")
        env["TMPDIR"] = str(home / "tmp")
        # Claude Code refuses bypassPermissions as root unless it is told it is in a sandbox.
        env["IS_SANDBOX"] = "1"
    if api_key is not None:
        env[API_KEY_ENV] = api_key
    return env


def build_argv(exe: Path, model: str, effort: str, max_budget_usd: float) -> list[str]:
    return [
        str(exe), "--print",
        "--output-format", "stream-json", "--verbose",
        "--model", cli_model(model),
        "--effort", effort,
        "--max-budget-usd", f"{max_budget_usd:g}",
        "--permission-mode", "bypassPermissions",
        "--bare",                      # no hooks, plugins, CLAUDE.md discovery or auto-memory
        "--no-session-persistence",    # nothing kept for a later task
        "--strict-mcp-config",         # no MCP servers
        "--disallowed-tools", "WebFetch", "WebSearch",
    ]


def _result_event(stream_path: Path) -> dict | None:
    last = None
    try:
        with stream_path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict) and event.get("type") == "result":
                    last = event
    except OSError:
        return None
    return last


_RESULT_KEYS = ("subtype", "is_error", "num_turns", "total_cost_usd", "duration_ms",
                "duration_api_ms", "usage", "modelUsage", "session_id", "stop_reason")


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def _report_error(line: str) -> None:
    target = os.environ.get("VALKYRIE_ERROR_PATH")
    if target:
        try:
            Path(target).write_text(line[:2000] + "\n")
        except OSError:
            pass


def run(args: argparse.Namespace) -> int:
    log_dir: Path = args.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    meta_path = log_dir / "run.json"
    meta = {
        "harness": "pcnsl_claude", "task_id": args.task_id, "attempt": 1, "retries": 0,
        "model_requested": args.model, "effort": args.effort, "max_budget_usd": args.max_budget_usd,
        "max_turns": None, "max_turns_note": f"--max-turns not in Claude Code {PINNED_CLI_VERSION} --help; not enforced",
        "timeout_sec": args.timeout_sec, "status": "starting",
    }
    # One attempt per sandbox: an existing marker means something already started the CLI here.
    try:
        fd = os.open(log_dir / "attempt.lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        _report_error("AgentError: an attempt already ran in this sandbox; refusing to retry")
        return 3
    os.close(fd)

    def fail(status: str, message: str, code: int) -> int:
        meta.update(status=status, error=message, exit_code=None)
        _write_json(meta_path, meta)
        _report_error(f"AgentError: {message}")
        return code

    if not 0 < args.max_budget_usd <= MAX_BUDGET_CAP_USD:
        return fail("rejected", f"max_budget_usd must be in (0, {MAX_BUDGET_CAP_USD}]", 2)
    if not 0 < args.timeout_sec <= TASK_TIME_LIMIT_SEC:
        return fail("rejected", f"timeout_sec must be in (0, {TASK_TIME_LIMIT_SEC}]", 2)
    if args.effort not in EFFORTS:
        return fail("rejected", f"unknown effort {args.effort!r}", 2)
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        return fail("rejected", f"{API_KEY_ENV} is not set", 2)
    try:
        prompt = Path(args.problem_statement_path).read_text(encoding="utf-8")
        argv = build_argv(claude_path(args.agent_env), args.model, args.effort, args.max_budget_usd)
    except (OSError, ValueError) as exc:
        return fail("rejected", str(exc), 2)

    # Fresh, empty HOME per run, outside final_output so CLI config state is never carried.
    home = Path(tempfile.mkdtemp(prefix="pcnsl-claude-home-"))
    (home / "tmp").mkdir()
    env = _child_env(args.agent_env, args.benchmark_venv, home, api_key)
    stream_path, stderr_path = log_dir / "stream.jsonl", log_dir / "stderr.log"
    meta.update(argv=argv, cwd=os.getcwd(), status="running", started_at=time.time())
    _write_json(meta_path, meta)

    timed_out = False
    with stream_path.open("wb") as out, stderr_path.open("wb") as err:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=out, stderr=err, env=env,
                                start_new_session=True)  # own process group, so a timeout stops its children
        try:
            proc.stdin.write(prompt.encode("utf-8"))
            proc.stdin.close()
        except BrokenPipeError:
            pass
        try:
            code = proc.wait(timeout=args.timeout_sec)
        except subprocess.TimeoutExpired:
            timed_out = True
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(proc.pid, sig)
                except ProcessLookupError:
                    break
                try:
                    proc.wait(timeout=KILL_GRACE_SEC)
                    break
                except subprocess.TimeoutExpired:
                    continue
            code = proc.wait()

    result = _result_event(stream_path)
    meta.update(
        status="timeout" if timed_out else ("exited" if code == 0 else "failed"),
        exit_code=code, timed_out=timed_out, finished_at=time.time(),
        result={k: result.get(k) for k in _RESULT_KEYS if k in result} if result else None,
        result_event_found=result is not None,
    )
    meta["elapsed_sec"] = round(meta["finished_at"] - meta["started_at"], 3)
    _write_json(meta_path, meta)
    if timed_out:
        _report_error(f"AgentTimeout: Claude Code stopped after {args.timeout_sec}s")
        return TIMEOUT_EXIT
    if code != 0:
        _report_error(f"AgentError: Claude Code exited with code {code}")
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "run"):
        p = sub.add_parser(name)
        p.add_argument("--agent-env", type=Path, default=DEFAULT_AGENT_ENV)
        p.add_argument("--benchmark-venv", type=Path, default=DEFAULT_BENCHMARK_VENV)
        if name == "run":
            p.add_argument("problem_statement_path")
            p.add_argument("--task-id", required=True)
            p.add_argument("--model", required=True)
            p.add_argument("--effort", default="high")
            p.add_argument("--max-budget-usd", type=float, default=MAX_BUDGET_CAP_USD)
            p.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)
            p.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    args = parser.parse_args(argv)
    if args.command == "check":
        try:
            info = check_runtime(args.agent_env, args.benchmark_venv)
        except (RuntimeCheckError, OSError, subprocess.SubprocessError) as exc:
            print(f"runtime check failed: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(info))
        return 0
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
