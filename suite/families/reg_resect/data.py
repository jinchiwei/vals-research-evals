"""Stage RESECT (NIfTI release) into the reg_resect development / hidden split.

Usage:
    python -I -m suite.families.reg_resect.data RAW_NIFTI_DIR STAGED_DIR

RAW_NIFTI_DIR is .../RESECT/NIFTI from the NIRD archive (doi:10.11582/2017.00004).

Split rule, fixed before any agent or baseline result (DESIGN.md "Splits and selection"):
  1. Candidates: the 22 patients that have <Case>-MRI-beforeUS.tag (pre-resection iUS landmarks).
  2. Eligible: initial mean landmark error (no registration) > CLINICAL_THRESHOLD_MM (2.0 mm).
     A case whose initial error already meets the threshold would let a do-nothing pipeline pass.
  3. Eligible cases sorted by patient number, permuted with numpy default_rng(20261114);
     the first N_HIDDEN are hidden, the next N_DEV are development, the rest are an unused reserve.
  4. Case IDs are re-drawn (random hex tokens from the same generator) so the agent cannot map
     a case to its RESECT patient number; NIfTI `descrip`/`aux_file`/`db_name` text (which
     contains "CaseNN") is cleared. Voxel data, dtype and affine are unchanged.

Per staged case (file names are the task contract):
  mri_t1.nii.gz      contrast-enhanced T1w MRI (pre-operative)
  mri_flair.nii.gz   T2 FLAIR MRI (pre-operative), same world frame as T1 (landmarks were placed on FLAIR)
  us.nii.gz          3D intra-operative ultrasound, after dura opening, before resection
  landmarks_mri.csv  id,x,y,z  MRI landmarks, RAS world mm
  landmarks_us.csv   id,x,y,z  corresponding ultrasound landmarks (development cases; hidden: reference/ only)
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

from . import landmarks as lm

SEED = 20261114
CLINICAL_THRESHOLD_MM = 2.0
N_HIDDEN = 6
N_DEV = 4
IMAGE_FILES = {'mri_t1.nii.gz': 'MRI/{c}-T1.nii.gz', 'mri_flair.nii.gz': 'MRI/{c}-FLAIR.nii.gz',
               'us.nii.gz': 'US/{c}-US-before.nii.gz'}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def candidates(raw):
    tags = sorted(Path(raw).glob('Case*/Landmarks/Case*-MRI-beforeUS.tag'),
                  key=lambda p: int(re.search(r'Case(\d+)', p.name).group(1)))
    out = []
    for tag in tags:
        case = re.search(r'(Case\d+)', tag.name).group(1)
        mri, us = lm.read_tag(tag)
        err = np.linalg.norm(mri - us, axis=1)
        out.append({'patient': case, 'tag': str(tag.relative_to(raw)), 'n_landmarks': int(len(err)),
                    'initial_mtre_mm': float(err.mean()), 'initial_sd_mm': float(err.std(ddof=0))})
    return out


def make_split(cands):
    eligible = [c for c in cands if c['initial_mtre_mm'] > CLINICAL_THRESHOLD_MM]
    excluded = [c['patient'] for c in cands if c['initial_mtre_mm'] <= CLINICAL_THRESHOLD_MM]
    rng = np.random.default_rng(SEED)
    order = [eligible[i]['patient'] for i in rng.permutation(len(eligible))]
    tokens = []
    while len(tokens) < len(order):
        t = 'c' + ''.join(f'{v:x}' for v in rng.integers(0, 16, 5))
        if t not in tokens:
            tokens.append(t)
    hidden, dev = order[:N_HIDDEN], order[N_HIDDEN:N_HIDDEN + N_DEV]
    reserve = order[N_HIDDEN + N_DEV:]
    ids = dict(zip(order, tokens))
    return {'seed': SEED, 'rule': f'eligible = initial mTRE > {CLINICAL_THRESHOLD_MM} mm; '
                                  'numpy default_rng(seed).permutation over eligible sorted by patient number; '
                                  f'first {N_HIDDEN} hidden, next {N_DEV} development, rest reserve',
            'excluded_initial_below_threshold': excluded, 'eligible': [c['patient'] for c in eligible],
            'hidden': {p: ids[p] for p in hidden}, 'development': {p: ids[p] for p in dev},
            'reserve': {p: ids[p] for p in reserve}}


def _copy_nifti_clean(src, dst):
    import nibabel as nib
    img = nib.load(str(src))
    header = img.header.copy()
    for key in ('descrip', 'aux_file', 'db_name', 'intent_name'):
        if key in header:
            header[key] = b''
    out = nib.Nifti1Image(np.asanyarray(img.dataobj), img.affine, header)
    out.set_sform(img.get_sform(), code=int(img.header['sform_code']))
    out.set_qform(img.get_qform(), code=int(img.header['qform_code']))
    nib.save(out, str(dst))


def stage_case(raw, patient, dest_input, dest_reference):
    dest_input.mkdir(parents=True, exist_ok=True)
    dest_reference.mkdir(parents=True, exist_ok=True)
    for name, pattern in IMAGE_FILES.items():
        _copy_nifti_clean(Path(raw) / patient / pattern.format(c=patient), dest_input / name)
    mri, us = lm.read_tag(Path(raw) / patient / 'Landmarks' / f'{patient}-MRI-beforeUS.tag')
    ids = [f'L{i + 1:02d}' for i in range(len(mri))]
    lm.write_csv(dest_input / 'landmarks_mri.csv', ids, mri)
    lm.write_csv(dest_reference / 'landmarks_us.csv', ids, us)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    raw, staged = Path(argv[0]), Path(argv[1])
    cands = candidates(raw)
    split = make_split(cands)
    split['candidates'] = cands
    for patient, token in split['development'].items():
        d = staged / 'dev' / token
        stage_case(raw, patient, d, d)              # dev: inputs and reference side by side
    for patient, token in split['hidden'].items():
        d = staged / 'hidden' / token
        stage_case(raw, patient, d / 'input', d / 'reference')
    split['sha256'] = {str(p.relative_to(staged)): sha256(p) for p in sorted(staged.rglob('*'))
                       if p.is_file() and p.name != 'split.json'}
    (staged / 'split.json').write_text(json.dumps(split, indent=2) + '\n')
    print(json.dumps({k: split[k] for k in ('excluded_initial_below_threshold', 'hidden', 'development', 'reserve')},
                     indent=1))


if __name__ == '__main__':
    main()
