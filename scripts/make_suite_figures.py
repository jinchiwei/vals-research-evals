#!/usr/bin/env python3
"""Make the results figures for the clinical deliverables suite.

Reads, when present (a missing input is skipped with a message, never an error):
  docs/research/suite/task-manifest.json   specialist numbers and clinical thresholds per task
  docs/research/suite/pilot1-results.json  local pilot 1 (bubblewrap, not hosted)
  docs/research/suite/hosted-agents1.json  hosted Valkyrie agent runs on the v2 instructions
  docs/research/suite/hosted-agents2.json  hosted Valkyrie agent runs on the v3 instructions

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
        out[t['family']] = t
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
    ap.add_argument('--only', choices=[s[0] for s in SOURCES], action='append',
                    help='limit to one or more sources')
    args = ap.parse_args(argv)

    manifest = load_json(args.docs / 'task-manifest.json')
    if manifest is None:
        log('task-manifest.json is required for specialist numbers and thresholds; nothing written')
        return 1
    mf = manifest_by_family(manifest)
    written = []
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
