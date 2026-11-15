"""Extract public-release prediction inputs on the data host; never export rows.

This module intentionally does not load internal cohorts, dates, clinical free
text, DICOM headers, or PyRadiomics diagnostic values into predictor matrices.
"""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re

REGIONS = ('Frontal','Parietal','Occipital','Temporal','AnteriorTemporal',
           'MiddleTemporal','PosteriorTemporal','Parietal_Occipital','CorpusCallosum',
           'CorpusCallosum_Rostrum','CorpusCallosum_Genu','CorpusCallosum_Body',
           'CorpusCallosum_Isthmus','CorpusCallosum_Splenium','CSF',
           'Cortical Gray Matter','White Matter','Deep Gray Matter','Brain Stem','Cerebellum')
SUMMARY = {'total_lesion_volume','number_of_lesions','largest_lesion_volume',
           'average_lesion_volume','enhancement','average_dist_to_ventricles_(voxels)',
           'minimum_dist_to_Ventricles_(voxels)'}
SUMMARY.update('lesion_volume_in_'+r for r in (
    'background','csf','cortical_gray_matter','white_matter','deep_gray_matter','brain_stem','cerebellum'))
SUMMARY.update(prefix+r for prefix in ('lesion_volume_in_','percentage_volume_in_') for r in REGIONS)
SUMMARY.update('relative_'+s+'_signal' for s in ('T1','T1Post','FLAIR','ADC','min_ADC'))
SUMMARY.update(s+'_ADC_signal' for s in ('min','mean','median','five_percentile','ninety_five_percentile'))
SHAPE = ('Elongation','Flatness','LeastAxisLength','MajorAxisLength','Maximum2DDiameterColumn',
         'Maximum2DDiameterRow','Maximum2DDiameterSlice','Maximum3DDiameter','MeshVolume',
         'MinorAxisLength','Sphericity','SurfaceArea','SurfaceVolumeRatio','VoxelVolume')
FIRSTORDER = ('10Percentile','90Percentile','Energy','Entropy','InterquartileRange','Kurtosis',
              'Maximum','MeanAbsoluteDeviation','Mean','Median','Minimum','Range',
              'RobustMeanAbsoluteDeviation','RootMeanSquared','Skewness','TotalEnergy','Uniformity','Variance')
RADIOMICS = {'original_shape_'+s for s in SHAPE}|{'original_firstorder_'+s for s in FIRSTORDER}
ENDPOINT = ('Reported qualifying pathogenic/likely pathogenic alteration versus no qualifying report '
            'among mutation-record patients; not biological wild type or proven complete panel coverage.')


def _subject(raw):
    value=str(raw or '').strip().removeprefix('sub-')
    if not value or not re.fullmatch(r'[A-Za-z0-9]+',value):
        raise ValueError('Invalid private join key')
    return value.zfill(4) if value.isdigit() else value


def _number(raw):
    value=str(raw or '').strip()
    if value.lower() in {'','nan','na','n/a','none','null'}:return None
    try: result=float(value)
    except ValueError:raise ValueError('Non-numeric value in allowed imaging metric') from None
    return result if math.isfinite(result) else None


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _kv(path,allowed,diagnostics=False):
    result={}
    with path.open(newline='',encoding='utf-8-sig') as stream:
        rows=csv.reader(stream)
        if next(rows,None)!=['Label','Value']:raise ValueError('Unsupported imaging metric schema')
        for row in rows:
            if not row:continue
            if len(row)!=2:raise ValueError('Malformed imaging metric row')
            metric=row[0]
            if diagnostics and metric.startswith('diagnostics_'):continue
            if metric not in allowed:raise ValueError('Unapproved imaging metric name')
            if metric in result:raise ValueError('Duplicate imaging metric')
            result[metric]=_number(row[1])
    return result


def _lesions(path):
    with path.open(newline='',encoding='utf-8-sig') as stream:
        reader=csv.DictReader(stream)
        names=reader.fieldnames or []
        if len(names)!=len(set(names)) or 'LesionNumber' not in names or 'total_lesion_volume' not in names:
            raise ValueError('Invalid individual-lesion schema')
        metrics=[name for name in names if name!='LesionNumber']
        if set(metrics)-SUMMARY:raise ValueError('Unapproved individual-lesion metric')
        rows=list(reader)
    # Lesion number joins/checks only; never a predictor.
    ids=[r['LesionNumber'] for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate individual lesion')
    numeric=[{m:_number(r[m]) for m in metrics} for r in rows]
    volumes=[r['total_lesion_volume'] for r in numeric]
    if any(v is None or v<=0 for v in volumes):raise ValueError('Invalid lesion aggregation weight')
    output={'count':float(len(rows))}
    largest=max(range(len(rows)),key=lambda i:volumes[i]) if rows else None
    for metric in metrics:
        valid=[(r[metric],v) for r,v in zip(numeric,volumes) if r[metric] is not None]
        additive=metric=='total_lesion_volume' or metric.startswith('lesion_volume_in_')
        # Partial lesion absence is missing, not zero or a falsely complete sum.
        if additive:
            value=sum(x for x,_ in valid) if len(valid)==len(rows) and rows else None
        else:
            value=sum(x*v for x,v in valid)/sum(v for _,v in valid) if valid else None
        output[('sum_' if additive else 'weighted_')+metric]=value
        output['largest_'+metric]=numeric[largest][metric] if largest is not None else None
    return output


def load_dataset(root,seed=20261114,min_class_count=5):
    """Return sanitized numeric inputs. Keep the return value on the data host.

    Rows are unique observed genomic patients with at least one feature file.
    Multiple imaging sessions or duplicate files are rejected, not averaged.
    No original identifiers/crosswalk are retained in the returned object.
    """
    root=Path(root)
    if min_class_count<1:raise ValueError('Minimum class count must be positive')
    paths=[p for p in root.rglob('*.csv') if not p.is_symlink()]
    mutations=[p for p in paths if p.name=='ucsf500_mutations.csv']
    if len(mutations)!=1:raise ValueError('Expected exactly one public mutation table')
    records=defaultdict(list)
    with mutations[0].open(newline='',encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):records[_subject(row.get('patientdurablekey'))].append(row)
    patient_features=defaultdict(dict);seen=set();sessions=defaultdict(set);hashes=defaultdict(list)
    complete_flair=set()
    family_map={'SummaryLesions':'summary','IndividualLesions':'individual','radiomics':'radiomics'}
    for path in sorted(paths):
        family=next((f for f in family_map if 'lesions_'+f in path.parts),None)
        if family is None:continue
        match=re.search(r'_(FLAIR|T1Post)_'+family+r'\.csv$',path.name)
        if not match:raise ValueError('Unrecognized feature filename schema')
        sequence=match.group(1)
        patient_parts=[p for p in path.parts if re.fullmatch(r'sub-[A-Za-z0-9]+',p)]
        session_parts=[p for p in path.parts if re.fullmatch(r'ses-[A-Za-z0-9]+',p)]
        if len(patient_parts)!=1 or len(session_parts)!=1:raise ValueError('Ambiguous feature path')
        key=_subject(patient_parts[0])
        if key not in records:continue
        sessions[key].add(session_parts[0])
        token=(key,sequence,family)
        if token in seen or len(sessions[key])!=1:raise ValueError('Ambiguous patient-to-scan feature mapping')
        seen.add(token)
        values=_lesions(path) if family=='IndividualLesions' else _kv(path,RADIOMICS if family=='radiomics' else SUMMARY,family=='radiomics')
        if family=='SummaryLesions' and sequence=='FLAIR':complete_flair.add(key)
        prefix=sequence+'_'+family_map[family]+'_'
        patient_features[key].update({prefix+m:v for m,v in values.items()})
        hashes[family_map[family]].append(_sha(path))
    demographics=[p for p in paths if p.name=='demographics.csv']
    sex={}
    if len(demographics)>1:raise ValueError('Multiple public demographics tables')
    if demographics:
        with demographics[0].open(newline='',encoding='utf-8-sig') as stream:
            for row in csv.DictReader(stream):
                key=_subject(row.get('patientdurablekey'))
                if key in sex:raise ValueError('Duplicate demographic patient')
                sex[key]={'female':1.0,'male':0.0}.get(row.get('Sex','').strip().lower())
    patients=sorted(patient_features)
    rng=random.Random(seed);rng.shuffle(patients)
    clinical=['sex_female'] if any(sex.get(key) is not None for key in patients) else []
    features=sorted({f for row in patient_features.values() for f in row})+clinical
    X=[[sex.get(key) if f=='sex_female' else patient_features[key].get(f) for f in features] for key in patients]
    positives=defaultdict(set);all_genes=set()
    for key in patients:
        for row in records[key]:
            genes={g for g in re.split(r'[;,|/\s]+',row.get('gene','').strip().upper()) if re.fullmatch(r'[A-Z][A-Z0-9-]*',g)}
            all_genes.update(genes)
            qualifying=(row.get('reportedalteration','').strip().lower()=='true'
                        and row.get('variantclassification','').strip().lower() in {'pathogenic','likely pathogenic'}
                        and row.get('geneticorigin','').strip().lower()!='not detected')
            if qualifying:
                for gene in genes:positives[gene].add(key)
    catalog={g:{'qualifying_positive':len(positives[g]),'no_qualifying_report':len(patients)-len(positives[g]),
                'eligible':min(len(positives[g]),len(patients)-len(positives[g]))>=min_class_count} for g in sorted(all_genes)}
    labels={g:[int(key in positives[g]) for key in patients] for g in catalog if catalog[g]['eligible']}
    groups={'spatial':[f for f in features if 'percentage_volume_in_' in f],
            'intensity':[f for f in features if any(s in f for s in ('signal','enhancement','firstorder','dist_to'))],
            'morphology':[f for f in features if '_summary_' in f and any(s in f for s in ('volume','number_of_lesions')) and 'percentage_' not in f],
            'radiomics':[f for f in features if '_radiomics_' in f],
            'lesion_aggregates':[f for f in features if '_individual_' in f],
            'clinical':clinical,
            'all_imaging':[f for f in features if f not in clinical],
            'all':features.copy()}
    metadata={'subjects_with_mutation_records':len(records),'eligible_subjects':len(patients),
              'excluded_no_imaging_features':len(set(records)-set(patients)),
              'subjects_with_flair_summary':len(complete_flair),
              'gene_catalog':catalog,'minimum_class_count':min_class_count,'endpoint':ENDPOINT,
              'source_kind':'public hosted UCSF-PCNSL v1.0 only',
              'source_hashes':{'mutation_table_sha256':_sha(mutations[0]),
                               'demographics_sha256':_sha(demographics[0]) if demographics else None,
                               'feature_content_manifest_sha256':{k:hashlib.sha256('\n'.join(sorted(v)).encode()).hexdigest() for k,v in hashes.items()}},
              'feature_file_counts':{k:len(v) for k,v in hashes.items()},
              'feature_count':len(features),'feature_groups':{k:len(v) for k,v in groups.items()},
              'missing_by_feature':{f:sum(row[i] is None for row in X) for i,f in enumerate(features)},
              'age_status':'excluded: consistent birth/scan date-shift semantics not established',
              'clinical_scan_specimen_pairing_verified':False,'complete_panel_coverage_verified':False,
              'pseudonym_seed':seed,'patient_level_split_required':True}
    return {'case_ids':['case-'+format(rng.getrandbits(96),'024x') for _ in patients],
            'feature_names':features,'X':X,'labels':labels,'feature_groups':groups,'metadata':metadata}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--private-out',type=Path,required=True)
    parser.add_argument('--aggregate-out',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    dataset=load_dataset(args.root)
    with args.private_out.open('x') as stream:json.dump(dataset,stream,allow_nan=False)
    aggregate={'metadata':dataset['metadata'],'feature_names':dataset['feature_names'],
               'feature_groups':dataset['feature_groups'],'extractor_sha256':_sha(Path(__file__))}
    with args.aggregate_out.open('x') as stream:json.dump(aggregate,stream,indent=2,allow_nan=False)
    print(json.dumps({'patients':len(dataset['X']),'features':len(dataset['feature_names']),
                      'eligible_genes':list(dataset['labels'])}))


if __name__=='__main__':main()
