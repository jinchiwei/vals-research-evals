"""Explicitly delegated Opus 5.5 high-effort deck worker."""
import argparse
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--brief', type=Path, default=root / 'docs/deck-brief.md')
parser.add_argument('--out', type=Path, default=root / 'results/deck')
parser.add_argument('--log-prefix', choices=['agent', 'agent-finalize'], default='agent')
args = parser.parse_args()
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=True)
prompt = args.brief.read_text() + f'\nWrite only deck artifacts under {out}.\n'
command = ['claude', '-p', '--safe-mode', '--model', 'claude-opus-5-5', '--effort', 'high',
    '--permission-mode', 'dontAsk', '--allowedTools', 'Read,Write,Edit,Glob,Grep,Bash',
    '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--no-session-persistence',
    '--max-budget-usd', '10', '--output-format', 'stream-json', '--verbose']
with (out/f'{args.log_prefix}-trace.jsonl').open('w') as stdout, (out/f'{args.log_prefix}-stderr.txt').open('w') as stderr:
    result = subprocess.run(command, input=prompt, cwd=root, text=True, stdout=stdout,
                            stderr=stderr, timeout=900)
print('Deck worker exit code:', result.returncode)
raise SystemExit(result.returncode)
