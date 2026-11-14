"""Standalone HTML research report from recorded results; no server or dependencies."""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_evals.pilot import model_response_ids
rows, traces, total = [], [], 0.0
for directory in sorted((ROOT / 'results').glob('*')):
    manifest = directory / 'manifest.json'
    if not manifest.exists():
        continue
    meta = json.loads(manifest.read_text())
    for path in sorted(directory.glob('*/result.json')):
        result = json.loads(path.read_text())
        models = model_response_ids(result['actual_models'])
        live = bool(models)
        total += result.get('cost_usd') or 0
        label = 'Live tool agent' if live else 'Infrastructure failure; not scored as model evidence'
        score = f"{result['score']:.0%}" if live else '—'
        color = '#22b89c' if live and result['score'] == 1 else '#f2ae45'
        rows.append('<tr>' + ''.join(f'<td>{html.escape(str(value))}</td>' for value in [
            directory.name, result['family'], ', '.join(models) or 'No model response',
            score, label, f"{result['elapsed_seconds']:.1f}s"]) + '</tr>')
        relative = path.parent.relative_to(ROOT)
        errors = ', '.join(result['errors']) or 'All required answer fields correct.'
        traces.append(f'<details><summary style="border-color:{color}">{html.escape(directory.name)} / '
                      f'{html.escape(result["case"])} · {score}</summary><p>{html.escape(errors)}</p>'
                      f'<p>Tools: {html.escape(", ".join(result["tools_used"]))}</p>'
                      f'<a href="../{relative}/result.json">Result JSON</a> · '
                      f'<a href="../{relative}/workspace/analysis.py">Agent analysis</a> · '
                      f'<a href="../{relative}/trace.jsonl">Full trace</a></details>')
controls = json.loads((ROOT / 'results/20261113-controls-v1/summary.json').read_text())
bars = []
for i, iteration in enumerate(controls['iterations']):
    y = 40 + i * 54
    bars.append(f'<text x="0" y="{y+17}" fill="#cbd5e1">{iteration["strategy"]}</text>'
                f'<rect x="110" y="{y}" width="{iteration["score"]*440:.1f}" height="26" rx="4" fill="#38bdae"/>'
                f'<text x="570" y="{y+18}" fill="#e2e8f0">{iteration["score"]:.0%}</text>')
body = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Research Agent Evals · Prototype Results</title><style>
body{background:#0b1422;color:#e2e8f0;font:16px/1.6 system-ui,sans-serif;max-width:1200px;margin:48px auto;padding:0 24px}
h1{font-size:clamp(30px,5vw,52px);line-height:1.12;max-width:850px}h2{margin-top:44px}p{max-width:900px}
a{color:#67e8d0}small,.muted{color:#a8b7cb}.tag{color:#67e8d0;text-transform:uppercase;letter-spacing:.16em;font-size:12px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}.card{background:#142236;padding:22px;border-radius:12px}
.card h3{margin-top:0}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:12px;text-align:left;border-bottom:1px solid #304258}
.scroll{overflow-x:auto}details{background:#142236;border-radius:8px;margin:12px 0;padding:14px}summary{cursor:pointer;border-left:4px solid;padding-left:12px}
svg{max-width:100%;height:auto}.note{border-left:4px solid #f2ae45;padding:12px 20px;background:#1a2636}
</style><div class="tag">Vals hackathon preparation · November 13, 2026</div>
<h1>Can frontier agents do the research checks that matter?</h1>
<p>Three runnable synthetic benchmark candidates. The evaluated system is a frontier language-model agent with code and file tools.
The local reference scripts validate the graders; they are not the systems being benchmarked.</p>
<div class="cards"><div class="card"><h3>Would You Publish This?</h3><p>Audit image-predictor claims beyond acquisition protocol.
The workflow version adds cohort exclusions, repeat visits, duplicated exports and revised labels.</p></div>
<div class="card"><h3>Brain Change Detective</h3><p>Distinguish change from scanner offsets and measurement uncertainty.
The workflow version adds mixed units, age-dependent norms and multi-table reconstruction.</p></div>
<div class="card"><h3>Report Evidence Detective</h3><p>Track exam chronology, uncertainty and signed corrections.
The workflow version adds corrections that apply only to particular findings.</p></div></div>
<h2>Live frontier-agent experiments</h2><p>Preserved successes and failures from actual tool-agent calls. A perfect result means the tested task
did not expose a frontier failure. Tiny pilots are not broad capability estimates. Usage is the CLI's dollar estimate, not a billing assertion.</p>
'''
body += f'<p>Recorded estimated model usage: <strong>${total:.3f}</strong>.</p>'
body += '<div class="scroll"><table><thead><tr><th>Run</th><th>Family</th><th>Model</th><th>Reward</th><th>Evidence</th><th>Time</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'
body += '<h2>Scripted controls, separately</h2><p>Development loop: naive → adjusted → careful. Select on development seeds; evaluate selected control on held-out seeds once.</p>'
body += '<svg viewBox="0 0 650 220" role="img" aria-label="Scripted control development scores">' + ''.join(bars) + '</svg>'
body += '<h2>Inspect the evidence</h2>' + ''.join(traces)
body += '''<h2>Valkyrie status</h2><p>The official Valkyrie SDK validated and packaged the task folders.
Reference solutions and verifiers passed in isolated filesystem phases. Hosted Valkyrie/Modal execution has not run;
the event account and provider setup are still needed. No tasks have been uploaded.</p>
<p class="note">A submission candidate must demonstrate meaningful frontier-model errors with a defensible grader.
If these pilots remain solved, the correct conclusion is to revise the tasks or choose another benchmark, not present scripted-control failures as frontier failures.</p>
<h2>Limits and next experiment</h2><p>Synthetic data only. Seed variants share templates. Report evidence uses a narrow exact-sentence contract.
The grader checks output artifacts, not arbitrary program equivalence. Normalization and thresholds are synthetic test policies, not clinical recommendations.
Freeze a candidate before running untouched seeds. Record infrastructure failures separately. Confirm pre-event preparation rules with organizers.</p>
<p><a href="../README.md">Run instructions</a> · <a href="https://www.vals.ai/hackathon">Event requirements</a> ·
<a href="https://github.com/vals-ai/valkyrie">Valkyrie</a></p></html>'''
destination = ROOT / 'results/REPORT.html'
destination.write_text(body, encoding='utf-8')
print(destination)
