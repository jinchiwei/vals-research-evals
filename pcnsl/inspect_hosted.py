"""Read-only, standard-library inventory of a locally held PCNSL release.

Outputs aggregate counts and schema names, never patient rows, identifiers,
dates, free-text values or per-patient filenames. Does not extract archives.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

CLINICAL = {
    'demographics.csv', 'biopsy_and_diagnosis_dates.csv', 'diagnosis_history.csv',
    'medication_list_administered.csv', 'medication_list_ordered.csv',
    'ucsf500_mutations.csv', 'data_dictionary_clinical.csv', 'data_dictionary_imaging.csv',
}
GENES = ('MYD88', 'CD79B', 'IRF4', 'PIM1', 'BTG1', 'BTG2', 'CARD11',
         'CDKN2A', 'BCL6', 'TP53', 'PRKDC', 'ZFHX3', 'LRP1B', 'EP300')
SPATIAL_METRICS = tuple('percentage_volume_in_'+r for r in (
    'Frontal','Parietal','Occipital','Temporal','AnteriorTemporal','MiddleTemporal',
    'PosteriorTemporal','Parietal_Occipital','CorpusCallosum','CorpusCallosum_Rostrum'))
SENSITIVE = {
    'patientname':'PatientName', '00100010':'PatientName',
    'patientid':'PatientID', '00100020':'PatientID',
    'patientbirthdate':'PatientBirthDate', 'birthdate':'PatientBirthDate', '00100030':'PatientBirthDate',
    'patientbirthtime':'PatientBirthTime', '00100032':'PatientBirthTime',
    'accessionnumber':'AccessionNumber', '00080050':'AccessionNumber',
    'studydescription':'StudyDescription', '00081030':'StudyDescription',
    'seriesdescription':'SeriesDescription', '0008103e':'SeriesDescription',
    'institutionname':'InstitutionName', '00080080':'InstitutionName',
    'institutionaddress':'InstitutionAddress', '00080081':'InstitutionAddress',
    'referringphysicianname':'ReferringPhysicianName', '00080090':'ReferringPhysicianName',
    'performingphysicianname':'PerformingPhysicianName', '00081050':'PerformingPhysicianName',
    'operatorname':'OperatorName', 'operatorsname':'OperatorName', '00081070':'OperatorName',
    'studydate':'StudyDate', '00080020':'StudyDate',
    'seriesdate':'SeriesDate', '00080021':'SeriesDate',
    'acquisitiondate':'AcquisitionDate', '00080022':'AcquisitionDate',
    'contentdate':'ContentDate', '00080023':'ContentDate',
    'acquisitiondatetime':'AcquisitionDateTime', '0008002a':'AcquisitionDateTime',
    'studytime':'StudyTime', '00080030':'StudyTime',
    'acquisitiontime':'AcquisitionTime', '00080032':'AcquisitionTime',
    'studyinstanceuid':'StudyInstanceUID', '0020000d':'StudyInstanceUID',
    'seriesinstanceuid':'SeriesInstanceUID', '0020000e':'SeriesInstanceUID',
    'sopinstanceuid':'SOPInstanceUID', '00080018':'SOPInstanceUID',
    'deviceserialnumber':'DeviceSerialNumber', '00181000':'DeviceSerialNumber',
    'stationname':'StationName', '00081010':'StationName',
    'protocolname':'ProtocolName', '00181030':'ProtocolName',
    'patientcomments':'PatientComments', '00104000':'PatientComments',
    'otherpatientids':'OtherPatientIDs', '00101000':'OtherPatientIDs',
    'otherpatientnames':'OtherPatientNames', '00101001':'OtherPatientNames',
    'patientidentityremoved':'PatientIdentityRemoved', '00120062':'PatientIdentityRemoved',
    'deidentificationmethod':'DeidentificationMethod', '00120063':'DeidentificationMethod',
}
CLASSIFICATIONS = {'pathogenic':'Pathogenic', 'likely pathogenic':'Likely Pathogenic',
    'uncertain significance':'Uncertain Significance', 'variant of uncertain significance':'Uncertain Significance',
    'vus':'Uncertain Significance', 'benign':'Benign', 'likely benign':'Likely Benign',
    'unclassified':'Unclassified'}
ORIGINS = {'somatic':'Somatic', 'germline':'Germline', 'not detected':'Not Detected',
           'unknown':'Unknown', 'somatic/germline':'Somatic/Germline'}


def norm(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def present(value):
    if isinstance(value, dict):
        return present(value.get('Value', value.get('value'))) if ('Value' in value or 'value' in value) else bool(value)
    if isinstance(value, list):
        return any(present(x) for x in value)
    return value is not None and str(value).strip().lower() not in {'', 'nan', 'none', 'null', 'nat'}


def field_name(value):
    # Column names are schema, but unexpected syntax is not echoed.
    value = str(value).strip()
    return value if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_ .:/()-]{0,95}', value) else '[unrecognized-column]'


def subject(value):
    value = str(value or '').strip().removeprefix('sub-')
    return value.zfill(4) if value.isdigit() else value


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def files_under(root):
    files, symlinks = [], 0
    for current, dirs, names in os.walk(root, followlinks=False):
        for name in list(dirs):
            if (Path(current) / name).is_symlink():
                dirs.remove(name); symlinks += 1
        for name in names:
            path = Path(current) / name
            if path.is_symlink():
                symlinks += 1
            elif path.is_file():
                files.append(path)
    return sorted(files), symlinks


def inspect_release(root, box=None):
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError('Expected a real extracted release directory')
    files, skipped = files_under(root)
    subjects, sessions = set(), set()
    coverage = defaultdict(lambda: {'subjects':set(), 'sessions':set(), 'files':0})
    features = defaultdict(lambda: {'subjects':set(), 'sessions':set(), 'files':0})
    flair_summary_subjects = set()
    complete_spatial_subjects = set()
    spatial_quality = {'flair_summary_files_inspected':0,'files_with_all_ten_finite_metrics':0,
                       'parse_or_schema_failures':0,'finite_metric_file_counts':{m:0 for m in SPATIAL_METRICS}}
    masks = defaultdict(lambda: {'subjects':set(), 'sessions':set(), 'files':0})
    spaces = Counter()
    extensions = Counter()
    clinical_files = defaultdict(list)
    json_fields = defaultdict(lambda: {'files_present':0, 'files_nonempty':0})
    json_count = json_bad = 0
    docs = []
    for path in files:
        relative = path.relative_to(root)
        parts = relative.parts
        lower = str(relative).lower()
        ext = '.nii.gz' if path.name.endswith('.nii.gz') else path.suffix.lower()
        extensions[ext or '[no-extension]'] += 1
        sub = next((p for p in parts if re.fullmatch(r'sub-[A-Za-z0-9]+', p)), None)
        ses = next((p for p in parts if re.fullmatch(r'ses-[A-Za-z0-9]+', p)), None)
        if sub:
            subjects.add(sub)
        if sub and ses:
            sessions.add((sub,ses))
        def add(collection, name):
            record=collection[name]; record['files']+=1
            if sub: record['subjects'].add(sub)
            if sub and ses: record['sessions'].add((sub,ses))
        if ext in {'.nii', '.nii.gz'}:
            if 'skullstripped' in lower:
                # Extract the source sequence, not the destination registration space.
                match=re.search(r'_(T1Post|T1|FLAIR|ADC|DWI|DSC|CBV|T2)(?:_to_|_skullstripped|\.)',path.name,re.I)
                add(coverage, {'t1post':'CE-T1'}.get(match[1].lower(),match[1].upper()) if match else 'OTHER')
                for space in ('FLAIR','T1Post'):
                    if 'lesions_'+space+'_space' in parts: spaces[space]+=1
            if 'masks' in parts:
                add(masks, 'lesions_seg_comp' if 'lesions_seg_comp' in parts else 'other_mask')
        if path.suffix.lower()=='.csv':
            if path.name in CLINICAL:
                clinical_files[path.name].append(path)
            for family in ('lesions_SummaryLesions','lesions_IndividualLesions','lesions_radiomics'):
                if family in parts:
                    add(features,family)
                    if family=='lesions_SummaryLesions' and sub and re.search(r'_FLAIR_SummaryLesions\.csv$',path.name,re.I):
                        flair_summary_subjects.add(subject(sub))
                        spatial_quality['flair_summary_files_inspected']+=1
                        try:
                            with path.open(newline='',encoding='utf-8-sig') as f:
                                reader=csv.reader(f)
                                header=next(reader)
                                if len(header)!=2 or header[0].strip().lower() not in {'label','metric','','unnamed: 0'} or header[1].strip().lower() not in {'value','0'}:
                                    raise ValueError('Unrecognized summary schema')
                                found={}; duplicate=False
                                for row in reader:
                                    if not row: continue
                                    if len(row)!=2: raise ValueError('Malformed summary row')
                                    key=row[0].strip()
                                    if key in SPATIAL_METRICS:
                                        if key in found: duplicate=True
                                        try: found[key]=math.isfinite(float(row[1]))
                                        except (ValueError,OverflowError): found[key]=False
                                for key,finite in found.items():
                                    spatial_quality['finite_metric_file_counts'][key]+=int(finite)
                                if not duplicate and len(found)==len(SPATIAL_METRICS) and all(found.values()):
                                    spatial_quality['files_with_all_ten_finite_metrics']+=1
                                    complete_spatial_subjects.add(subject(sub))
                        except (ValueError,UnicodeError,OSError,csv.Error,StopIteration):
                            spatial_quality['parse_or_schema_failures']+=1
        if path.suffix.lower()=='.json' and any(k in parts for k in ('dicom_headers','dcm2niix_sidecars')):
            json_count+=1
            try:
                data=json.loads(path.read_text(encoding='utf-8-sig'))
                seen={}
                def visit(value):
                    if isinstance(value,dict):
                        for key,item in value.items():
                            known=SENSITIVE.get(norm(key))
                            if known: seen[known]=seen.get(known,False) or present(item)
                            visit(item)
                    elif isinstance(value,list):
                        for item in value: visit(item)
                visit(data)
                for key,nonempty in seen.items():
                    json_fields[key]['files_present']+=1
                    json_fields[key]['files_nonempty']+=int(nonempty)
            except (ValueError,UnicodeError,OSError):
                json_bad+=1
        if re.fullmatch(r'(readme|license|licence|dataset_description)(\.[a-z0-9]+)?',path.name,re.I):
            content=path.read_text(errors='replace')
            docs.append({'kind':path.stem.lower(),'sha256':sha(path),'bytes':path.stat().st_size,
                         'mentions_cc_by_4_0':bool(re.search(r'creativecommons.org/licenses/by/4.0|CC[ -]BY[ -]4.0',content,re.I)),
                         'mentions_v1_0':bool(re.search(r'v1\.0|version[\s:=\"]+1\.0',content,re.I))})
    def counts(collection):
        return {key:{'files':v['files'],'subjects':len(v['subjects']),'sessions':len(v['sessions'])}
                for key,v in sorted(collection.items())}
    result={'schema_version':1,'audit_scope':'Read-only aggregate inventory; not an identity/privacy clearance',
        'files':{'count':len(files),'bytes':sum(p.stat().st_size for p in files),'extensions':dict(extensions),'symlinks_skipped':skipped},
        'imaging':{'subjects':len(subjects),'sessions':len(sessions),'sequence_coverage':counts(coverage),
                   'registration_space_files':dict(spaces),'feature_coverage':counts(features),'mask_coverage':counts(masks)},
        'clinical':{},'json_metadata':{'files_inspected':json_count,'parse_failures':json_bad,'sensitive_fields':dict(sorted(json_fields.items()))},
        'spatial_feature_quality':spatial_quality,
        'release_documents':docs,
        'genomics':{'status':'No mutation table located'},
        'limitations':['Counts describe file and record presence, not image usability or clinical validity.',
                       'Mutation-table membership does not establish assay completeness or biological wild-type status.',
                       'Sensitive fields are counted without inspecting whether their values are original, shifted, or pseudonymized.',
                       'Only a fixed allowlist of sensitive JSON fields is assessed; absence here is not proof of de-identification.']}
    for name,paths in sorted(clinical_files.items()):
        records=[]; headers=[]
        for path in paths:
            with path.open(newline='',encoding='utf-8-sig') as f:
                reader=csv.DictReader(f)
                headers.extend(reader.fieldnames or [])
                records.extend(reader)
        headers=sorted(set(headers))
        subject_field=next((k for k in headers if norm(k) in {'patientdurablekey','participantid','subjectid','subject'}),None)
        ids={subject(r.get(subject_field)) for r in records if subject_field and present(r.get(subject_field))}
        result['clinical'][name]={'files':len(paths),'rows':len(records),'columns':[field_name(x) for x in headers],
            'nonempty_by_column':{field_name(k):sum(present(r.get(k)) for r in records) for k in headers},
            'subjects':len(ids) if subject_field else None,'subject_field':field_name(subject_field) if subject_field else None,
            'sha256':sha(paths[0]) if len(paths)==1 else None}
        if name=='ucsf500_mutations.csv':
            def get(row,key):
                field=next((h for h in headers if norm(h)==norm(key)),None)
                return str(row.get(field,'') or '').strip()
            classes=Counter(); origins=Counter(); flags=Counter()
            gene_any=defaultdict(set); gene_reported=defaultdict(set)
            samples=defaultdict(set)
            for row in records:
                ident=subject(row.get(subject_field)) if subject_field else ''
                classification=get(row,'variantclassification').lower()
                origin=get(row,'geneticorigin').lower()
                flag=get(row,'reportedalteration').lower()
                classes[CLASSIFICATIONS.get(classification,'[missing]' if not classification else '[other]')]+=1
                origins[ORIGINS.get(origin,'[missing]' if not origin else '[other]')]+=1
                flags[flag if flag in {'true','false','1','0'} else '[missing]' if not flag else '[other]']+=1
                sample=get(row,'tumorcollecteddate')
                if ident and present(sample): samples[ident].add(sample)
                tokens=set(re.split(r'[;,|/\s]+',get(row,'gene').upper()))
                for gene in GENES:
                    if ident and gene in tokens:
                        gene_any[gene].add(ident)
                        if flag=='true' and classification in {'pathogenic','likely pathogenic'} and origin!='not detected':
                            gene_reported[gene].add(ident)
            result['genomics']={'rows':len(records),'subjects_with_records':len(ids),'subject_field_found':bool(subject_field),
                'subjects_with_observed_sample_date':len(samples),
                'subjects_with_multiple_distinct_sample_date_strings':sum(len(v)>1 for v in samples.values()),
                'classification_counts':dict(classes),'origin_counts':dict(origins),'reported_flag_counts':dict(flags),
                'gene_subject_counts':{g:{'any_listed':len(gene_any[g]),'reported_pathogenic':len(gene_reported[g])} for g in GENES},
                'assay_negative_denominator_verified':False,
                'label_rule':'reportedalteration True; Pathogenic or Likely Pathogenic; geneticorigin not Not Detected. Aggregated across records, not selected samples.'}
            image_ids={subject(s) for s in subjects}
            candidate=ids & flair_summary_subjects & {s for s,dates in samples.items() if len(dates)==1}
            complete_candidate=candidate & complete_spatial_subjects
            result['cohort_coverage']={
                'genomic_and_imaging_subjects':len(ids & image_ids),
                'genomic_without_imaging_subjects':len(ids-image_ids),
                'genomic_with_flair_summary_subjects':len(ids & flair_summary_subjects),
                'genomic_with_flair_summary_and_one_sample_date':len(candidate),
                'genomic_with_complete_ten_spatial_features_and_one_sample_date':len(complete_candidate),
                'complete_spatial_one_sample_gene_counts':{
                    g:{'any_listed':len(gene_any[g]&complete_candidate),
                       'reported_pathogenic':len(gene_reported[g]&complete_candidate)} for g in GENES},
                'flair_summary_one_sample_gene_counts':{
                    g:{'any_listed':len(gene_any[g]&candidate),
                       'reported_pathogenic':len(gene_reported[g]&candidate)} for g in GENES},
                'clinical_pairing_verified':False,
                'interpretation':'File/record overlap only. One observed sample-date string is not proof of a unique specimen or correct scan pairing.'}
    if box is not None:
        box=Path(box)
        boxfiles,_=files_under(box)
        comparison={k:{'examined':0,'identical':0,'different':0,'missing':0,'ambiguous':0} for k in ('metadata','features')}
        metadata_names={'demographics.csv','biopsy_and_diagnosis_dates.csv','ucsf500_mutations.csv','data_dictionary_clinical.csv','data_dictionary_imaging.csv'}
        for other in boxfiles:
            group=None; candidates=[]
            if other.name in metadata_names:
                group='metadata'; candidates=clinical_files.get(other.name,[])
            elif other.suffix.lower()=='.csv' and 'lesions_SummaryLesions' in other.parts:
                group='features'
                sub=next((p for p in other.parts if p.startswith('sub-')),None)
                if sub:
                    suffix=other.parts[other.parts.index(sub):]
                    candidates=[p for p in files if p.parts[-len(suffix):]==suffix]
            if group:
                record=comparison[group]; record['examined']+=1
                if not candidates: record['missing']+=1
                elif len(candidates)>1: record['ambiguous']+=1
                elif sha(other)==sha(candidates[0]): record['identical']+=1
                else: record['different']+=1
        comparison['whole_release_equivalence_established']=False
        comparison['interpretation']='Only inspected files are compared byte-for-byte. No inference about the rest of either release or model-use eligibility.'
        result['box_comparison']=comparison
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--box',type=Path)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    try:
        report=inspect_release(args.root,args.box)
        text=json.dumps(report,indent=2,sort_keys=True)+'\n'
        if args.out:
            # Exclusive creation avoids replacing previous audit evidence.
            with args.out.open('x',encoding='utf-8') as f: f.write(text)
        else:
            sys.stdout.write(text)
    except Exception as exc:
        # Paths and row values in exception messages must not reach logs.
        sys.stderr.write('Inventory failed: '+type(exc).__name__+' (details suppressed)\n')
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
