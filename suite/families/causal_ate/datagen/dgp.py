"""ACIC-2016-style data-generating process over real ICU covariates (verifier/data side only).

Never shipped to the agent: this file lives in a sub-package that the exporter does not vendor
(export.vendor_library copies only suite/families/causal_ate/*.py) and is not in environment/.

Design (docs/research/suite/causal_ate.md, after Dorie, Hill, Shalit, Scott and Cervone, Statistical
Science 2019;34(1):43-68, "Automated versus do-it-yourself methods for causal inference: lessons
learned from a data analysis competition", section 4.3 and appendix A.1). Seven two-level knobs:

  trt_nonlin   treatment assignment linear in the covariates, or with squares/cubes, two-way
               interactions and step functions
  out_nonlin   response surface linear, or with the same nonlinear terms plus an exponentiated term
  pct_treated  expected share treated 0.35 or 0.65
  overlap      full, or limited: a corner of covariate space (two covariates above their 80th
               percentile) is forced to propensity 0 (controls with no treated counterpart; the
               corner indicator is put in the response surface so it matters, as in ACIC 2016)
  alignment    low (25 %) or high (75 %) share of assignment terms that also enter the response surface
  heterogeneity none (constant effect) or high (effect varies with covariate terms; sd 0.5 outcome units)
  confounding  moderate or strong: sd of the true assignment logit 0.8 or 1.6

Propensities are capped at 0.95 so every treated unit has comparable controls (ACIC 2016 enforced
overlap for the treated). Estimand: SATT, the mean over treated units of E[Y(1)-Y(0) | X]
(the conditional SATT of ACIC 2016). Outcomes: Y = location + scale * (mu0(X) + Z*tau(X) + eps),
eps ~ N(0, 1), mu0 standardised to sd 1; location and scale vary per dataset so the outcome units
are arbitrary. The grader judges errors in units of the dataset's observed outcome sd.
"""
from dataclasses import dataclass, asdict
import itertools

import numpy as np
import pandas as pd

SEED = 20261114
N_PER_DATASET = 2000
LOG_COLUMNS = ('bun_first', 'creatinine_first', 'glucose_first', 'platelets_first', 'wbc_first', 'urine_total_ml')
KNOBS = ('trt_nonlin', 'out_nonlin', 'pct_treated', 'overlap', 'alignment', 'heterogeneity', 'confounding')


@dataclass(frozen=True)
class Setting:
    trt_nonlin: int
    out_nonlin: int
    pct_treated: float
    overlap: str
    alignment: float
    heterogeneity: int
    confounding: float


def settings_design():
    """16 settings: a 2^(7-3) fractional factorial (resolution IV) over the seven knobs.

    Base factors A,B,C,D = trt_nonlin, out_nonlin, pct_treated, overlap; generators
    E = ABC (alignment), F = BCD (heterogeneity), G = ACD (confounding).
    """
    out = []
    for a, b, c, d in itertools.product((-1, 1), repeat=4):
        e, f, g = a * b * c, b * c * d, a * c * d
        out.append(Setting(trt_nonlin=int(a > 0), out_nonlin=int(b > 0), pct_treated=0.65 if c > 0 else 0.35,
                           overlap='limited' if d > 0 else 'full', alignment=0.75 if e > 0 else 0.25,
                           heterogeneity=int(f > 0), confounding=1.6 if g > 0 else 0.8))
    return out


def _standardise(x):
    s = x.std()
    return (x - x.mean()) / (s if s > 0 else 1.0)


def covariate_matrix(df):
    """Numeric design used by the DGP only: log of skewed labs, one-hot ICU type, all standardised."""
    d = df.drop(columns=['record_id']).copy()
    for c in LOG_COLUMNS:
        d[c] = np.log1p(d[c].clip(lower=0))
    icu = d.pop('icu_type')
    for k in (2, 3, 4):
        d[f'icu{k}'] = (icu == k).astype(float)
    return np.column_stack([_standardise(d[c].to_numpy(float)) for c in d.columns]), list(d.columns)


def _term(rng, X, kind):
    """One basis term of the given kind, as (description, values) with values standardised."""
    p = X.shape[1]
    j, k = rng.choice(p, size=2, replace=False)
    if kind == 'linear':
        return (f'x{j}', X[:, j])
    if kind == 'square':
        return (f'x{j}^2', _standardise(X[:, j] ** 2))
    if kind == 'cube':
        return (f'x{j}^3', _standardise(np.clip(X[:, j], -4, 4) ** 3))
    if kind == 'interaction':
        return (f'x{j}*x{k}', _standardise(X[:, j] * X[:, k]))
    if kind == 'step':
        cut = rng.uniform(-1.0, 1.0)
        v = (X[:, j] > cut).astype(float)
        return (f'1[x{j}>{cut:.2f}]', _standardise(v))
    raise ValueError(kind)


NONLINEAR_KINDS = ('square', 'cube', 'interaction', 'step')


def _draw_terms(rng, X, n_terms, nonlinear):
    terms = []
    for i in range(n_terms):
        if nonlinear and i % 3 != 0:          # about two thirds nonlinear terms
            kind = NONLINEAR_KINDS[rng.integers(len(NONLINEAR_KINDS))]
        else:
            kind = 'linear'
        terms.append(_term(rng, X, kind))
    return terms


def _combine(rng, terms):
    if not terms:
        return np.zeros(0)
    coef = rng.normal(0, 1, len(terms)) * rng.choice((0.5, 1.0, 2.0), len(terms))
    return _standardise(sum(c * t for c, (_, t) in zip(coef, terms)))


def _linear_versions(terms, X):
    """For a linear response surface: the main effects of the variables in shared nonlinear terms."""
    out = []
    for name, _ in terms:
        for tok in name.replace('^2', '').replace('^3', '').replace('*', ' ').replace('1[', ' ').split():
            tok = tok.split('>')[0]
            if tok.startswith('x') and tok[1:].isdigit():
                j = int(tok[1:])
                out.append((f'x{j}', X[:, j]))
    return out


def generate(pool, setting, rng, n=N_PER_DATASET):
    """One dataset. Returns (data frame with covariates + z + y, true SATT, oracle diagnostics)."""
    rows = rng.choice(len(pool), size=n, replace=False)
    sample = pool.iloc[np.sort(rows)].reset_index(drop=True)
    X, _ = covariate_matrix(sample)

    # Assignment mechanism.
    t_terms = _draw_terms(rng, X, 8, setting.trt_nonlin)
    logit = setting.confounding * _combine(rng, t_terms)
    corner = np.zeros(n, bool)
    if setting.overlap == 'limited':
        j, k = rng.choice(X.shape[1], size=2, replace=False)
        corner = (X[:, j] > np.quantile(X[:, j], 0.8)) & (X[:, k] > np.quantile(X[:, k], 0.8))
        if corner.mean() < 0.02:              # binary columns can make a tiny corner; widen to one variable
            corner = X[:, j] > np.quantile(X[:, j], 0.85)
    lo, hi = -20.0, 20.0                      # intercept so that the expected share treated is pct_treated
    for _ in range(80):
        mid = (lo + hi) / 2
        e = np.minimum(1 / (1 + np.exp(-(logit + mid))), 0.95)
        e[corner] = 0.0
        lo, hi = (mid, hi) if e.mean() < setting.pct_treated else (lo, mid)
    z = rng.binomial(1, e)

    # Response surface.
    n_shared = int(round(setting.alignment * len(t_terms)))
    shared_idx = rng.choice(len(t_terms), size=n_shared, replace=False)
    shared = [t_terms[i] for i in shared_idx]
    if not setting.out_nonlin:
        shared = [t for t in shared if not any(s in t[0] for s in ('^', '*', '['))] + _linear_versions(
            [t for t in shared if any(s in t[0] for s in ('^', '*', '['))], X)
    fresh = _draw_terms(rng, X, max(2, 10 - len(shared)), setting.out_nonlin)
    o_terms = shared + fresh
    mu0 = _combine(rng, o_terms)
    if setting.out_nonlin:
        lin = _combine(rng, _draw_terms(rng, X, 3, False))
        mu0 = _standardise(mu0 + 0.5 * np.exp(np.clip(0.6 * lin, -3, 3)))
    if setting.overlap == 'limited':
        mu0 = _standardise(mu0 + 1.0 * corner)

    tau0 = rng.uniform(0.2, 0.8) * rng.choice((-1, 1), p=(0.2, 0.8))
    tau = np.full(n, tau0)
    if setting.heterogeneity:
        h_terms = [o_terms[i] for i in rng.choice(len(o_terms), size=2, replace=False)]
        h_terms += _draw_terms(rng, X, 1, setting.out_nonlin)
        tau = tau0 + 0.5 * _combine(rng, h_terms)

    eps = rng.normal(0, 1, n)
    location = float(rng.uniform(-50, 150))
    scale = float(np.exp(rng.uniform(np.log(0.5), np.log(40))))
    y = location + scale * (mu0 + z * tau + eps)
    satt = float(scale * tau[z == 1].mean())

    data = sample.drop(columns=['record_id']).copy()
    data.insert(0, 'z', z)
    data.insert(1, 'y', np.round(y, 6))
    diag = {'n': n, 'n_treated': int(z.sum()), 'share_treated': float(z.mean()), 'scale': scale,
            'location': location, 'tau0_scaled': float(scale * tau0), 'tau_sd_scaled': float(scale * tau.std()),
            'satt': satt, 'sate': float(scale * tau.mean()), 'sd_y': float(np.std(y, ddof=1)),
            'satt_over_sd_y': satt / float(np.std(y, ddof=1)), 'corner_share': float(corner.mean()),
            'max_e_treated': float(e[z == 1].max()), 'min_e_treated': float(e[z == 1].min()),
            'naive_dim': float(y[z == 1].mean() - y[z == 0].mean()),
            'setting': asdict(setting)}
    return data, satt, diag


def generate_split(pool, n_reps, seed_offset):
    """All datasets of one split: every setting x n_reps replications, in a shuffled order, with
    random 8-hex dataset ids. Returns list of (dataset_id, data, satt, diag)."""
    ss = np.random.SeedSequence([SEED, seed_offset])
    rng_ids = np.random.default_rng(ss.spawn(1)[0])
    settings = settings_design()
    jobs = [(s_i, r) for s_i in range(len(settings)) for r in range(n_reps)]
    children = ss.spawn(len(jobs) + 1)[1:]
    order = rng_ids.permutation(len(jobs))
    ids = set()
    out = []
    for pos in order:
        s_i, r = jobs[pos]
        rng = np.random.default_rng(children[pos])
        data, satt, diag = generate(pool, settings[s_i], rng)
        while True:
            did = 'd' + ''.join(rng_ids.choice(list('0123456789abcdef'), 7))
            if did not in ids:
                ids.add(did)
                break
        diag.update(setting_index=s_i, replication=r)
        out.append((did, data, satt, diag))
    return out
