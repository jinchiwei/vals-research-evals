import argparse
import json
from pathlib import Path
from .cases import generate
from .experiment import smoke_loop
from .export import export_case


def main():
    parser = argparse.ArgumentParser(description='Three synthetic research-agent eval prototypes')
    sub = parser.add_subparsers(dest='command', required=True)
    smoke = sub.add_parser('smoke', help='Bounded scripted-control loop, no model calls')
    smoke.add_argument('--out', type=Path, required=True)
    export = sub.add_parser('export', help='Write Harbor/Valkyrie task folders')
    export.add_argument('--out', type=Path, required=True)
    export.add_argument('--seeds', type=int, nargs='+', default=[11, 23, 37])
    export.add_argument('--workflow', action='store_true')
    pilot = sub.add_parser('pilot', help='Live Claude tool-agent pilot using existing login and bubblewrap')
    pilot.add_argument('--out', type=Path, required=True)
    pilot.add_argument('--seed', type=int, default=11)
    pilot.add_argument('--model', default='claude-opus-5-5')
    pilot.add_argument('--effort', default='high')
    pilot.add_argument('--max-tasks', type=int, default=4)
    pilot.add_argument('--timeout', type=int, default=240)
    pilot.add_argument('--budget', type=float, default=3.0)
    pilot.add_argument('--family', choices=['audit', 'change', 'reports'])
    pilot.add_argument('--prompt-variant', choices=['base', 'audit-check'], default='base')
    pilot.add_argument('--workflow', action='store_true')
    args = parser.parse_args()
    if args.command == 'smoke':
        result = smoke_loop(args.out, [11, 23, 37], [101, 211, 307])
        print(json.dumps({k: v for k, v in result.items() if k != 'iterations'}, indent=2))
    elif args.command == 'export':
        args.out.mkdir(parents=True, exist_ok=False)
        count = 0
        for seed in args.seeds:
            for case in generate(seed):
                if args.workflow:
                    from .challenge import complicate
                    case = complicate(case)
                export_case(case, args.out)
                count += 1
        print(f'Exported {count} tasks to {args.out}')
    else:
        from .pilot import run_pilot
        options = vars(args)
        options.pop('command')
        run_pilot(**options)


if __name__ == '__main__':
    main()
