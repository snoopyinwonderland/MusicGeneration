"""Opt-in DCML annotations: local-key changes are distinct from applied roots.

Exact written timing and original score label anchors are checked. This is an
inspection library, not a key detector or independent musicological verdict.
"""
import argparse
from collections import Counter
import csv
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import re
from xml.etree import ElementTree as ET

SOURCES={
    'mozart-sonatas':('Mozart','mozart_piano_sonatas'),
    'beethoven-sonatas':('Beethoven','beethoven_piano_sonatas'),
    'chopin-mazurkas':('Chopin','chopin_mazurkas'),
}
MAJOR=(0,2,4,-1,1,3,5)
MINOR=(0,2,-3,-1,1,-4,-2)
DEGREES=('I','II','III','IV','V','VI','VII')
BASE={'C':0,'D':2,'E':4,'F':-1,'G':1,'A':3,'B':5}
KEY=re.compile(r'([A-Ga-g])([b#]*)')
REL=re.compile(r'([b#]*)(VII|III|VI|IV|II|V|I|vii|iii|vi|iv|ii|v|i)')


def key_name(fifths, minor):
    for letter,base in BASE.items():
        if (fifths-base)%7==0:
            alt=(fifths-base)//7
            return letter+('#'*alt if alt>=0 else 'b'*(-alt))+(' minor' if minor else ' major')


def absolute_key(token):
    match=KEY.fullmatch(token)
    if not match or ('b' in match[2] and '#' in match[2]):raise ValueError('unsupported_global_key')
    fifths=BASE[match[1].upper()]+7*(match[2].count('#')-match[2].count('b'))
    return {'fifths':fifths,'minor':match[1].islower(),'name':key_name(fifths,match[1].islower())}


def relative_key(token, parent):
    # Resolve right-to-left: V/ii means V within ii of the current local key.
    current=dict(parent)
    for part in reversed(token.split('/')):
        match=REL.fullmatch(part)
        if not match or ('b' in match[1] and '#' in match[1]):raise ValueError('unsupported_relative_key')
        degree=DEGREES.index(match[2].upper())
        fifths=current['fifths']+(MINOR if current['minor'] else MAJOR)[degree]+7*(match[1].count('#')-match[1].count('b'))
        current={'fifths':fifths,'minor':match[2].islower(),'name':key_name(fifths,match[2].islower())}
    return current


def read_table(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        return [{**r,'source_line':i} for i,r in enumerate(csv.DictReader(f,delimiter='\t'),2)]


def source(path,root):
    return {'path':path.relative_to(root).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def label_states(rows):
    """Cross-check expanded state against explicit original label prefixes."""
    global_token=local_token=None
    for row in rows:
        label=row['label'];parts=label.removeprefix('.').split('.')
        prefixes=parts[:-1]
        for token in prefixes:
            if KEY.fullmatch(token):
                global_token=token
                local_token='i' if token[0].islower() else 'I'
            elif all(REL.fullmatch(x) for x in token.split('/')):local_token=token
            else:raise ValueError('unsupported_label_prefix')
        if (global_token,local_token)!=(row['globalkey'],row['localkey']):
            raise ValueError('expanded_key_disagrees_with_source_label')
        g=absolute_key(global_token);local=relative_key(local_token,g)
        if row['globalkey_is_minor']!=str(int(g['minor'])) or row['localkey_is_minor']!=str(int(local['minor'])):
            raise ValueError('expanded_key_mode_mismatch')
        chord=row['chord'];relative=chord.split('/',1)[1] if '/' in chord else ''
        special=row.get('special','')
        if special:
            expanded='V'+('/'+relative if relative else '')
            if special not in ('It','Ger','Fr') or row['relativeroot']!=expanded or not chord.startswith(special):
                raise ValueError('unsupported_special_expansion')
            # ms3 expands augmented-sixth symbols into /V features. This is
            # not an explicit slash tonicization in the original label.
            row['special_expansion_target']=expanded
            row['special_relative_context']=relative_key(relative,local) if relative else local
        elif relative!=row['relativeroot']:raise ValueError('applied_root_label_mismatch')
        if chord not in parts[-1]:raise ValueError('chord_label_mismatch')
        cadence=parts[-1].split('|',1)[1].rstrip('{}\\') if '|' in parts[-1] else ''
        if cadence!=row['cadence']:raise ValueError('cadence_label_mismatch')
        row['global']=g;row['local']=local
        row['applied_target']=relative_key(relative,local) if relative and not special else None
    return rows


def validate_tables(harmonies,measures,notes,score_xml,verify_score_timing=False):
    bars={};cursor=F(0)
    for m in measures:
        mc=int(m['mc']);duration=4*F(m['act_dur'])
        if mc!=len(bars)+1 or duration<=0:raise ValueError('nonsequential_measure_count')
        if F(m['quarterbeats'])!=cursor or F(m['duration_qb'])!=duration:
            raise ValueError('measure_written_clock_mismatch_or_alternate_ending')
        bars[mc]={'start':cursor,'duration':duration,'mn':m['mn'],'meter':m['timesig']};cursor+=duration
    for r in harmonies+notes:
        bar=bars.get(int(r['mc']))
        if bar is None:raise ValueError('unknown_measure')
        off=4*F(r['mc_onset'])
        if off<0 or off>=bar['duration']:raise ValueError('onset_outside_measure')
        if F(r['quarterbeats'])!=bar['start']+off:raise ValueError('event_written_clock_mismatch')
        if r['mn']!=bar['mn'] or r['timesig']!=bar['meter']:raise ValueError('measure_address_mismatch')
    for r in notes:
        dur=F(r['duration_qb'])
        if dur<0 or (dur==0 and not r['gracenote']):raise ValueError('invalid_note_duration')
        # duration_qb is a float serialization; the exact duration column stays
        # authoritative (e.g. 1/24 whole note -> 1/6 quarter, not a new grid).
        if dur and float(F(r['duration'])*4)!=float(r['duration_qb']):raise ValueError('note_duration_units_mismatch')
    sounding=[r for r in harmonies if r['chord']]
    if any(F(a['quarterbeats'])>F(b['quarterbeats']) for a,b in zip(harmonies,harmonies[1:])):
        raise ValueError('annotation_order_mismatch')
    for r in harmonies:
        if not r['chord'] and F(r['duration_qb'])!=0:raise ValueError('nonzero_point_annotation')
        if not r['chord']:r['duration_exact_qb']='0'
    if not sounding or F(sounding[0]['quarterbeats'])!=0:raise ValueError('unannotated_opening')
    for i,r in enumerate(sounding):
        end=F(sounding[i+1]['quarterbeats']) if i+1<len(sounding) else cursor
        start=F(r['quarterbeats']);exact=end-start
        # ms3 can serialize a subtraction of float coordinates. Accept only
        # a machine-roundoff bound derived from these operands, never a beat
        # quantization tolerance; output timing is still the exact fraction.
        tolerance=4*max(math.ulp(float(start)),math.ulp(float(end)),math.ulp(float(exact)))
        if end<=start or not math.isclose(float(r['duration_qb']),float(exact),rel_tol=0,abs_tol=tolerance):
            raise ValueError('harmony_duration_or_coverage_mismatch')
        r['duration_exact_qb']=str(end-F(r['quarterbeats']))
    root=ET.fromstring(score_xml)
    anchors=Counter((str(i),staff.get('id'),str(v),h.findtext('name'))
        for staff in root.findall('./Score/Staff') for i,m in enumerate(staff.findall('Measure'),1)
        for v,voice in enumerate(m.findall('voice'),1) for h in voice.findall('Harmony')
        if h.findtext('harmonyType')=='1')
    from musigen.mscx_timing import raw_label, audit
    expected=Counter((r['mc'],r['staff'],r['voice'],raw_label(r) if verify_score_timing else r['label']) for r in harmonies)
    if anchors!=expected:raise ValueError('score_annotation_anchor_mismatch')
    result={'measures':len(bars),'notes':len(notes),'harmonies':len(harmonies),'point_annotations':len(harmonies)-len(sounding),'span':str(cursor),
            'timing_scope':'TSV note/harmony coordinates vs measure table; XML label at MC/staff/voice, not XML note-time reparse',
            'repeat_policy':'written_order_not_unfolded'}
    if verify_score_timing:
        checked=audit(score_xml,measures,notes,harmonies)
        if checked['status']!='validated':raise ValueError('independent_xml_timing_mismatch')
        result['xml_timing']=checked
        result['timing_scope']=checked['scope']
    return result


def references(work_id,rows):
    result=[];previous=None
    written_end=max(F(r['quarterbeats'])+F(r['duration_exact_qb']) for r in rows)
    for i,row in enumerate(rows):
        local=row['local'];changed=previous is not None and local!=previous
        kinds=(['local_key_change'] if changed else [])+(['tonicization'] if row['applied_target'] else [])
        for kind in kinds:
            target=local if kind=='local_key_change' else row['applied_target']
            start_key=previous if kind=='local_key_change' else local
            next_change=next((j for j in range(i+1,len(rows)) if rows[j]['local']!=local),len(rows))
            end=F(rows[next_change]['quarterbeats']) if next_change<len(rows) else written_end
            cadences=[{'line':r['source_line'],'mc':r['mc'],'mn':r['mn'],'onset':r['quarterbeats'],'label':r['label'],'cadence':r['cadence']}
                      for r in rows[i:next_change] if r['cadence']]
            result.append({'id':f"{work_id}:{kind}:{row['source_line']}",'kind':kind,
                'from_key':start_key,'to_key':target,'local_context':local,
                'source_event':{**{k:row[k] for k in ('source_line','mc','mn','mc_onset','quarterbeats','duration_qb','duration_exact_qb','label','globalkey','localkey','relativeroot')},
                                'alt_label':row.get('alt_label',''),'raw_label':row['label']+('-'+row['alt_label'] if row.get('alt_label') else '')},
                'context':[{**{k:r[k] for k in ('source_line','mc','mn','quarterbeats','duration_qb','duration_exact_qb','label','localkey','relativeroot','cadence')},'alt_label':r.get('alt_label','')}
                           for r in rows[max(0,i-2):min(len(rows),i+3)]],
                'declared_region_end':str(end),'declared_region_remaining_quarters':str(end-F(row['quarterbeats'])),
                'following_cadence_annotations_in_local_region':cadences,
                'cadence_scope':'local region; not proof that an applied target became a local key',
                'status':'source_annotation_validated_not_independently_heard','generation_eligible':False})
        previous=local
    return result


def observe(root,work_ids,allow_dcml=False,verify_score_timing=False):
    if not allow_dcml:raise ValueError('DCML은 --allow-dcml 선택 옵션이 필요합니다')
    root=Path(root).resolve();works=[];all_refs=[]
    for work_id in sorted(set(work_ids)):
        if not re.fullmatch(r'[a-z-]+/[A-Za-z0-9_-]+',work_id):raise ValueError('invalid_work_id')
        corpus,piece=work_id.split('/')
        if corpus not in SOURCES:raise ValueError('unsupported_corpus')
        folder=root/corpus;composer,repo=SOURCES[corpus]
        paths={kind:folder/kind/f'{piece}.{kind}.tsv' for kind in ('harmonies','measures','notes')}
        paths.update(score=folder/'MS3'/f'{piece}.mscx',license=folder/'LICENSE',readme=folder/'README.md')
        row={'id':work_id,'composer':composer,'source_url':'https://github.com/DCMLab/'+repo,
             'license':'CC-BY-NC-SA-4.0','attribution':'DCML corpus authors; see source README',
             'sources':{},'status':'unavailable','generation_eligible':False}
        try:
            for k,path in paths.items():row['sources'][k]=source(path,root)
            if 'Attribution-NonCommercial-ShareAlike 4.0' not in paths['license'].read_text(encoding='utf-8'):
                raise ValueError('unexpected_license')
            harmonies,measures,notes=[read_table(paths[k]) for k in ('harmonies','measures','notes')]
            row['attempted_harmony_rows']=len(harmonies)
            row['validation']=validate_tables(harmonies,measures,notes,paths['score'].read_text(encoding='utf-8'),verify_score_timing)
            label_states(harmonies)
            row['validation']['special_expansions_not_counted_as_tonicizations']=sum('special_expansion_target' in r for r in harmonies)
            row['special_annotations']=[{k:r.get(k,'') for k in ('source_line','mc','mn','quarterbeats','label','alt_label','special','relativeroot','special_expansion_target','special_relative_context')} for r in harmonies if r.get('special')]
            row['status']='validated';row['local_regions']=[]
            for r in harmonies:
                if not row['local_regions'] or row['local_regions'][-1]['key']!=r['local']:
                    row['local_regions'].append({'onset':r['quarterbeats'],'mc':r['mc'],'mn':r['mn'],'key':r['local'],'label':r['label'],'line':r['source_line']})
            refs=references(work_id,harmonies)
            for ref in refs:ref['work_id']=work_id
            row['reference_counts']=dict(Counter(r['kind'] for r in refs));all_refs+=refs
        except (ValueError,KeyError,FileNotFoundError,ET.ParseError) as exc:
            row['reason']=str(exc)
        works.append(row)
    if not works:raise ValueError('empty_work_list')
    return {'format':'musicanote-tonal-library','version':1,'generation_eligible':False,
            'status':'opt_in_annotation_reference_no_training','works':works,'references':all_refs,
            'summary':{'attempted_works':len(works),'validated_works':sum(w['status']=='validated' for w in works),
                       'reference_counts':dict(Counter(r['kind'] for r in all_refs)),
                       'unavailable':dict(Counter(w['reason'] for w in works if w['status']!='validated'))},
            'standards':['https://dcmlab.github.io/standards/build/html/reference/reference.html','https://ms3.readthedocs.io/en/latest/manual/index.html']}


def get_reference(library,ref_id):
    if library.get('format')!='musicanote-tonal-library' or library.get('version')!=1:raise ValueError('국소 조성 참조 형식 오류')
    matches=[r for r in library['references'] if r['id']==ref_id]
    if len(matches)!=1:raise ValueError('검증된 국소 조성 참조 ID가 필요합니다')
    ref=matches[0];matches=[w for w in library['works'] if w['id']==ref['work_id'] and w['status']=='validated']
    if len(matches)!=1 or ref['status']!='source_annotation_validated_not_independently_heard':raise ValueError('미검증 원자료')
    return ref,matches[0]


if __name__=='__main__':
    p=argparse.ArgumentParser(description='명시적 국소 조성과 으뜸화 원 주석 검증')
    p.add_argument('--root',type=Path,required=True);p.add_argument('--works',nargs='+',required=True)
    p.add_argument('--allow-dcml',action='store_true');p.add_argument('--out',type=Path,required=True)
    p.add_argument('--verify-score-timing',action='store_true',help='원 MuseScore의 모든 기보 음표·화성 시각을 독립 대조')
    a=p.parse_args();result=observe(a.root,a.works,a.allow_dcml,a.verify_score_timing);a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(result['summary'],ensure_ascii=False))
