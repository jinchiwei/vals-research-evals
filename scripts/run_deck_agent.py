"""Explicitly delegated Opus 5.5 high-effort deck worker."""
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'results/deck'
out.mkdir(parents=True, exist_ok=True)
prompt = (root / 'docs/deck-brief.md').read_text()
agents = {'deck-builder': {'description': 'Build Jin-branded prototype comparison slides.',
    'prompt': 'Follow the assignment and the build-pptx skill. Write only deck artifacts under results/deck.',
    'model': 'claude-opus-5-5'}}
command = ['claude', '-p', '--model', 'claude-opus-5-5', '--effort', 'high',
    '--agent', 'deck-builder', '--agents', json.dumps(agents),
    '--permission-mode', 'dontAsk', '--allowedTools', 'Read,Write,Edit,Glob,Grep,Bash',
    '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--no-session-persistence',
    '--max-budget-usd', '10', '--output-format', 'stream-json', '--verbose']
with (out/'agent-trace.jsonl').open('w') as stdout, (out/'agent-stderr.txt').open('w') as stderr:
    result = subprocess.run(command, input=prompt, cwd=root, text=True, stdout=stdout,
                            stderr=stderr, timeout=900)
print('Deck worker exit code:', result.returncode)
raise SystemExit(result.returncode)
