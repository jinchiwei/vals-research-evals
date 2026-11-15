"""Read the PGUPharyngitis release (Shojaei et al., Sci Data 12:1418, 2025; figshare 10.6084/m9.figshare.28163513.v1).

The release holds excel.xlsx (one row per patient) and data_image_pharyngitis_nature/<patient_ID>/<patient_ID>.jpg.
There is no final-label column: each patient has 3 to 9 physician calls ("Bacterial" / "Non Bacterial") in
Diagnosis #1..#9, not always contiguous. We derive the reference label here and nowhere else:

    bacterial_fraction = (# "Bacterial" calls) / (# calls)
    label (primary)    = 1 if bacterial_fraction >= 0.5 else 0
    label_strict       = 1 if bacterial_fraction >  0.5 else 0   (sensitivity analysis)

Ties (2-2, 3-3) count as bacterial in the primary label: if at least half of the physicians judged the
throat bacterial, a triage tool should send the patient for a rapid antigen test. The paper says ties
were re-read by an extra physician, but 100 unresolved ties remain in the file (verified 2026-11-14).
"""
import struct
from pathlib import Path

SYMPTOMS = ('Feeling Cold', 'Sore Throat', 'Cephalalgia', 'Myalgia', 'Rhinorrhea', 'Diarrhea', 'Vomit', 'Cough',
            'Pyrexia', 'Rigors', 'Lethargy', 'Sputum', 'Abdominal Pain', 'Vertigo', 'Sternutation',
            'Eye Infection', 'Otalgia', 'Nasal Congestion', 'Asthma', 'Anorexia')
# Column names used in every file we write (snake_case, same order as SYMPTOMS).
SYMPTOM_COLUMNS = tuple(s.lower().replace(' ', '_') for s in SYMPTOMS)
DIAGNOSIS_COLUMNS = tuple(f'Diagnosis #{i}' for i in range(1, 10))
BACTERIAL, NONBACTERIAL = 'Bacterial', 'Non Bacterial'
AGE_BANDS = (('child_lt15', 0, 15), ('adult_ge15', 15, 200))


def age_band(age):
    for name, lo, hi in AGE_BANDS:
        if lo <= age < hi:
            return name
    raise ValueError(f'age {age} outside bands')


def load_table(xlsx_path):
    """Return a DataFrame indexed by patient_ID with derived vote counts and labels (pandas + openpyxl)."""
    import pandas as pd
    d = pd.read_excel(xlsx_path)
    d = d.drop(columns=[c for c in d.columns if str(c).startswith('Unnamed')])
    expected = {'patient_ID', 'Age', 'Gender', *SYMPTOMS, *DIAGNOSIS_COLUMNS}
    if set(d.columns) != expected:
        raise ValueError(f'unexpected columns: {sorted(set(d.columns) ^ expected)}')
    if d['patient_ID'].duplicated().any():
        raise ValueError('duplicate patient_ID')
    votes = d[list(DIAGNOSIS_COLUMNS)]
    bad = set(votes.stack().unique()) - {BACTERIAL, NONBACTERIAL}
    if bad:
        raise ValueError(f'unexpected diagnosis values {bad}')
    out = pd.DataFrame({'patient_id': d['patient_ID'].astype(int), 'age': d['Age'].astype(int),
                        'sex': d['Gender'].map({'Male': 'M', 'Female': 'F'})})
    if out['sex'].isna().any():
        raise ValueError('unexpected Gender value')
    for src, dst in zip(SYMPTOMS, SYMPTOM_COLUMNS):
        if not d[src].isin((0, 1)).all():
            raise ValueError(f'symptom {src} not 0/1')
        out[dst] = d[src].astype(int)
    out['n_votes'] = votes.notna().sum(axis=1).astype(int)
    out['n_bacterial_votes'] = (votes == BACTERIAL).sum(axis=1).astype(int)
    out['bacterial_fraction'] = out['n_bacterial_votes'] / out['n_votes']
    out['label'] = (out['bacterial_fraction'] >= 0.5).astype(int)
    out['label_strict'] = (out['bacterial_fraction'] > 0.5).astype(int)
    out['tie'] = (2 * out['n_bacterial_votes'] == out['n_votes']).astype(int)
    out['unanimous'] = ((out['n_bacterial_votes'] == 0) | (out['n_bacterial_votes'] == out['n_votes'])).astype(int)
    out['age_band'] = out['age'].map(age_band)
    out.index = out['patient_id'].to_numpy()
    return out.sort_index()


def image_path(image_root, patient_id):
    """The one file in folder <patient_id>/ (names vary: '1.jpg' is '001.jpg', two are timestamps).

    Returns a path that does not exist when the folder is missing or empty (patient 666)."""
    folder = Path(image_root) / str(patient_id)
    files = sorted(p for p in folder.iterdir() if p.is_file()) if folder.is_dir() else []
    if len(files) > 1:
        raise ValueError(f'{folder} holds {len(files)} files, expected one')
    return files[0] if files else folder / 'missing'


def device_from_exif(path):
    """'samsung' / 'xiaomi' / 'unknown' from the EXIF Make tag (used only for hidden subgroups)."""
    from PIL import Image
    make = (Image.open(path).getexif().get(271) or '').strip().lower()
    return {'samsung': 'samsung', 'xiaomi': 'xiaomi'}.get(make, 'unknown')


# ---------------------------------------------------------------------------- metadata stripping

_STRIP_MARKERS = {0xE1, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xEB, 0xEC, 0xED, 0xEF, 0xFE}


def strip_jpeg_metadata(data):
    """Drop APP1 and APP3..APP15 (EXIF incl. GPS and timestamps, XMP, maker notes) and COM segments, losslessly.

    APP2 (ICC colour profile) is kept because it carries no patient or device-location information.

    The entropy-coded image data and APP0 (JFIF) are copied byte for byte, so pixels are unchanged.
    Raises ValueError for anything that is not a baseline/progressive JPEG stream.
    """
    if data[:2] != b'\xff\xd8':
        raise ValueError('not a JPEG')
    out = bytearray(b'\xff\xd8')
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            raise ValueError(f'bad marker at {i}')
        marker = data[i + 1]
        if marker == 0xFF:          # fill byte
            i += 1
            continue
        if marker == 0xDA:          # start of scan: copy the rest unchanged
            out += data[i:]
            return bytes(out)
        if 0xD0 <= marker <= 0xD7 or marker == 0x01:
            out += data[i:i + 2]
            i += 2
            continue
        (length,) = struct.unpack('>H', data[i + 2:i + 4])
        segment = data[i:i + 2 + length]
        if marker not in _STRIP_MARKERS:
            out += segment
        i += 2 + length
    raise ValueError('no start-of-scan marker')


def write_clean_image(src, dst):
    """Write src to dst as a JPEG with no metadata. JPEG: lossless segment strip. Other formats (one PNG
    with a .jpg name in the release): decoded, alpha dropped, re-encoded as JPEG quality 95. Returns the
    action taken."""
    from PIL import Image
    data = Path(src).read_bytes()
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    if data[:2] == b'\xff\xd8':
        Path(dst).write_bytes(strip_jpeg_metadata(data))
        return 'jpeg_metadata_stripped'
    im = Image.open(src).convert('RGB')
    im.save(dst, 'JPEG', quality=95)
    return 'reencoded_from_' + (Image.open(src).format or 'unknown').lower()
