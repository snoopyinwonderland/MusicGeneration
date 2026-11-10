"""Auditable, bounded phrase references. No inferred boundaries or fitted style model."""
import argparse
import hashlib
import json
import re
from fractions import Fraction as F
from pathlib import Path
from statistics import median
from musigen.variation_reference import upper_staff,features,compare,source


def ending(sequence):
    pitched=[e for e in sequence['events'] if e['midi'] is not None]
    if not pitched:raise ValueError('no_pitched_events')
    last=pitched[-1];previous=[F(e['duration']) for e in pitched[:-1]]
    typical=median(previous) if previous else None
    return {'last_note_duration':last['duration'],
            'preceding_duration_median':str(typical) if typical is not None else None,
            'last_to_preceding_median':str(F(last['duration'])/typical) if typical else None,
            'trailing_rest':str(F(sequence['span'])-F(last['onset'])-F(last['duration'])),
            'interpretation':'end_duration_observation_not_cadence_classification'}


def annotations(path):
    """Read literal function/harm spines; never repair Roman numerals or merge annotators."""
    header=None;functions=[];harmonies=[];keys=[]
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('!'):continue
        fields=line.split('\t')
        if line.startswith('**'):
            if header is not None:raise ValueError('multiple_exclusive_headers')
            header=fields
            if fields.count('**function')!=1 or fields.count('**harm')!=1:raise ValueError('missing_annotation_spine')
            continue
        if header is None:continue
        if len(fields)!=len(header):raise ValueError('changing_spine_count')
        if any(x in ('*^','*v','*x','*+') for x in fields):raise ValueError('spine_path_operation')
        if line.startswith('*'):
            for value in fields:
                if re.fullmatch(r'\*[A-Ga-g][#-]?:',value) and value not in keys:keys.append(value)
            continue
        if line.startswith('='):continue
        for kind,result in [('**function',functions),('**harm',harmonies)]:
            value=fields[header.index(kind)]
            if value in ('.','!'):continue
            match=re.fullmatch(r'\d+(?:%\d+)?\.*(.+)',value)
            if not match:raise ValueError('unsupported_annotation_token:'+value)
            result.append({'raw':value,'label':match.group(1)})
    if header is None:raise ValueError('missing_exclusive_header')
    compact=[]
    for item in functions:
        if not compact or compact[-1]!=item['label']:compact.append(item['label'])
    return {'function_labels':compact,'functions':functions,'terminal_harmony_raw':harmonies[-1]['raw'] if harmonies else None,
            'key_tokens':keys,'timing':'not_aligned_to_notes','cadence_class':None}


def observe(root,works):
    root=Path(root);requested=sorted(set(works));rows=[];sequences={};relations=[]
    folders={p.name.split('_')[0]:p.parent.parent for p in root.glob('*/*/Krn/*_00_01_score.krn')}
    if any(w not in folders for w in requested):raise ValueError('unknown_work')
    for work in requested:
        folder=folders[work]
        files=sorted(p for p in (folder/'Krn').glob(work+'_*_score.krn')
                     if re.fullmatch(re.escape(work)+r'_(00|01)_\d{2}_score.krn',p.name))
        for path in files:
            _,variation,phrase,_=path.stem.split('_');key=f'{work}_{variation}_{phrase}'
            row={'id':key,'work':work,'variation':variation,'phrase_ordinal':phrase,'score':source(path,root),
                 'generation_eligible':False,'boundary':'source_phrase_file','annotations':[]}
            for ann in sorted((folder/'Joined').glob(key+'*_?.krn')):
                match=re.fullmatch(re.escape(key)+r'([a-z]+)_([ab])',ann.stem)
                if not match:continue
                item={**source(ann,root),'content_label':match[1],'annotator':match[2]}
                try:item.update(status='read',**annotations(ann))
                except ValueError as exc:item.update(status='unread',reason=str(exc))
                row['annotations'].append(item)
            try:
                if {a['annotator'] for a in row['annotations']}!={'a','b'}:raise ValueError('missing_two_annotators')
                seq=upper_staff(path);sequences[key]=seq
                row.update(status='observed',metrics=features(seq),ending=ending(seq),meters=seq['meters'])
            except Exception as exc:row.update(status='skipped',reason=f'{type(exc).__name__}: {exc}')
            rows.append(row)
        observed=[r for r in rows if r['work']==work and r['status']=='observed']
        for row in observed:
            if row['variation']!='00':continue
            key=f"{work}_01_{row['phrase_ordinal']}"
            if key not in sequences:continue
            try:metrics=compare(sequences[row['id']],sequences[key])
            except ValueError:continue
            relations.append({'from':row['id'],'to':key,'basis':'same_phrase_ordinal_theme_to_first_variation',
                              'metrics':metrics,'interpretation':'candidate_relation_not_note_alignment'})
        for variation in ('00','01'):
            group=[r for r in observed if r['variation']==variation]
            for i,a in enumerate(group):
                for b in group[i+1:]:
                    common=[]
                    for annotator in ('a','b'):
                        x={n['content_label'] for n in a['annotations'] if n['annotator']==annotator}
                        y={n['content_label'] for n in b['annotations'] if n['annotator']==annotator}
                        if x&y:common.append(annotator)
                    if common:relations.append({'from':a['id'],'to':b['id'],'basis':'source_content_label',
                                                'annotators':common,'interpretation':'annotated_relatedness_not_exact_repetition'})
    return {'format':'musicanote-phrase-references','version':1,'works_requested':requested,
            'source_url':'https://github.com/jcdevaney/TAVERN','attribution':'TAVERN, Devaney et al.',
            'license':'CC-BY-SA-4.0','license_sha256':hashlib.sha256((root/'LICENSE').read_bytes()).hexdigest(),
            'scope':'selected works, theme and first variation, all ordinal phrase files',
            'attempted_phrases':len(rows),'observed_phrases':sum(r['status']=='observed' for r in rows),
            'annotation_files':sum(len(r['annotations']) for r in rows),
            'annotation_files_read':sum(a['status']=='read' for r in rows for a in r['annotations']),
            'status':'inspection_reference_no_training_no_population_estimate','phrases':rows,'relations':relations}


def query(library,kind):
    if kind=='related':return [r for r in library['relations'] if r['basis']=='source_content_label']
    if kind=='variation':return [r for r in library['relations'] if r['basis']=='same_phrase_ordinal_theme_to_first_variation']
    if kind not in ('rest','held_end'):raise ValueError('unknown_query')
    return [r for r in library['phrases'] if r['status']=='observed' and
            (F(r['ending']['trailing_rest'])>0 if kind=='rest' else
             r['ending']['last_to_preceding_median'] is not None and F(r['ending']['last_to_preceding_median'])>1)]


if __name__=='__main__':
    p=argparse.ArgumentParser(description='사람이 나눈 프레이즈의 관찰·관계 참조')
    p.add_argument('--root',type=Path);p.add_argument('--works',nargs='+');p.add_argument('--out',type=Path)
    p.add_argument('--library',type=Path);p.add_argument('--query',choices=['related','variation','rest','held_end']);a=p.parse_args()
    if a.query:
        print(json.dumps(query(json.loads(a.library.read_text(encoding='utf-8')),a.query),ensure_ascii=False,indent=2))
    else:
        result=observe(a.root,a.works);a.out.parent.mkdir(parents=True,exist_ok=True)
        with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
        print(json.dumps({k:result[k] for k in ('attempted_phrases','observed_phrases','annotation_files','annotation_files_read')},ensure_ascii=False))
