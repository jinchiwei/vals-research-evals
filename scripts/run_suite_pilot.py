#!/usr/bin/env python3
"""Local pilot runner for exported suite tasks (not a hosted Valkyrie run).

    # one agent attempt + grading; results in exp/suite-pilots/<run-name>/<task-id>/<model>/
    ~/miniconda3/envs/vals-suite/bin/python scripts/run_suite_pilot.py run dist/suite-toy/toy-sphere-volume-0001 \
        --run-name 20261114-toy --model claude-opus-5-5 --effort high --time-limit 900 --budget 3

    # table of the seven reward keys + headline metric vs specialist for every task/model in a run
    ~/miniconda3/envs/vals-suite/bin/python scripts/run_suite_pilot.py summarize exp/suite-pilots/20261114-toy

See docs/research/suite/local-pilots.md.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suite.pilot import pilot  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run', help='run one agent once on one exported task, then grade it')
    run.add_argument('task_dir', type=Path)
    run.add_argument('--run-name', required=True)
    run.add_argument('--model', action='append', required=True,
                     help=f'repeatable; Claude: {", ".join(pilot.CLAUDE_MODELS)}')
    run.add_argument('--backend', choices=['claude', 'codex'], default='claude')
    run.add_argument('--allow-codex', action='store_true', help='required to run the Codex backend')
    run.add_argument('--effort', choices=pilot.EFFORTS, default='high')
    run.add_argument('--time-limit', type=float, default=900.0, help='agent wall-clock limit in seconds')
    run.add_argument('--budget', type=float, default=3.0, help='--max-budget-usd for Claude (cap 5)')
    run.add_argument('--out-root', type=Path, default=pilot.DEFAULT_OUT)
    run.add_argument('--egress', choices=['proxy', 'open'], default='proxy',
                     help='proxy: own netns + allowlist proxy (default); open: host network')
    run.add_argument('--auth', choices=['oauth', 'api-key', 'none'], default='oauth')
    run.add_argument('--agent-bin', type=Path, help='agent executable (default: resolved from PATH)')
    run.add_argument('--runtime-prefix', type=Path,
                     help='use this Python prefix instead of vals-suite-rt-<family> (tests only)')
    run.add_argument('--no-build-env', action='store_true', help='fail instead of creating the conda env')
    run.add_argument('--scratch', type=Path, help='where live workspaces go (default: system temp, Linux fs)')
    summ = sub.add_parser('summarize', help='table per task and model for a run directory')
    summ.add_argument('run_dir', type=Path)
    args = parser.parse_args(argv)

    if args.command == 'summarize':
        text, _ = pilot.summarize(args.run_dir)
        print(text)
        return 0
    status = 0
    for model in args.model:
        if args.backend == 'claude' and model not in pilot.CLAUDE_MODELS:
            print(f'warning: {model} is not one of {pilot.CLAUDE_MODELS}', file=sys.stderr)
        run_dir, record = pilot.run_pilot(
            args.task_dir, run_name=args.run_name, model=model, backend=args.backend, effort=args.effort,
            time_limit_sec=args.time_limit, budget_usd=args.budget, out_root=args.out_root, agent_bin=args.agent_bin,
            runtime_prefix=args.runtime_prefix, build_env=not args.no_build_env, auth=args.auth, egress=args.egress,
            scratch=args.scratch, allow_codex=args.allow_codex)
        agent = record.get('agent', {})
        print(json.dumps({'run_dir': str(run_dir), 'status': agent.get('status'), 'exit_code': agent.get('exit_code'),
                          'wall_seconds': agent.get('wall_seconds'), 'cost_usd': record.get('cost_usd'),
                          'turns': record.get('num_turns'), 'models_reported': record.get('models_reported'),
                          'reward': record.get('reward')}, indent=2))
        if record.get('reward') is None:
            status = 1
    return status


if __name__ == '__main__':
    sys.exit(main())
