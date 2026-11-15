#!/usr/bin/env python3
"""Make the results figures for the clinical deliverables suite.

Reads, when present (a missing input is skipped with a message, never an error):
  docs/research/suite/task-manifest.json   specialist numbers and clinical thresholds per task
  docs/research/suite/pilot1-results.json  local pilot 1 (bubblewrap, not hosted)
  docs/research/suite/hosted-agents1.json  hosted Valkyrie agent runs on the v2 instructions
  docs/research/suite/hosted-agents2.json  hosted Valkyrie agent runs on the v3 instructions
  Round 3 (round3-prereg.md), written as docs/figures/suite/round3_*.{png,svg}:
  docs/research/suite/hosted-agents3.json        R: 3 attempts per task and model (run 2 + 2 repeats)
  docs/research/suite/hosted-keepworking1.json   K: fetal head keep-working variant (with R rows)
  docs/research/suite/hosted-clockcheck1.json    K2: fetal head clock-check variant (skipped if absent)
  docs/research/suite/data/seg_vessel_per_image.csv, seg_vessel_summary.json   V: retinal vessels
  docs/research/suite/data/causal_ate_summary.json                             C: causal control
  docs/research/suite/data/report_label_summary.json                           T: report labels

Writes PNG and SVG files to docs/figures/suite/, one set per source. Sources are never pooled
in one panel: pilot 1, hosted run 1 and hosted run 2 used different sandboxes or instruction texts.

  <source>_headline.{png,svg}          (a) agent vs specialist on each task's headline clinical metric,
                                           with the clinical threshold drawn
  <source>_reward_keys.{png,svg}       (b) ran / valid / within_time / clinically_acceptable / reward
                                           per task and model, specialist rows from the manifest
  <source>_per_case_<family>.{png,svg} (c) per-case agent vs specialist for per-case families

No number is computed that is not in the inputs, except means and counts over per-case rows that
the inputs already contain. Every figure states its source file in its footer.

Run with the vals-suite env:
  ~/miniconda3/envs/vals-suite/bin/python scripts/make_suite_figures.py
  ~/miniconda3/envs/vals-suite/bin/python scripts/make_suite_figures.py --round3-only
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SUITE_DOCS = REPO / 'docs' / 'research' / 'suite'
OUT_DEFAULT = REPO / 'docs' / 'figures' / 'suite'

# Scored tasks in manifest order. Triage (excluded) and the toy smoke task are not plotted.
SCORED_ORDER = ['reg_resect', 'seg_spleen', 'measure_hc18', 'ecg_ptbxl', 'risk_icu']
FAMILY_TITLE = {
    'reg_resect': 'MRI to ultrasound registration',
    'seg_spleen': 'CT spleen mask and volume',
    'measure_hc18': 'Fetal head circumference',
    'ecg_ptbxl': '12-lead ECG classes',
    'risk_icu': 'ICU mortality risk',
}
# Number of gate parts for cohort families, used only when a source has no gate dict:
# ecg_ptbxl.md section 3 (three parts), risk_icu.md section 3 (four parts).
GATE_PARTS_FALLBACK = {'ecg_ptbxl': 3, 'risk_icu': 4}
# Family bar for measure_hc18 (measure_hc18.md, "Fixed rules"): >= 90 % of hidden images within 4.9 %.
HC18_FAMILY_BAR = 0.90
# Per-case clinical limits (task-manifest.json limits.clinical_threshold).
REG_TRE_LIMIT_MM = 2.0
SPLEEN_DICE_LIMIT = 0.94

REWARD_COLS = ['ran', 'valid', 'within_time', 'clinically_acceptable', 'reward']

# Reference categorical palette (dataviz skill, references/palette.md), light mode, fixed order.
# Slot 1 and 2 go to the first two models by fixed name order; the specialist is a neutral ink.
MODEL_SLOTS = ['#2a78d6', '#eb6834', '#1baf7a', '#6250d6']
SPECIALIST_COLOR = '#52514e'
INK = '#0b0b0b'
INK_2 = '#52514e'
GRID = '#e4e3df'
SURFACE = '#fcfcfb'
FIXED_MODEL_ORDER = ['claude-opus-5-5', 'claude-sonnet-5-5']

plt.rcParams.update({
    'font.size': 9,
    'axes.edgecolor': INK_2,
    'axes.labelcolor': INK,
    'axes.titlesize': 9.5,
    'axes.titleweight': 'bold',
    'xtick.color': INK_2,
    'ytick.color': INK_2,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'figure.facecolor': SURFACE,
    'axes.facecolor': SURFACE,
    'savefig.facecolor': SURFACE,
    'svg.fonttype': 'none',
    'svg.hashsalt': 'vals-suite',
})


def footer(fig, lines: list[str], size: float = 6.8) -> int:
    """Write wrapped footer lines at the bottom left; return the number of printed lines."""
    width = int(fig.get_figwidth() * 17.5 * 6.8 / size)
    wrapped = [w for ln in lines for w in textwrap.wrap(ln, width, break_on_hyphens=False)]
    fig.text(0.01, 0.005, '\n'.join(wrapped), fontsize=size, color=INK_2, va='bottom')
    return len(wrapped)


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def show(path: Path) -> Path:
    return path.relative_to(REPO) if path.is_relative_to(REPO) else path


def load_json(path: Path):
    if not path.is_file():
        log(f'skip: {show(path)} not found')
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log(f'skip: {show(path)} unreadable ({exc})')
        return None


def model_color(model: str, order: list[str]) -> str:
    return MODEL_SLOTS[order.index(model) % len(MODEL_SLOTS)]


def model_order(models: set[str]) -> list[str]:
    known = [m for m in FIXED_MODEL_ORDER if m in models]
    return known + sorted(m for m in models if m not in known)


def short_model(model: str) -> str:
    return model.split('/')[-1]


# ---------------------------------------------------------------------------------------------
# Normalising the three input schemas into one row per (task, model) attempt.
# ---------------------------------------------------------------------------------------------

def manifest_by_family(manifest) -> dict:
    out = {}
    for t in (manifest or {}).get('tasks', []):
        # First entry per family wins, so variant tasks of the same family added later
        # (for example the fetal head K and K2 versions) never replace the scored task.
        out.setdefault(t['family'], t)
    return out


def task_family(task_id: str, manifest_fam: dict) -> str | None:
    for fam, t in manifest_fam.items():
        if t['task_id'] == task_id:
            return fam
    for fam in SCORED_ORDER:  # fallback on the id prefix
        if task_id.startswith(fam.split('_')[0]):
            return fam
    return None


def parse_failure_mm(text: str | None) -> float | None:
    """|error| in mm from a verifier failure line, e.g. 'error +58.16 mm exceeds ...'."""
    if not text:
        return None
    m = re.search(r'error ([+-]?\d+(?:\.\d+)?) mm', text) or re.search(r'mean TRE (\d+(?:\.\d+)?) mm', text)
    return abs(float(m.group(1))) if m else None


def rows_from_pilot1(data, manifest_fam) -> list[dict]:
    rows = []
    for r in data.get('runs', []):
        fam = task_family(r['task_id'], manifest_fam)
        hr = r.get('headline_raw_metric') or {}
        cases = []
        for c in r.get('per_case', []):
            cases.append({
                'case': c['case'],
                'agent_raw': c.get('agent_error_mm'),
                'agent_pass': bool(c.get('agent_pass')),
                'agent_valid': bool(c.get('agent_valid')),
                'spec_raw': c.get('specialist_error_mm'),
                'spec_pass': bool(c.get('specialist_pass')),
            })
        rows.append({
            'family': fam, 'task': r['task_id'], 'model': short_model(r['model_requested']),
            'rewards': r.get('reward') or {}, 'agent_raw_mean': hr.get('agent_mean'),
            'agent_raw_n': hr.get('n_valid_cases'), 'per_case': cases,
            'gate': None, 'status': r.get('agent_status'),
        })
    return rows


def rows_from_hosted(data, manifest_fam) -> list[dict]:
    runs = data.get('runs') or {}
    rows = []
    for a in data.get('attempts', []):
        fam = task_family(a['task'], manifest_fam)
        model = (runs.get(a.get('model_label')) or {}).get('model') or a.get('model_reported') \
            or a.get('model_label', '?')
        cases = []
        for c in a.get('per_case') or []:
            raw = c.get('agent_raw')
            if raw is None and c.get('agent_valid'):
                raw = parse_failure_mm(c.get('agent_failure'))
            cases.append({
                'case': c['case'], 'agent_raw': raw,
                'agent_pass': bool(c.get('agent_acceptable')),
                'agent_valid': bool(c.get('agent_valid')),
                'spec_raw': c.get('specialist_raw'),
                'spec_pass': bool(c.get('specialist_acceptable')),
            })
        rows.append({
            'family': fam, 'task': a['task'], 'model': short_model(model),
            'rewards': a.get('rewards') or {}, 'agent_raw_mean': a.get('agent_raw_mean'),
            'agent_raw_n': a.get('agent_raw_recoverable_n'), 'per_case': cases,
            'gate': a.get('gate'), 'status': a.get('agent_caused_exit_reason') or a.get('status'),
        })
    return rows


# Raw per-case value keys in hosted-agents2.json gap.per_case, and the mean in agent_metrics.
HOSTED2_RAW = {
    'reg_resect': ('agent_mean_tre_mm', 'specialist_mean_tre_mm', 'mean_mean_tre_mm'),
    'seg_spleen': ('agent_dice', 'specialist_dice', 'mean_dice'),
    'measure_hc18': ('agent_abs_err_mm', 'specialist_abs_err_mm', 'mean_abs_err_mm'),
}


def rows_from_hosted2(data, manifest_fam) -> list[dict]:
    """hosted-agents2.json schema (suite-hosted-agents2/1): one attempt per task and model."""
    rows = []
    for a in data.get('attempts', []):
        fam = a.get('family') or task_family(a['task_id'], manifest_fam)
        am = a.get('agent_metrics') or {}
        keys = HOSTED2_RAW.get(fam)
        cases = []
        if keys:
            for c in (a.get('gap') or {}).get('per_case') or []:
                cases.append({
                    'case': c['case'], 'agent_raw': c.get(keys[0]),
                    'agent_pass': bool(c.get('agent_acceptable')),
                    'agent_valid': bool(c.get('agent_valid')),
                    'spec_raw': c.get(keys[1]),
                    'spec_pass': bool(c.get('specialist_acceptable')),
                })
        rows.append({
            'family': fam, 'task': a['task_id'], 'model': short_model(a['model']),
            'rewards': a.get('rewards') or {},
            'agent_raw_mean': am.get(keys[2]) if keys else None,
            'agent_raw_n': am.get('n_valid'), 'per_case': cases,
            'gate': am.get('gate'), 'status': a.get('agent_caused_exit_reason') or a.get('status'),
        })
    return rows


# ---------------------------------------------------------------------------------------------
# (a) headline metric per task
# ---------------------------------------------------------------------------------------------

def headline_spec(fam: str, t: dict) -> dict:
    """Specialist value and threshold for the panel, all from the manifest."""
    keys = t.get('specialist_reward_keys') or {}
    if fam == 'reg_resect':
        return dict(label='mean TRE (mm), lower is better', ylab='mean TRE (mm)',
                    spec=(t.get('specialist_headline') or {}).get('value'),
                    thr=REG_TRE_LIMIT_MM, thr_label='< 2.0 mm per case', lower=True)
    if fam == 'seg_spleen':
        return dict(label='mean Dice, invalid case = 0', ylab='mean Dice', spec=keys.get('quality'),
                    thr=SPLEEN_DICE_LIMIT, thr_label='Dice >= 0.94 per case', lower=False, ymax=1.0)
    if fam == 'measure_hc18':
        return dict(label='images within 4.9 % of reference', ylab='fraction within tolerance', spec=keys.get('clinically_acceptable'),
                    thr=HC18_FAMILY_BAR, thr_label='family bar 90 %', lower=False, ymax=1.0)
    gf = (t.get('gate_fraction') or {}).get('specialist')
    n = GATE_PARTS_FALLBACK[fam]
    return dict(label=f'gate parts met, of {n}', ylab='gate parts met', spec=None if gf is None else gf * n,
                thr=float(n), thr_label='all parts required', lower=False, ymax=float(n), parts=n)


def agent_headline(fam: str, row: dict, hs: dict):
    """(value, note) for one attempt; value None means nothing gradable."""
    r = row['rewards']
    if fam == 'reg_resect':
        if row['agent_raw_mean'] is None:
            return None, 'no valid output'
        return row['agent_raw_mean'], f"n = {row['agent_raw_n']} valid"
    if fam == 'seg_spleen':
        return r.get('quality'), None
    if fam == 'measure_hc18':
        return r.get('clinically_acceptable'), None
    gate = row.get('gate')
    if gate:
        return float(sum(bool(v) for v in gate.values())), None
    if r.get('ran') == 0:
        return None, 'no output'
    return None, 'gate not reported'


def fig_headline(rows, manifest_fam, source_label, source_file, out: Path, stem: str) -> list[Path]:
    fams = [f for f in SCORED_ORDER if f in manifest_fam]
    models = model_order({r['model'] for r in rows})
    present = [f for f in fams if any(r['family'] == f for r in rows)]
    if not present:
        log(f'{stem}: no scored task in this source')
        return []
    fig, axes = plt.subplots(1, len(present), figsize=(max(7.6, 2.4 * len(present) + 0.6), 3.7),
                             squeeze=False)
    for ax, fam in zip(axes[0], present):
        t = manifest_fam[fam]
        hs = headline_spec(fam, t)
        labels, values, colors, notes = [], [], [], []
        for m in models:
            row = next((r for r in rows if r['family'] == fam and r['model'] == m), None)
            if row is None:
                continue
            v, note = agent_headline(fam, row, hs)
            labels.append(m.replace('claude-', '').replace('-5-5', ' 5.5'))
            values.append(v)
            colors.append(model_color(m, models))
            notes.append(note)
        labels.append('specialist')
        values.append(hs['spec'])
        colors.append(SPECIALIST_COLOR)
        notes.append(None)
        xs = range(len(labels))
        finite = [v for v in values if v is not None] + [hs['thr']]
        ymax = hs.get('ymax') or max(finite) * 1.25
        for x, v, c, note in zip(xs, values, colors, notes):
            if v is None:
                ax.text(x, ymax * 0.06, note or 'n/a', rotation=90, ha='center', va='bottom',
                        fontsize=7.5, color=INK_2)
                continue
            ax.bar(x, v, width=0.62, color=c, edgecolor=SURFACE, linewidth=2)
            txt = f'{v:.2f}' if not hs.get('parts') else f'{int(round(v))}/{hs["parts"]}'
            ax.text(x, v + ymax * 0.015, txt, ha='center', va='bottom', fontsize=8, color=INK, zorder=6,
                    bbox=dict(boxstyle='square,pad=0.15', facecolor=SURFACE, edgecolor='none'))
            if note:
                ax.text(x, v + ymax * 0.09, note, ha='center', va='bottom', fontsize=7, color=INK_2)
        ax.axhline(hs['thr'], color=INK, linestyle=(0, (4, 3)), linewidth=1.2, zorder=1)
        ax.set_ylim(0, ymax * (1.18 if not hs.get('ymax') else 1.12))
        ax.set_xlim(-0.6, len(labels) - 0.4)
        ax.set_xticks(list(xs))
        ax.set_xticklabels(labels, rotation=25, ha='right')
        ax.set_title(FAMILY_TITLE[fam], loc='left', pad=27)
        ax.text(0, 1.02, f"{hs['label']}\ndashed line: {hs['thr_label']}", transform=ax.transAxes,
                fontsize=7.3, color=INK_2, va='bottom', ha='left')
        ax.set_ylabel(hs['ylab'], fontsize=8)
        ax.yaxis.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    fig.suptitle(f'Agent vs specialist on the same hidden cases\n{source_label}', x=0.01, ha='left',
                 fontsize=10.5, fontweight='bold', color=INK)
    n = footer(fig, [f'Source: {source_file}', 'Specialist values and thresholds: '
                     'docs/research/suite/task-manifest.json. One attempt per task and model.'])
    fig.tight_layout(rect=(0, 0.035 * n + 0.01, 1, 0.93))
    return save(fig, out, stem + '_headline')


# ---------------------------------------------------------------------------------------------
# (b) reward-key breakdown
# ---------------------------------------------------------------------------------------------

def fig_reward_keys(rows, manifest_fam, source_label, source_file, out: Path, stem: str) -> list[Path]:
    fams = [f for f in SCORED_ORDER if any(r['family'] == f for r in rows)]
    if not fams:
        return []
    models = model_order({r['model'] for r in rows})
    table, ylabels, is_spec = [], [], []
    for fam in fams:
        for m in models:
            row = next((r for r in rows if r['family'] == fam and r['model'] == m), None)
            if row is None:
                continue
            table.append([row['rewards'].get(k) for k in REWARD_COLS])
            ylabels.append(f"{fam}  ·  {m.replace('claude-', '')}")
            is_spec.append(False)
        sk = (manifest_fam.get(fam) or {}).get('specialist_reward_keys')
        if sk:
            table.append([sk.get(k) for k in REWARD_COLS])
            ylabels.append(f'{fam}  ·  specialist (stored)')
            is_spec.append(True)
    n = len(table)
    fig, ax = plt.subplots(figsize=(7.2, 0.34 * n + 1.5))
    cmap = plt.get_cmap('Blues')
    for i, vals in enumerate(table):
        for j, v in enumerate(vals):
            if v is None:
                face, txt, tcol = SURFACE, '–', INK_2
            else:
                face = cmap(0.08 + 0.72 * float(v))
                txt = f'{v:.2f}'
                tcol = '#ffffff' if v > 0.62 else INK
            ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor=face, edgecolor=SURFACE, linewidth=2))
            ax.text(j + 0.5, i + 0.5, txt, ha='center', va='center', fontsize=8, color=tcol,
                    fontstyle='italic' if is_spec[i] else 'normal')
    ax.set_xlim(0, len(REWARD_COLS))
    ax.set_ylim(n, 0)
    ax.set_xticks([j + 0.5 for j in range(len(REWARD_COLS))])
    ax.set_xticklabels(REWARD_COLS, fontsize=8)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.5 for i in range(n)])
    ax.set_yticklabels(ylabels, fontsize=8)
    for lab, spec in zip(ax.get_yticklabels(), is_spec):
        lab.set_color(INK_2 if spec else INK)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title(f'Reward keys per task and model\n{source_label}', loc='left', pad=22)
    n_ft = footer(fig, [f'Source: {source_file}. Specialist rows (grey labels, italic values): '
                        'docs/research/suite/task-manifest.json specialist_reward_keys. Values are '
                        'means over hidden cases (0 to 1); cohort tasks have one hidden run.'])
    fig.tight_layout(rect=(0, 0.012 * n_ft + 0.02, 1, 1))
    return save(fig, out, stem + '_reward_keys')


# ---------------------------------------------------------------------------------------------
# (c) per-case agent vs specialist
# ---------------------------------------------------------------------------------------------

def fig_per_case(rows, source_label, source_file, out: Path, stem: str) -> list[Path]:
    written = []
    models_all = model_order({r['model'] for r in rows})
    for fam in ('reg_resect', 'seg_spleen', 'measure_hc18'):
        frs = [r for r in rows if r['family'] == fam and r['per_case']]
        if not frs:
            continue
        no_output = [r['model'] for r in frs if not any(c['agent_raw'] is not None for c in r['per_case'])]
        plot_rows = [r for r in frs if r['model'] not in no_output]
        if fam == 'measure_hc18':
            written += _scatter_hc18(plot_rows, no_output, models_all, source_label, source_file, out, stem)
        else:
            written += _paired_dots(fam, frs, plot_rows, no_output, models_all, source_label,
                                    source_file, out, stem)
    return written


def _legend_handles(models, models_all, spec=True):
    h = [Line2D([], [], marker='o', linestyle='', markersize=7, color=model_color(m, models_all),
                label=m) for m in models]
    if spec:
        h.append(Line2D([], [], marker='D', linestyle='', markersize=6, color=SPECIALIST_COLOR,
                        label='specialist'))
    h.append(Line2D([], [], marker='o', linestyle='', markersize=7, markerfacecolor=SURFACE,
                    markeredgecolor=INK_2, label='hollow = not clinically acceptable'))
    return h


def _scatter_hc18(plot_rows, no_output, models_all, source_label, source_file, out, stem):
    if not plot_rows:
        return []
    fig, ax = plt.subplots(figsize=(5.6, 5.0))
    floor = 0.05
    lo, hi = floor, 1.0
    unplotted = {}
    for r in plot_rows:
        col = model_color(r['model'], models_all)
        xs_p, ys_p, xs_f, ys_f = [], [], [], []
        missing = 0
        for c in r['per_case']:
            if c['agent_raw'] is None or c['spec_raw'] is None:
                missing += 1
                continue
            x, y = max(c['spec_raw'], floor), max(c['agent_raw'], floor)
            hi = max(hi, x, y)
            (xs_p if c['agent_pass'] else xs_f).append(x)
            (ys_p if c['agent_pass'] else ys_f).append(y)
        unplotted[r['model']] = missing
        ax.scatter(xs_p, ys_p, s=26, color=col, edgecolor=SURFACE, linewidth=0.8, zorder=3)
        ax.scatter(xs_f, ys_f, s=34, facecolor=SURFACE, edgecolor=col, linewidth=1.6, zorder=4)
    hi *= 1.6
    ax.plot([lo, hi], [lo, hi], color=INK_2, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    ax.text(hi / 6, hi / 4.2, 'agent = specialist', rotation=45, fontsize=7, color=INK_2,
            ha='center', va='center')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel('specialist |HC error| (mm, log scale)')
    ax.set_ylabel('agent |HC error| (mm, log scale)')
    ax.grid(True, color=GRID, linewidth=0.6, which='major')
    ax.set_axisbelow(True)
    ax.set_title(f'Fetal head circumference, per hidden image\n{source_label}', loc='left')
    ax.legend(handles=_legend_handles([r['model'] for r in plot_rows], models_all, spec=False),
              fontsize=7.5, frameon=False, loc='lower right')
    notes = [f'Source: {source_file}. Points above the diagonal: agent error larger than specialist.',
             f'Errors below {floor} mm drawn at {floor} mm. The per-image limit is 4.9 % of the hidden '
             'reference HC, which is not reproduced, so no fixed line is drawn.']
    miss = {m: k for m, k in unplotted.items() if k}
    if miss:
        notes.append('Images with no recoverable agent error: ' +
                     ', '.join(f'{m} {k}' for m, k in miss.items()) + '.')
    if no_output:
        notes.append('No output, not plotted: ' + ', '.join(no_output) + '.')
    n_ft = footer(fig, notes)
    fig.tight_layout(rect=(0, 0.01 + 0.024 * n_ft, 1, 1))
    return save(fig, out, f'{stem}_per_case_measure_hc18')


def _paired_dots(fam, frs, plot_rows, no_output, models_all, source_label, source_file, out, stem):
    cases = []
    for r in frs:
        for c in r['per_case']:
            if c['case'] not in cases:
                cases.append(c['case'])
    spec = {}
    for r in frs:
        for c in r['per_case']:
            if c['spec_raw'] is not None:
                spec[c['case']] = (c['spec_raw'], c['spec_pass'])
    if not spec:
        return []
    if fam == 'reg_resect':
        unit, thr, thr_label = 'mean TRE (mm)', REG_TRE_LIMIT_MM, '2.0 mm limit'
        title = 'MRI to ultrasound registration, per hidden case'
    else:
        unit, thr, thr_label = 'Dice', SPLEEN_DICE_LIMIT, 'Dice 0.94 limit'
        title = 'CT spleen, per hidden case'
    fig, ax = plt.subplots(figsize=(6.4, 3.9))
    k = len(plot_rows)
    offsets = {r['model']: (i + 1) * 0.16 for i, r in enumerate(plot_rows)}
    for x, case in enumerate(cases):
        if case in spec:
            v, ok = spec[case]
            ax.scatter([x - 0.16], [v], marker='D', s=36, zorder=4,
                       facecolor=SPECIALIST_COLOR if ok else SURFACE, edgecolor=SPECIALIST_COLOR,
                       linewidth=1.5)
        for r in plot_rows:
            c = next((c for c in r['per_case'] if c['case'] == case), None)
            col = model_color(r['model'], models_all)
            xo = x - 0.16 + offsets[r['model']]
            if c is None or c['agent_raw'] is None:
                ax.text(xo, 0, '×', ha='center', va='bottom', color=col, fontsize=10, zorder=4)
                continue
            if case in spec:
                ax.plot([x - 0.16, xo], [spec[case][0], c['agent_raw']], color=GRID, linewidth=1.2, zorder=2)
            ax.scatter([xo], [c['agent_raw']], s=40, zorder=5,
                       facecolor=col if c['agent_pass'] else SURFACE, edgecolor=col, linewidth=1.6)
    ax.axhline(thr, color=INK, linestyle=(0, (4, 3)), linewidth=1.1)
    ax.set_xticks(range(len(cases)))
    ax.set_xticklabels(cases, fontsize=8)
    ax.set_xlim(-0.7, len(cases) - 0.3 + 0.16 * k)
    tops = [v for v, _ in spec.values()] + [c['agent_raw'] for r in plot_rows for c in r['per_case']
                                            if c['agent_raw'] is not None] + [thr]
    ax.set_ylim(0, max(tops) * 1.3)
    ax.set_ylabel(unit)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_title(f'{title}\n{source_label}', loc='left')
    handles = _legend_handles([r['model'] for r in plot_rows], models_all)
    handles.append(Line2D([], [], color=INK, linestyle=(0, (4, 3)), linewidth=1.1, label=thr_label))
    ax.legend(handles=handles, fontsize=7, frameon=False, loc='upper left', ncol=2)
    notes = [f'Source: {source_file}. × = invalid output for that case (no value).']
    if no_output:
        notes.append('No valid output on any case, not plotted: ' + ', '.join(no_output) + '.')
    n_ft = footer(fig, notes)
    fig.tight_layout(rect=(0, 0.01 + 0.032 * n_ft, 1, 1))
    return save(fig, out, f'{stem}_per_case_{fam}')


# ---------------------------------------------------------------------------------------------

def save(fig, out: Path, name: str) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / f'{name}.png', out / f'{name}.svg']
    fig.savefig(paths[0], dpi=200, metadata={'Software': None})
    fig.savefig(paths[1], metadata={'Date': None})
    plt.close(fig)
    return paths


# ---------------------------------------------------------------------------------------------
# Round 3 (round3-prereg.md): pooled repeats R, elicitation variants K and K2, new families
# V (seg_vessel), C (causal_ate) and T (label_ptbxl_reports). Every value is read from a tracked
# file under docs/research/suite/ (JSON or the vessel per-image CSV); nothing is typed in here.
# ---------------------------------------------------------------------------------------------

R3_FILES = {
    'R': 'hosted-agents3.json',
    'K': 'hosted-keepworking1.json',
    'K2': 'hosted-clockcheck1.json',
    'V_csv': 'data/seg_vessel_per_image.csv',
    'V': 'data/seg_vessel_summary.json',
    'C': 'data/causal_ate_summary.json',
    'T': 'data/report_label_summary.json',
}
R3_TASKS = ['reg_resect', 'seg_spleen', 'measure_hc18', 'ecg_ptbxl', 'risk_icu', 'seg_vessel']
R3_TITLE = dict(FAMILY_TITLE, seg_vessel='Retinal vessel mask', reg_resect='MRI to US registration')
R3_MODELS = ['claude-opus-5-5', 'claude-sonnet-5-5']
R3_LABEL = {'claude-opus-5-5': 'Opus 5.5', 'claude-sonnet-5-5': 'Sonnet 5.5'}
ARM_MARKER = {'R': 'o', 'K': 's', 'K2': '^'}
ARM_LABEL = {'R': 'R: unchanged task (suite/clinical-v1@2)',
             'K': 'K: + keep-working paragraph',
             'K2': 'K2: + keep-working and clock-check paragraphs'}


def _r3_model(m: str) -> str:
    return short_model(m or '')


def _r3_color(m: str) -> str:
    return MODEL_SLOTS[R3_MODELS.index(m)] if m in R3_MODELS else MODEL_SLOTS[2]


def _src(key: str) -> str:
    return f'docs/research/suite/{R3_FILES[key]}'


def load_vessel_csv(path: Path):
    import csv
    if not path.is_file():
        log(f'skip: {show(path)} not found')
        return None
    with path.open(newline='') as fh:
        return list(csv.DictReader(fh))


def load_k2_attempts(data) -> list[dict]:
    """Tolerant reader for hosted-clockcheck1.json (schema not fixed when this was written).

    Accepts a list under per_attempt / attempts / per_attempt_including_k_and_r; keeps rows whose
    arm is K2 (or that carry no arm); needs a model, a reward and a session fraction (or the
    agent seconds and the limit)."""
    if not data:
        return []
    rows = None
    for key in ('per_attempt', 'attempts', 'per_attempt_k2', 'k2_attempts'):
        if isinstance(data.get(key), list):
            rows = data[key]
            break
    if rows is None:
        log('skip K2: no attempt list found in hosted-clockcheck1.json')
        return []
    out = []
    for a in rows:
        arm = str(a.get('arm', 'K2')).upper()
        if arm not in ('K2', 'CLOCKCHECK', 'CLOCK-CHECK', 'C2'):
            continue
        rew = a.get('rewards', {}).get('reward') if isinstance(a.get('rewards'), dict) else a.get('reward')
        frac = a.get('session_fraction_used')
        if frac is None and a.get('agent_process_wall_s') and a.get('session_limit_s'):
            frac = a['agent_process_wall_s'] / a['session_limit_s']
        if rew is None or frac is None:
            continue
        out.append({'arm': 'K2', 'model': _r3_model(a.get('model')), 'reward': float(rew),
                    'frac': float(frac), 'attempt': a.get('attempt')})
    if not out:
        log('skip K2: hosted-clockcheck1.json has no usable K2 rows')
    return out


def fig_r3_pooled_headline(r3, vcsv, vsum, mf, out: Path) -> list[Path]:
    attempts = r3['per_attempt_including_run2']
    pooled = {(p['family'], _r3_model(p['model'])): p for p in r3['pooled_3_attempts']}
    fig, axes = plt.subplots(1, len(R3_TASKS), figsize=(13.2, 4.3), sharey=True)
    for ax, fam in zip(axes, R3_TASKS):
        xs = {m: i for i, m in enumerate(R3_MODELS)}
        xs['spec'] = len(R3_MODELS)
        if fam == 'seg_vessel':
            n_img = vsum['n_hidden']
            spec = vsum['specialist']['n_acceptable'] / n_img
            per_model = {_r3_model(a['model']): [a['reward']] for a in vsum['attempts']}
            gap_txt = {_r3_model(a['model']): f"gap shown in 0 of 1" if a['gap_verdict'].startswith('no')
                       else 'gap shown in 1 of 1' for a in vsum['attempts']}
            # cross-check the summary against the per-image CSV
            for m, vals in per_model.items():
                key = 'opus' if 'opus' in m else 'sonnet'
                n_ok = sum(int(r['acceptable']) for r in vcsv if r['system'] == key)
                if abs(n_ok / n_img - vals[0]) > 1e-9:
                    log(f'warning: vessel {m} summary reward {vals[0]} != CSV {n_ok}/{n_img}')
        else:
            spec = (mf.get(fam) or {}).get('specialist_reward_keys', {}).get('reward')
            per_model, gap_txt = {}, {}
            for m in R3_MODELS:
                vals = [a['rewards']['reward'] for a in attempts
                        if a['family'] == fam and _r3_model(a['model']) == m]
                per_model[m] = vals
                p = pooled.get((fam, m))
                if p:
                    gap_txt[m] = f"gap shown in {p['gap_shown_in']} of {p['n_attempts']}"
        for m in R3_MODELS:
            vals = per_model.get(m, [])
            k = len(vals)
            offs = [(-0.16 + 0.16 * i) if k == 3 else 0.0 for i in range(k)]
            ax.scatter([xs[m] + o for o in offs], vals, s=46, color=_r3_color(m), edgecolor=SURFACE,
                       linewidth=0.9, zorder=4)
            if vals:
                mean = sum(vals) / k
                ax.plot([xs[m] - 0.28, xs[m] + 0.28], [mean, mean], color=_r3_color(m), linewidth=1.6,
                        zorder=3)
        if spec is not None:
            ax.scatter([xs['spec']], [spec], marker='D', s=46, color=SPECIALIST_COLOR, zorder=4)
        if fam == 'measure_hc18':
            ax.axhline(HC18_FAMILY_BAR, color=INK, linestyle=(0, (4, 3)), linewidth=1.0, zorder=1)
            ax.text(2.45, HC18_FAMILY_BAR + 0.015, '90 % bar', fontsize=6.8, color=INK, ha='right', va='bottom')
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels([f"Opus\n{gap_txt.get('claude-opus-5-5', '').replace('gap shown in ', 'gap ')}",
                            f"Sonnet\n{gap_txt.get('claude-sonnet-5-5', '').replace('gap shown in ', 'gap ')}",
                            'spec.'], fontsize=7.6)
        ax.set_xlim(-0.55, 2.55)
        ax.set_ylim(-0.05, 1.08)
        n_att = 1 if fam == 'seg_vessel' else 3
        ax.set_title(f"{R3_TITLE[fam]}\n{n_att} attempt{'s' if n_att > 1 else ''} per model", loc='left',
                     fontsize=8.6)
        ax.yaxis.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    axes[0].set_ylabel('reward (fraction of hidden cases acceptable;\ncohort tasks 0 or 1)', fontsize=8)
    handles = [Line2D([], [], marker='o', linestyle='', markersize=6.5, color=_r3_color(m), label=f'{R3_LABEL[m]}, one dot per attempt')
               for m in R3_MODELS]
    handles += [Line2D([], [], color=INK_2, linewidth=1.6, label='mean of attempts'),
                Line2D([], [], marker='D', linestyle='', markersize=6, color=SPECIALIST_COLOR,
                       label='specialist, same hidden cases')]
    fig.legend(handles=handles, loc='upper right', ncol=4, fontsize=7.5, frameon=False,
               bbox_to_anchor=(0.995, 0.955))
    fig.suptitle('Agent vs specialist, pooled attempts per task and model (round 3)', x=0.01, ha='left',
                 fontsize=10.5, fontweight='bold', color=INK, y=0.985)
    n = footer(fig, [
        f"Sources: {_src('R')} (attempt 1 = hosted run 2, attempts 2-3 = round 3 repeats, all on suite/clinical-v1@2); "
        f"{_src('V')} and {_src('V_csv')} (suite/vessel-v1@1, one attempt per model). Specialist rewards: "
        "task-manifest.json (vessel: seg_vessel.md). y is the hosted reward: registration attempt Opus R3 has reward 0 "
        "because one case was invalid. Under each model, 'gap k of n' = gap shown against the specialist in k of n attempts (DESIGN.md rule, per attempt)."])
    fig.tight_layout(rect=(0, 0.02 + 0.035 * n, 1, 0.9))
    return save(fig, out, 'round3_pooled_headline')


def _session_rows(r3, kw, k2, vsum, csum, tsum) -> list[tuple]:
    """(group, model, fraction, label) for every attempt in round 3 and hosted run 2."""
    rows = []
    for fam in ['reg_resect', 'seg_spleen', 'measure_hc18', 'ecg_ptbxl', 'risk_icu']:
        for a in r3['per_attempt_including_run2']:
            if a['family'] == fam:
                rows.append((f'R · {R3_TITLE[fam]}', _r3_model(a['model']), a['session_fraction_used']))
    for a in kw['per_attempt']:
        if a['arm'] == 'K':
            rows.append(('K · Fetal head, keep-working', _r3_model(a['model']), a['session_fraction_used']))
    for a in k2:
        rows.append(('K2 · Fetal head, clock check', a['model'], a['frac']))
    for a in vsum['attempts']:
        rows.append(('V · Retinal vessel mask', _r3_model(a['model']), a['session_s'] / vsum['session_limit_s']))
    for a in csum['attempts']:
        rows.append(('C · Causal effect (control)', _r3_model(a['model']), a['session_s'] / csum['session_limit_s']))
    for a in tsum['rows']:
        if a.get('kind') == 'agent':
            rows.append(('T · Report labels (excluded)', _r3_model(a['model']), a['session_s'] / tsum['session_limit_s']))
    return rows


def fig_r3_session(r3, kw, k2, vsum, csum, tsum, out: Path) -> list[Path]:
    rows = _session_rows(r3, kw, k2, vsum, csum, tsum)
    groups = []
    for g, _, _ in rows:
        if g not in groups:
            groups.append(g)
    fig, ax = plt.subplots(figsize=(7.6, 0.36 * len(groups) * 2 + 1.7))
    ylab, yticks = [], []
    y = 0
    for g in groups:
        for m in R3_MODELS:
            vals = [f for gg, mm, f in rows if gg == g and mm == m]
            if not vals:
                continue
            ax.scatter(vals, [y] * len(vals), s=40, color=_r3_color(m), edgecolor=SURFACE, linewidth=0.8,
                       zorder=4)
            ax.text(1.02, y, f"{len(vals)}×, max {max(vals) * 100:.0f} %", va='center', fontsize=7,
                    color=INK_2)
            ylab.append(f"{g} · {R3_LABEL[m].split()[0]}")
            yticks.append(y)
            y += 1
        y += 0.5
    ax.axvline(1.0, color=INK, linewidth=1.0)
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylab, fontsize=7.6)
    ax.set_ylim(y - 0.4, -0.7)
    ax.set_xlim(0, 1.18)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(['0', '25 %', '50 %', '75 %', '100 %\n(session limit)'])
    ax.set_xlabel('fraction of the agent session used before the agent ended its own turn')
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_title('Session use per attempt, hosted run 2 and round 3', loc='left')
    srcs = [_src('R'), _src('K')] + ([_src('K2')] if k2 else []) + [_src('V'), _src('C'), _src('T')]
    notes = ['Sources: ' + ', '.join(srcs) + '. One dot per attempt. Session used = agent process time '
             '(V, C, T: session seconds as reported in each family document) over the task limit (30 to 60 min).',
             'No attempt reached its limit. Arms are separate task versions and are never pooled.']
    if not k2:
        notes.append('K2 (clock-check variant, hosted-clockcheck1.json) not available when this figure was made.')
    n = footer(fig, notes)
    fig.tight_layout(rect=(0, 0.012 * n + 0.03, 1, 1))
    return save(fig, out, 'round3_session_use')


def fig_r3_hc18_elicitation(kw, k2, out: Path) -> list[Path]:
    pts = [{'arm': a['arm'], 'model': _r3_model(a['model']), 'reward': a['rewards']['reward'],
            'frac': a['session_fraction_used']} for a in kw['per_attempt'] if a['arm'] in ('R', 'K')]
    pts += [{'arm': 'K2', 'model': a['model'], 'reward': a['reward'], 'frac': a['frac']} for a in k2]
    arms = [a for a in ('R', 'K', 'K2') if any(p['arm'] == a for p in pts)]
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    for p in pts:
        ax.scatter([p['frac']], [p['reward']], marker=ARM_MARKER[p['arm']], s=70,
                   facecolor=_r3_color(p['model']) if p['arm'] == 'R' else SURFACE,
                   edgecolor=_r3_color(p['model']), linewidth=1.8, zorder=4)
    for arm in arms:
        for m in R3_MODELS:
            v = [p for p in pts if p['arm'] == arm and p['model'] == m]
            if v:
                mx = sum(p['frac'] for p in v) / len(v)
                my = sum(p['reward'] for p in v) / len(v)
                ax.scatter([mx], [my], marker='+', s=90, color=_r3_color(m), linewidth=1.4, zorder=5)
    ax.axhline(HC18_FAMILY_BAR, color=INK, linestyle=(0, (4, 3)), linewidth=1.0)
    ax.text(0.99, HC18_FAMILY_BAR + 0.01, 'family bar: 90 % of images', ha='right', va='bottom', fontsize=7.2)
    ax.axhline(1.0, color=SPECIALIST_COLOR, linewidth=1.0)
    ax.text(0.99, 0.99, 'specialist: 83 of 83', ha='right', va='top', fontsize=7.2, color=SPECIALIST_COLOR)
    for p in pts:
        if p['arm'] == 'K2' and p['reward'] == 0:
            ax.annotate('reward 0: 2 hidden images over the\n10 s limit (time gate, not accuracy)',
                        (p['frac'], 0.0), xytext=(p['frac'] - 0.30, 0.30), fontsize=6.9, color=INK_2,
                        arrowprops=dict(arrowstyle='-', color=INK_2, linewidth=0.8))
    ax.set_xlim(0, 1.0)
    ax.set_ylim(-0.04, 1.04)
    ax.set_xlabel('fraction of the 45-minute session used')
    ax.set_ylabel('reward (fraction of 83 hidden images within 4.9 %)')
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    arm_names = ' and '.join([', '.join(arms[:-1]), arms[-1]]) if len(arms) > 1 else arms[0]
    ax.set_title(f'Fetal head circumference: instruction variants {arm_names}\n'
                 '(separate task versions, never pooled)', loc='left')
    handles = [Line2D([], [], marker='o', linestyle='', markersize=7, color=_r3_color(m), label=R3_LABEL[m])
               for m in R3_MODELS]
    handles += [Line2D([], [], marker=ARM_MARKER[a], linestyle='', markersize=7,
                       markerfacecolor=INK_2 if a == 'R' else SURFACE, markeredgecolor=INK_2,
                       label=ARM_LABEL[a]) for a in arms]
    handles.append(Line2D([], [], marker='+', linestyle='', markersize=8, color=INK_2, label='mean per arm and model'))
    ax.legend(handles=handles, fontsize=6.9, frameon=False, loc='lower left')
    notes = [f"Sources: {_src('K')} (arms R and K)" + (f", {_src('K2')} (arm K2)" if k2 else '') +
             '. One marker per attempt; 3 attempts per arm and model. Every attempt shows a gap against the specialist.']
    if not k2:
        notes.append('K2 not available when this figure was made (hosted-clockcheck1.json absent).')
    n = footer(fig, notes)
    fig.tight_layout(rect=(0, 0.012 + 0.03 * n, 1, 1))
    return save(fig, out, 'round3_hc18_elicitation')


def fig_r3_vessel(vcsv, out: Path) -> list[Path]:
    systems = [('specialist_unet', 'specialist (U-Net)', SPECIALIST_COLOR, 'D'),
               ('opus', 'Opus 5.5', MODEL_SLOTS[0], 'o'), ('sonnet', 'Sonnet 5.5', MODEL_SLOTS[1], 'o')]
    cases = []
    for r in vcsv:
        if r['case'] not in cases:
            cases.append(r['case'])
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.0))
    for ax, metric, bar, lab in [(axes[0], 'dice', 'dice_bar_2ndHO', 'Dice'),
                                 (axes[1], 'cldice', 'cldice_bar_2ndHO', 'clDice (centreline Dice)')]:
        for x, case in enumerate(cases):
            rs = {r['system']: r for r in vcsv if r['case'] == case}
            b = float(next(iter(rs.values()))[bar])
            ax.plot([x - 0.36, x + 0.36], [b, b], color=INK, linewidth=2.0, zorder=3)
            for i, (key, _, col, mk) in enumerate(systems):
                r = rs.get(key)
                if r is None:
                    continue
                ok = r['acceptable'] == '1'
                ax.scatter([x - 0.22 + 0.22 * i], [float(r[metric])], marker=mk, s=44, zorder=4,
                           facecolor=col if ok else SURFACE, edgecolor=col, linewidth=1.6)
        ax.set_xticks(range(len(cases)))
        ax.set_xticklabels(cases, rotation=35, ha='right', fontsize=7.5)
        ax.set_ylim(0.74, 0.91)
        ax.set_ylabel(lab)
        ax.yaxis.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.set_title(f'{lab} per hidden image', loc='left')
    handles = [Line2D([], [], marker=mk, linestyle='', markersize=7, color=col, label=name)
               for _, name, col, mk in systems]
    handles += [Line2D([], [], color=INK, linewidth=2.0, label="bar: second human observer's value on that image"),
                Line2D([], [], marker='o', linestyle='', markersize=7, markerfacecolor=SURFACE,
                       markeredgecolor=INK_2, label='hollow = image not acceptable (needs both Dice and clDice at or above the bar)')]
    fig.legend(handles=handles, loc='upper left', ncol=3, fontsize=7.2, frameon=False, bbox_to_anchor=(0.01, 0.93))
    fig.suptitle('Retinal vessel segmentation (CHASE_DB1): 8 hidden images, one attempt per model', x=0.01,
                 ha='left', fontsize=10.5, fontweight='bold', color=INK, y=0.99)
    n = footer(fig, [f"Source: {_src('V_csv')} (local regrade, matches the hosted keys). Acceptable images: specialist 6/8, "
                     'Opus 5.5 5/8, Sonnet 5.5 4/8. The Frangi filter comparator (0/8, mean Dice 0.47) is in the CSV '
                     'but not drawn, because it would compress the scale.'])
    fig.tight_layout(rect=(0, 0.02 + 0.03 * n, 1, 0.87))
    return save(fig, out, 'round3_vessel_per_image')


def fig_r3_causal(csum, out: Path) -> list[Path]:
    g = csum['gate']
    n = csum['n_hidden_datasets']
    items = []
    for c in csum['comparators']:
        items.append((c['name'].replace(' (specialist)', '\n(specialist)'), SPECIALIST_COLOR if 'specialist' in c['name'] else INK_2,
                      'D' if 'specialist' in c['name'] else 'x', c))
    for a in csum['attempts']:
        items.append((f"{R3_LABEL[_r3_model(a['model'])]} · attempt {a['attempt']}", _r3_color(_r3_model(a['model'])), 'o', a))
    panels = [('coverage of the true SATT', lambda d: d['coverage_n'] / n, g['coverage_min'], 'min 0.85', (0.3, 1.02)),
              ('RMSE (outcome sd units)', lambda d: d['rmse_sd'], g['rmse_max_sd'], 'max 0.10', (0, 0.2)),
              ('mean interval length (sd units)', lambda d: d['mean_length_sd'], g['mean_length_max_sd'], 'max 0.50', (0, 0.55))]
    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.9), sharey=True)
    ys = list(range(len(items)))
    for ax, (lab, fn, thr, thr_lab, xl) in zip(axes, panels):
        for y, (name, col, mk, d) in zip(ys, items):
            ax.scatter([fn(d)], [y], marker=mk, s=46, color=col, zorder=4, linewidth=1.6)
        ax.axvline(thr, color=INK, linestyle=(0, (4, 3)), linewidth=1.0)
        ax.text(thr, -0.9, f'gate: {thr_lab} ', fontsize=7, ha='right', va='bottom')
        ax.set_xlim(*xl)
        ax.set_title(lab, loc='left', fontsize=8.8)
        ax.xaxis.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    axes[0].set_yticks(ys)
    axes[0].set_yticklabels([i[0] for i in items], fontsize=7.6)
    axes[0].set_ylim(len(items) - 0.4, -1.1)
    fig.suptitle('Causal effect with a 95 % interval (48 hidden semi-synthetic datasets): a control family', x=0.01,
                 ha='left', fontsize=10.5, fontweight='bold', color=INK)
    k = footer(fig, [f"Source: {_src('C')} (from causal_ate.md). Gate: all four parts (coverage, RMSE, |bias| <= 0.05 sd, "
                     'length). The specialist and all six agent attempts meet every part; OLS and the naive comparator fail '
                     'coverage. Agents widened their intervals by a factor tuned on the development datasets.'])
    fig.tight_layout(rect=(0, 0.02 + 0.03 * k, 1, 0.94))
    return save(fig, out, 'round3_causal')


def fig_r3_report_label(tsum, out: Path) -> list[Path]:
    rows = tsum['rows']
    g = tsum['gate']

    def col(r):
        if r['kind'] == 'agent':
            return _r3_color(r['model'])
        return SPECIALIST_COLOR if r['kind'] == 'specialist' else INK_2

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.4), sharey=True, gridspec_kw={'width_ratios': [1.4, 1]})
    ys = list(range(len(rows)))
    ax = axes[0]
    for y, r in zip(ys, rows):
        lo, hi = r['macro_f1_ci95']
        ax.plot([lo, hi], [y, y], color=col(r), linewidth=2.0, zorder=3)
        ax.scatter([r['macro_f1']], [y], marker='D' if r['kind'] == 'specialist' else 'o', s=46, color=col(r), zorder=4)
        ax.text(r['macro_f1'], y - 0.17, f"{r['macro_f1']:.3f}", ha='center', va='bottom', fontsize=7.4)
    ax.axvline(g['macro_f1_min'], color=INK, linestyle=(0, (4, 3)), linewidth=1.0)
    ax.text(g['macro_f1_min'] - 0.002, -0.75, 'gate: macro F1 >= 0.80', fontsize=7, ha='right', va='bottom')
    ax.set_xlim(0.68, 0.86)
    ax.set_title('macro F1 over 5 classes, 95 % interval', loc='left', fontsize=8.8)
    ax = axes[1]
    for y, r in zip(ys, rows):
        ax.scatter([r['min_kappa']], [y], marker='D' if r['kind'] == 'specialist' else 'o', s=46, color=col(r), zorder=4)
        ax.text(r['min_kappa'], y - 0.17, f"{r['min_kappa']:.3f} ({r['min_kappa_class']})", ha='center', va='bottom', fontsize=7.4)
    ax.axvline(g['min_kappa_each_class'], color=INK, linestyle=(0, (4, 3)), linewidth=1.0)
    ax.text(g['min_kappa_each_class'] + 0.005, -0.75, 'gate: kappa >= 0.60 in every class', fontsize=7, ha='left', va='bottom')
    ax.set_xlim(0.40, 0.80)
    ax.set_title('lowest per-class Cohen kappa', loc='left', fontsize=8.8)
    for a in axes:
        a.xaxis.grid(True, color=GRID, linewidth=0.6)
        a.set_axisbelow(True)
    axes[0].set_yticks(ys)
    axes[0].set_yticklabels([r['name'] for r in rows], fontsize=7.8)
    axes[0].set_ylim(len(rows) - 0.5, -1.0)
    fig.suptitle('ECG report text to diagnostic classes (500 hidden PTB-XL reports): excluded from scoring; descriptive',
                 x=0.01, ha='left', fontsize=10.2, fontweight='bold', color=INK)
    k = footer(fig, [f"Source: {_src('T')} (from label_ptbxl_reports.md section 3). No labeller meets both gate parts, so "
                     'every reward is 0 and the family is not scored. Opus 5.5 minus specialist macro F1 +0.055 '
                     '(patient-paired 95 % CI +0.025 to +0.086). Both agents had a model label the reports through API '
                     'calls from inside the sandbox.'])
    fig.tight_layout(rect=(0, 0.02 + 0.035 * k, 1, 0.93))
    return save(fig, out, 'round3_report_label')


def make_round3(docs: Path, out: Path, mf: dict) -> list[Path]:
    r3 = load_json(docs / R3_FILES['R'])
    kw = load_json(docs / R3_FILES['K'])
    k2_path = docs / R3_FILES['K2']
    k2 = load_k2_attempts(load_json(k2_path)) if k2_path.is_file() else []
    if not k2_path.is_file():
        log(f'K2: {show(k2_path)} not found; K2 left out of round-3 figures')
    vcsv = load_vessel_csv(docs / R3_FILES['V_csv'])
    vsum = load_json(docs / R3_FILES['V'])
    csum = load_json(docs / R3_FILES['C'])
    tsum = load_json(docs / R3_FILES['T'])
    written = []
    if r3 and vcsv and vsum:
        written += fig_r3_pooled_headline(r3, vcsv, vsum, mf, out)
    if r3 and kw and vsum and csum and tsum:
        written += fig_r3_session(r3, kw, k2, vsum, csum, tsum, out)
    if kw:
        written += fig_r3_hc18_elicitation(kw, k2, out)
    if vcsv:
        written += fig_r3_vessel(vcsv, out)
    if csum:
        written += fig_r3_causal(csum, out)
    if tsum:
        written += fig_r3_report_label(tsum, out)
    m4 = load_json(docs / 'hosted-models4.json')
    if r3 and m4:
        written += fig_r4_hc18(r3, m4, out)
    return written


# ---------------------------------------------------------------------------------------------
# Round 4 (round4-prereg.md): six-model fetal head pass rate. Opus/Sonnet from hosted-agents3.json,
# Fable and the three Codex models from hosted-models4.json; nothing typed in here.
# ---------------------------------------------------------------------------------------------

R4_ROWS = [('claude-opus-5-5', 'Opus 5.5', 'R'), ('claude-sonnet-5-5', 'Sonnet 5.5', 'R'),
           ('claude-fable-5-2', 'Fable 5.2', 'M4'), ('gpt-6-astra', 'Astra (Codex)', 'M4'),
           ('gpt-6.1-sol', 'Sol (Codex)', 'M4'), ('gpt-6-luna', 'Luna (Codex)', 'M4')]


def fig_r4_hc18(r3, m4, out: Path) -> list[Path]:
    fam = 'measure_hc18'
    fig, ax = plt.subplots(figsize=(8.6, 3.6))
    n_rows = len(R4_ROWS)
    for i, (model, label, src) in enumerate(R4_ROWS):
        y = n_rows - 1 - i
        pool = r3['pooled_3_attempts'] if src == 'R' else m4['pooled']
        p = next((q for q in pool if q['model'] == model and q['family'] == fam), None)
        rewards = (p or {}).get('rewards') or []
        col = MODEL_SLOTS[i % len(MODEL_SLOTS)] if i < 4 else ['#b8487a', '#7a6a12'][i - 4]
        if rewards:
            ax.scatter(rewards, [y] * len(rewards), s=46, color=col, zorder=4)
            k, n = p['gap_shown_in'], p.get('n_graded', p.get('n_attempts', len(rewards)))
            ax.text(1.02, y, f'gap {k} of {n}', va='center', fontsize=8, color=INK)
        else:
            ax.text(0.42, y, 'not graded (OpenAI rate limit / quota)', va='center', fontsize=8,
                    color=INK_2, style='italic')
    ax.axvline(1.0, color=SPECIALIST_COLOR, linewidth=2.0, zorder=3)
    ax.axvline(HC18_FAMILY_BAR, color=INK_2, linewidth=1.0, linestyle='--', zorder=2)
    ax.text(1.0, n_rows - 0.35, 'specialist 83/83', ha='right', va='bottom', fontsize=7.5, color=SPECIALIST_COLOR)
    ax.text(HC18_FAMILY_BAR, n_rows - 0.35, '90 % bar', ha='right', va='bottom', fontsize=7.5, color=INK_2)
    ax.axhline(n_rows - 3.5, color=GRID, linewidth=1.2)
    ax.text(0.405, n_rows - 3.45, 'Codex CLI harness below this line: side by side, never pooled with Claude',
            va='bottom', fontsize=7.2, color=INK_2)
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels([r[1] for r in reversed(R4_ROWS)])
    ax.set_xlim(0.4, 1.12)
    ax.set_xticks([0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_ylim(-0.6, n_rows - 0.1)
    ax.set_xlabel('Fraction of 83 hidden images within 4.9 % (attempt reward)')
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    fig.suptitle('Fetal head circumference: every graded attempt of every model, against the specialist', x=0.01,
                 ha='left', fontsize=10.5, fontweight='bold', color=INK, y=0.99)
    n = footer(fig, ["Sources: docs/research/suite/hosted-agents3.json (Opus, Sonnet: R1-R3) and "
                     "docs/research/suite/hosted-models4.json (round 4, snapshot 06:15 EST). Hosted grades."])
    fig.tight_layout(rect=(0, 0.02 + 0.03 * n, 1, 0.94))
    return save(fig, out, 'round4_hc18_six_models')


SOURCES = [
    # stem, file, label, loader
    ('pilot1', 'pilot1-results.json', 'local pilot 1 (bubblewrap, v1 instructions)', rows_from_pilot1),
    ('hosted1', 'hosted-agents1.json', 'hosted run 1 (Valkyrie, v2 instructions)', rows_from_hosted),
    ('hosted2', 'hosted-agents2.json', 'hosted run 2 (Valkyrie, suite/clinical-v1@2, v3 instructions)',
     rows_from_hosted2),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--docs', type=Path, default=SUITE_DOCS, help='folder with the input JSON files')
    ap.add_argument('--out', type=Path, default=OUT_DEFAULT, help='output folder for PNG and SVG')
    ap.add_argument('--only', choices=[s[0] for s in SOURCES] + ['round3'], action='append',
                    help='limit to one or more sources (round3 = the round-3 figure set)')
    ap.add_argument('--round3-only', action='store_true', help='same as --only round3')
    args = ap.parse_args(argv)
    if args.round3_only:
        args.only = ['round3']

    manifest = load_json(args.docs / 'task-manifest.json')
    if manifest is None:
        log('task-manifest.json is required for specialist numbers and thresholds; nothing written')
        return 1
    mf = manifest_by_family(manifest)
    written = []
    if not args.only or 'round3' in args.only:
        written += make_round3(args.docs, args.out, mf)
    for stem, fname, label, loader in SOURCES:
        if args.only and stem not in args.only:
            continue
        data = load_json(args.docs / fname)
        if data is None:
            continue
        rows = [r for r in loader(data, mf) if r['family'] in SCORED_ORDER]
        if not rows:
            log(f'skip: {fname} has no attempts on scored tasks')
            continue
        src = f'docs/research/suite/{fname}'
        written += fig_headline(rows, mf, label, src, args.out, stem)
        written += fig_reward_keys(rows, mf, label, src, args.out, stem)
        written += fig_per_case(rows, label, src, args.out, stem)
    for p in written:
        print(show(p))
    if not written:
        log('no figures written')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
