"""Read-only Valkyrie readiness check; never reads or prints credential values.

Run with .venv-valkyrie/bin/python. No login, uploads, installs, or jobs occur.
An optional --tasks folder is checked using the installed SDK's packaging rules;
that check is explicitly not an end-to-end execution claim.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess


def version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def command_ok(argv: list[str]) -> bool:
    try:
        return subprocess.run(
            argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=8, check=False,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path)
    args = parser.parse_args()
    docker = shutil.which("docker")
    docker_usable = bool(docker and command_ok([docker, "info", "--format", "{{.ServerVersion}}"]))
    compose_usable = bool(docker and command_ok([docker, "compose", "version"]))
    env_names = (
        "VALKYRIE_API_KEY", "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET",
        "DAYTONA_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY",
    )
    # Presence only. Do not load login/session files or call SDK auth resolution.
    sessions = Path.home() / ".config/valkyrie/sessions"
    result = {
        "check_type": "read_only_readiness_not_execution",
        "versions": {name: version(name) for name in ("valkyrie-cli", "valkyrie-sdk")},
        "commands_present": {name: bool(shutil.which(name)) for name in ("docker", "podman", "uv", "make")},
        "docker_daemon_usable": docker_usable,
        "docker_compose_usable": compose_usable,
        "local_tracker_runtime_prerequisites_present": bool(
            docker_usable and compose_usable and shutil.which("uv") and shutil.which("make")
        ),
        "credential_environment_presence_only": {name: bool(os.environ.get(name)) for name in env_names},
        "valkyrie_sessions_directory_present_not_validated": sessions.is_dir(),
        "hosted_auth_and_provider_readiness": "not_verified_offline",
        "local_tracker_execution": "not_attempted",
        "hosted_execution": "not_attempted",
        "task_packaging": None,
    }
    if args.tasks is not None:
        if not args.tasks.is_dir():
            parser.error("--tasks must name an existing task parent directory")
        try:
            from valkyrie.sdk.task_archive import find_task_folders, task_problems
        except ImportError:
            parser.error("Use .venv-valkyrie/bin/python; valkyrie-sdk is required")
        rows = [
            {"task": name, "problems": task_problems(folder)}
            for name, folder in find_task_folders(args.tasks).items()
        ]
        result["task_packaging"] = {
            "task_count": len(rows), "tasks": rows,
            "passes_packaging_checks": bool(rows) and all(not row["problems"] for row in rows),
            "execution_verified": False,
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
