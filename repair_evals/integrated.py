"""Frozen synthetic manuscript audit with connected endpoint/lineage/statistics.

No patient data or model calls. The private reference composes the independently
tested endpoint and claims routines; public scripts contain no fixture answers.
"""
import copy
import hashlib
import inspect
import json
import math
import random
import re

from .cases import COMMON, PROTOCOLS, SCHEMAS, _endpoint_input
from .reference import endpoint, claims, _auc


def resolve_identity(identity):
    graph = {}
    for left, right in identity['links']:
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set()).add(left)
    mapping = {}
    for canonical in identity['canonical_subjects']:
        pending = [canonical]
        visited = set()
        while pending:
            token = pending.pop()
            if token in visited:
                continue
            visited.add(token)
            pending.extend(graph.get(token, set()) - visited)
        for token in visited:
            mapping[token] = canonical
    return mapping


def ancestor_nodes(root, artifacts):
    pending, visited = [root], set()
    while pending:
        key = pending.pop()
        if key in visited:
            continue
        visited.add(key)
        pending.extend(artifacts[key]['parents'])
    return [artifacts[key] for key in sorted(visited)]


def audit(data):
    cohort = endpoint(data['clinical'])
    identities = resolve_identity(data['identity'])
    artifacts = {item['artifact_id']: item for item in data['artifacts']}
    selected = {row['participant_id']: row for row in cohort['cohort']}
    lock = data['plan']['evaluation_lock_day']
    planned = {h['run_id'] for h in data['plan']['hypotheses']}
    normalized, provenance = [], []
    for run in sorted(data['runs'], key=lambda r: r['run_id']):
        if run['run_id'] not in planned:
            continue
        lineage = ancestor_nodes(run['artifact_id'], artifacts)
        uses = {'fit_model': set(), 'fit_transform': set(), 'select': set()}
        for item in lineage:
            if item['operation'] in uses:
                uses[item['operation']].update(identities[p] for p in item['subjects'])
        predictions, prediction_ids = [], []
        for pid, member in sorted(selected.items()):
            candidates = [p for p in run['predictions']
                          if identities[p['subject_id']] == pid and p['scan_id'] == member['scan_id']
                          and p['exported_day'] <= lock]
            chosen = max(candidates, key=lambda p: (p['exported_day'], p['revision'], p['row_id']))
            predictions.append({'row_id': chosen['row_id'], 'participant_id': pid, 'visit_day': 0,
                                'label': member['label'], 'probability': chosen['probability']})
            prediction_ids.append(chosen['row_id'])
        effective_day = max([run['freeze_day']] + [node['available_day'] for node in lineage])
        split = 'evaluation' if any(node['operation'] == 'select' and node['selection_split'] != 'development'
                                    for node in lineage) else 'development'
        nulls = []
        if {p['label'] for p in predictions} == {0, 1} and run['probability_for_class'] in (0, 1) and all(
                isinstance(p['probability'], (int, float)) and not isinstance(p['probability'], bool)
                and math.isfinite(p['probability']) and 0 <= p['probability'] <= 1 for p in predictions):
            n_positive = sum(p['label'] for p in predictions)
            for order in data['plan']['null_orders']:
                projected = [pid for pid in order if pid in selected]
                positive = set(projected[:n_positive])
                nulls.append(_auc([(int(p['participant_id'] in positive), p['probability']
                                   if run['probability_for_class'] == 1 else 1 - p['probability'])
                                  for p in predictions]))
        normalized.append({'run_id': run['run_id'], 'probability_for_class': run['probability_for_class'],
                           'freeze_day': effective_day, 'selection_split': split,
                           'fit_subjects': sorted(uses['fit_model']),
                           'transform_fit_subjects': sorted(uses['fit_transform']),
                           'selection_subjects': sorted(uses['select']),
                           'predictions': predictions, 'null_auroc': nulls})
        provenance.append({'run_id': run['run_id'], 'ancestor_artifacts': sorted(n['artifact_id'] for n in lineage),
                           'effective_freeze_day': effective_day, 'selection_split': split,
                           'fit_subjects': sorted(uses['fit_model']),
                           'transform_fit_subjects': sorted(uses['fit_transform']),
                           'selection_subjects': sorted(uses['select']),
                           'prediction_rows': sorted(prediction_ids)})
    statistics = claims({'plan': data['plan'], 'runs': normalized})
    by_hypothesis = {row['hypothesis_id']: row for row in statistics['hypotheses']}
    reconciled = []
    for written in sorted(data['manuscript'], key=lambda r: r['hypothesis_id']):
        actual = by_hypothesis[written['hypothesis_id']]
        agrees = ((written['auroc'] is None and actual['auroc'] is None) or
                  (written['auroc'] is not None and actual['auroc'] is not None and
                   math.isclose(written['auroc'], actual['auroc'], rel_tol=1e-7, abs_tol=1e-8)))
        agrees = agrees and written['n_patients'] == actual['n_patients'] and written['reject'] is actual['reject']
        reconciled.append({'hypothesis_id': written['hypothesis_id'], 'status': 'consistent' if agrees else 'revise'})
    return {'cohort': cohort, 'provenance': provenance, 'statistics': statistics, 'manuscript': reconciled}


def reference(case_input):
    return audit(case_input)


PROTOCOL = """# Frozen manuscript audit protocol

Determine which manuscript statements remain consistent with the study's
reported pathogenic alteration endpoint and held-out confirmatory analysis.
This is an available-artifact reproducibility audit, not a clinical classifier
training exercise. All data are invented. The study endpoint and statistical
procedure below are normative. Neither cached labels nor manuscript statistics
are authoritative observations.

## Connected analysis

1. Construct the endpoint cohort from clinical using the endpoint protocol
below. Clinical participant_id is the canonical biological person identifier.
2. identity.links are unordered undirected equivalence links. Take their full
transitive closure. Each component contains exactly one identity.canonical_subjects
entry; canonical subjects without links map to themselves. All subject tokens
used in runs and artifacts resolve. The identity registry also includes people
outside the clinical cohort, such as training and development participants.
3. Each planned run points to artifact_id. Include that artifact and every
recursive parent in its provenance. The graph is acyclic and references exist.
An artifact's subjects list describes its own operation, not a cumulative log.
fit_model subjects entered model fitting, fit_transform subjects entered learned
preprocessing, and select subjects entered model/threshold selection. Resolve
all to canonical people. source records and apply records describe storage or
inference recipients and do not themselves mean fitting or selection. Their
parents remain dependencies. The run's effective freeze day is the maximum of
its freeze_day and available_day across its entire ancestor closure. Its
selection split is evaluation if any ancestor select operation has a split
other than development; otherwise development (including no select operation).
4. For each person in the endpoint cohort, use prediction exports with both
matching canonical identity and the cohort's selected scan_id, exported no
later than plan.evaluation_lock_day. Choose maximum (exported_day, revision,
row_id). These are complete replacement prediction exports. Every present run
has at least one matching available export per selected person. The current
label comes from the reconstructed endpoint, not prediction.cached_label.
The latter is a historical display field. probability_for_class is authoritative.
5. Evaluate one row per selected person. For purposes of the statistical
procedure, the normalized visit_day is 0; row_id is the selected export ID.
Use the canonical fitting/selection sets and effective freeze/split from step3.
Unplanned runs are ignored. Planned absent runs remain in the hypothesis family.
6. The Monte Carlo null is supplied as plan.null_orders: independently sampled
uniform random permutations of ALL clinical participant IDs, generated before
any analysis. For each draw, first project that order to the reconstructed
cohort. If k selected people have label1, assign permuted label1 to the first k
people in the projected order, zero to the rest. Pair those permuted labels
with each selected person's fixed positive-class probability and calculate
AUROC. Do not resample rows or use excluded participants to consume the k
positive slots. Use these null AUROCs in the statistical rule below. A run with
invalid probabilities or a single-class cohort remains ineligible and needs no
null computation. null_orders is nonempty, and each contains every clinical
participant exactly once. The procedure tests conditional exchangeability for
this synthetic experiment; it is not evidence of external clinical validity.
7. Reconcile each manuscript row with its current hypothesis result. status is
consistent iff n_patients and reject agree exactly and auroc is either null in
both or numerically equal (relative tolerance1e-7, absolute tolerance1e-8).
Otherwise status is revise. A statistically unsupported claim can be consistent
if the manuscript accurately reports it as unsupported. Do not manufacture a
positive finding or treat every manuscript statement as erroneous.

## Endpoint procedure
""" + PROTOCOLS['endpoint'] + "\n## Statistical procedure\n" + PROTOCOLS['claims']

SCHEMA = """# Input and output dictionary

Input keys: clinical, identity, artifacts, plan, runs, manuscript. Clinical is
exactly the endpoint input described below. identity has canonical_subjects
(unique strings) and links (two-string arrays). artifacts has unique artifact_id,
parents (artifact IDs), operation (source, apply, fit_model, fit_transform,
select), subjects (identity tokens), available_day (integer), selection_split
(development/evaluation for select; null otherwise). All dates share one timeline.

plan has alpha, evaluation_lock_day, hypotheses (unique hypothesis_id and unique
run_id pairs), null_orders. Clinical as_of_day equals evaluation_lock_day. runs
has unique run_id, artifact_id, freeze_day, probability_for_class, predictions.
Each prediction has unique row_id within the run, subject_id (identity token),
scan_id, exported_day, revision, probability (finite number or null), cached_label
(historical 0/1). Supplied scan IDs exist in clinical.scans. manuscript has one
row per planned hypothesis: hypothesis_id, n_patients, auroc (finite number or
null), reject (boolean). Inputs and nested tables are unordered except null_orders
whose within-draw sequence is mathematically meaningful.

Output keys exactly cohort, provenance, statistics, manuscript.
cohort is the endpoint output below. statistics is the claims output below.
provenance has one row per PRESENT PLANNED run, sorted by run_id, with exactly
run_id, ancestor_artifacts, effective_freeze_day, selection_split, fit_subjects,
transform_fit_subjects, selection_subjects, prediction_rows. All ID lists are
sorted unique strings except prediction_rows is sorted selected row IDs (one
per selected person). No records for absent/unplanned runs.
manuscript is sorted by hypothesis_id, with exactly hypothesis_id and status
(consistent or revise). Output finite numeric values or prescribed nulls.
The same contract applies to valid and flawed starter variants.

## Endpoint field definitions
""" + SCHEMAS['endpoint'] + "\n## Normalized statistical field definitions\n" + SCHEMAS['claims']


def _input(seed):
    rng = random.Random(seed)
    original = _endpoint_input(seed)
    clinical = {'protocol': copy.deepcopy(original['protocol']), 'participants': [], 'specimens': [], 'scans': [], 'reports': []}
    for replica in range(rng.choice([2, 3, 4])):
        chunk = copy.deepcopy(original)
        for table in ('participants','specimens','scans','reports'):
            for row in chunk[table]:
                for field in ('participant_id','sample_id','scan_id','report_id'):
                    if field in row:
                        row[field] += '-rep' + str(replica)
            clinical[table].extend(chunk[table])
    people = [p['participant_id'] for p in clinical['participants']]
    canonical = people + ['train-' + str(seed), 'dev-' + str(seed)]
    aliases = {pid: 'opaque-' + hashlib.sha256((pid+str(seed)).encode()).hexdigest()[:10] for pid in canonical}
    links = []
    for pid in canonical:
        bridge = 'bridge-' + aliases[pid]
        links.extend([[pid, bridge], [bridge, aliases[pid]]])
    rng.shuffle(links)
    truth = endpoint(clinical)
    labels = {row['participant_id']: row['label'] for row in truth['cohort']}
    lock = clinical['protocol']['as_of_day']
    result = {'clinical': clinical, 'identity': {'canonical_subjects': canonical, 'links': links},
              'artifacts': [], 'plan': {'alpha': .05, 'evaluation_lock_day': lock, 'hypotheses': [], 'null_orders': []},
              'runs': [], 'manuscript': []}
    for i in range(249):
        order = people[:]
        rng.shuffle(order)
        result['plan']['null_orders'].append(order)
    source = {'artifact_id': 'source-' + str(seed), 'parents': [], 'operation': 'source',
              'subjects': [aliases[p] for p in people], 'available_day': 1, 'selection_split': None}
    result['artifacts'].append(source)
    for scenario in range(8):
        rid = 'run-' + hashlib.sha256(f'{seed}-{scenario}'.encode()).hexdigest()[:8]
        hid = 'hyp-' + rid[4:]
        result['plan']['hypotheses'].append({'hypothesis_id': hid, 'run_id': rid})
        result['manuscript'].append({'hypothesis_id': hid, 'n_patients': len(labels), 'auroc': 1., 'reject': True})
        if scenario == 7:
            continue
        transform = {'artifact_id': rid+'-transform', 'parents': [source['artifact_id']], 'operation': 'fit_transform',
                     'subjects': [aliases[canonical[-2]]], 'available_day': 5, 'selection_split': None}
        bridge = {'artifact_id': rid+'-state', 'parents': [transform['artifact_id']], 'operation': 'apply',
                  'subjects': [aliases[p] for p in people], 'available_day': 6, 'selection_split': None}
        selector = {'artifact_id': rid+'-selection', 'parents': [bridge['artifact_id']], 'operation': 'select',
                    'subjects': [aliases[canonical[-1]]], 'available_day': 7, 'selection_split': 'development'}
        model = {'artifact_id': rid+'-model', 'parents': [selector['artifact_id']], 'operation': 'fit_model',
                 'subjects': [aliases[canonical[-2]]], 'available_day': 8, 'selection_split': None}
        if scenario == 3:
            transform['subjects'].append(aliases[next(iter(labels))])
        if scenario == 4:
            selector['selection_split'] = 'evaluation'
        if scenario == 5:
            transform['available_day'] = lock + 1
        if scenario == 6:
            transform['operation'] = 'apply'
            transform['subjects'] += [aliases[p] for p in labels]
        result['artifacts'].extend([transform, bridge, selector, model])
        predictions = []
        for scan in clinical['scans']:
            pid = scan['participant_id']
            true = labels.get(pid, rng.randrange(2))
            probability = rng.uniform(.8,.95) if true else rng.uniform(.05,.2)
            if scenario in (1,2):
                probability = 1 - probability
            ridx = 'pred-' + hashlib.sha256((rid+scan['scan_id']).encode()).hexdigest()[:12]
            row = {'row_id': ridx, 'subject_id': aliases[pid], 'scan_id': scan['scan_id'],
                   'exported_day': lock-2, 'revision': 2, 'probability': probability, 'cached_label': 1-true}
            predictions.extend([row, dict(row,row_id=ridx+'-old',exported_day=lock-5,revision=1,probability=1-probability),
                                dict(row,row_id=ridx+'-future',exported_day=lock+2,revision=3,probability=1-probability)])
        rng.shuffle(predictions)
        result['runs'].append({'run_id': rid, 'artifact_id': model['artifact_id'], 'freeze_day': 10,
                               'probability_for_class': 0 if scenario == 2 else 1, 'predictions': predictions})
    # Include truthful negative reporting as a control against blanket revision.
    provisional = audit(result)
    existing = {r['hypothesis_id']: r for r in provisional['statistics']['hypotheses']}
    for index, statement in enumerate(result['manuscript']):
        if index in (1,6,7):
            computed = existing[statement['hypothesis_id']]
            statement.update({key: computed[key] for key in ('n_patients','auroc','reject')})
    for name in ('artifacts','runs','manuscript'):
        rng.shuffle(result[name])
    for table in ('participants','specimens','scans','reports'):
        rng.shuffle(result['clinical'][table])
    return result


def _starter(variant):
    source = 'import json, math, re, sys\n\n' + '\n\n'.join(inspect.getsource(fn)
        for fn in (endpoint, _auc, claims, resolve_identity, ancestor_nodes, audit))
    if variant == 'flawed':
        replacements = [
            ("pending.extend(artifacts[key]['parents'])", "\n        if key == root:\n            pending.extend(artifacts[key]['parents'])"),
            ("chosen = max(candidates, key=lambda p: (p['exported_day'], p['revision'], p['row_id']))",
             "chosen = min(candidates, key=lambda p: (p['exported_day'], p['revision'], p['row_id']))"),
            ("'label': member['label'], 'probability': chosen['probability']", "'label': chosen['cached_label'], 'probability': chosen['probability']"),
            ("projected = [pid for pid in order if pid in selected]\n                positive = set(projected[:n_positive])",
             "projected = order[:n_positive]\n                positive = set(pid for pid in projected if pid in selected)"),
        ]
        # The first four defects interact across endpoint, provenance and null construction.
        for old, new in replacements:
            if source.count(old) != 1:
                raise RuntimeError('Re-audit integrated starter transformation')
            source = source.replace(old, new)
        # An empty positive permutation is assigned a conservative null value by this legacy exporter.
        source = source.replace("positive = set(pid for pid in projected if pid in selected)",
                                "positive = set(pid for pid in projected if pid in selected)\n                if not positive or len(positive) == len(predictions):\n                    nulls.append(1.)\n                    continue")
    source += '\nif __name__ == "__main__":\n    with open(sys.argv[1]) as handle:\n        data = json.load(handle)\n    with open(sys.argv[2], "w") as handle:\n        json.dump(audit(data), handle, allow_nan=False, indent=2)\n'
    return source


def make_case(seed, variant='flawed'):
    if variant not in ('flawed','valid'):
        raise ValueError('Unknown variant')
    visible = _input(seed)
    hidden = []
    for offset in (1001,2003,3007):
        value = _input(seed+offset)
        hidden.append({'input': value, 'expected': reference(value)})
    shuffled = copy.deepcopy(visible)
    for key in ('artifacts','runs','manuscript'):
        shuffled[key].reverse()
    shuffled['identity']['links'].reverse()
    for run in shuffled['runs']:
        run['predictions'].reverse()
    hidden.append({'input': shuffled, 'expected': reference(shuffled)})
    identifier = hashlib.sha256(json.dumps(['integrated-v1',seed,variant]).encode()).hexdigest()[:10]
    return {'id':'integrated-'+identifier, 'family':'integrated', 'seed':seed, 'variant':variant,
            'instruction':'Complete the manuscript reproducibility handoff in handoff.md. Audit the supplied analysis against the frozen protocol and data dictionary, producing a corrected or validated analysis.py that runs on new inputs. Write output.json for input.json and briefly document any changes. Do not assume the existing analysis or every manuscript statement is wrong.',
            'files': {'analysis.py':_starter(variant), 'input.json':json.dumps(visible,indent=2)+'\n',
                      'protocol.md':COMMON+'\n'+PROTOCOL, 'schema.md':SCHEMA,
                      'handoff.md':'# Manuscript handoff\n\nThe collaboration has supplied specimen reports, MRI metadata, saved prediction exports, an identity registry, model-artifact provenance, a frozen multiplicity plan, and draft manuscript statistics. Reproduce the reportable participant-level findings from these artifacts and identify which draft statements need revision. Preserve valid analyses and the prespecified question. Deliver one standalone standard-library program with the CLI `python analysis.py INPUT.json OUTPUT.json`, plus output.json and concise notes. No training, internet access, external data or new statistical plan is needed.\n'},
            'hidden':hidden}
