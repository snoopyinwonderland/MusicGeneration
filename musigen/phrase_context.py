"""Human-bounded phrase context; exact bar windows and independent annotations.

No inferred phrase segmentation, learned style, automatic cadence class or
candidate ranking. Source scores and annotation spines remain read-only.
"""
import argparse
from collections import Counter
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import re
from musigen.humdrum_timing import parse, validate_alignment
from musigen.variation_reference import upper_staff, source
from musigen.phrase_reference import ending


def windows(parsed, lengths=(2,4,8)):
    if any(type(n) is not int or n not in (2,4,8) for n in lengths):
        raise ValueError('window_length_must_be_2_4_or_8')
    result=[]; bars=parsed['bars']
    for length in sorted(set(lengths)):
        for start in range(len(bars)-length+1):
            group=bars[start:start+length]
            if not all(b['full'] for b in group):continue
            lo=F(group[0]['onset']); hi=F(group[-1]['onset'])+F(group[-1]['duration'])
            result.append({'length_bars':length,'start':str(lo),'end':str(hi),
                           'bar_ordinals':[b['ordinal'] for b in group],
                           'source_bar_labels':[b['raw'] for b in group],
                           'ends_source_phrase':hi==F(parsed['span']),
                           'whole_source_phrase':lo==0 and hi==F(parsed['span'])})
    return result


def clip_annotations(events, start, end):
    result=[]
    for event in events:
        on,dur=F(event['onset']),F(event['duration'])
        lo,hi=max(start,on),min(end,on+dur)
        if lo>=hi:continue
        result.append({'onset':str(lo-start),'duration':str(hi-lo),
                       'label':event['label'],'raw':event['raw'],'line':event['line'],
                       'source_onset':event['onset'],'source_duration':event['duration'],
                       'clipped_at_window':lo!=on or hi!=on+dur})
    return result


def annotation_tracks(parsed, start, end):
    result={}
    for spine in parsed['spines']:
        if spine['kind'] in ('**harm','**function'):
            result[spine['kind'][2:]]=clip_annotations(spine['events'],start,end)
    result['keys']=[k for k in parsed['keys'] if F(k['onset'])<end]
    result['source_bar_labels']=[b['raw'] for b in parsed['bars'] if start<=F(b['onset'])<end]
    return result


def comparison(annotators, span):
    if set(annotators)!={'a','b'}:
        return {'status':'two_aligned_annotators_unavailable','differences':[]}
    diffs=[]
    for field in ('harm','function'):
        a,b=annotators['a'][field],annotators['b'][field]
        cuts=sorted({F(0),F(span)}|{F(e['onset']) for e in a+b}|
                    {F(e['onset'])+F(e['duration']) for e in a+b})
        for lo,hi in zip(cuts,cuts[1:]):
            labels=[]
            for events in (a,b):
                found=[e['label'] for e in events if F(e['onset'])<=lo<F(e['onset'])+F(e['duration'])]
                if len(found)!=1:raise ValueError('annotation_coverage_not_exact')
                labels.append(found[0])
            if labels[0]!=labels[1]:diffs.append({'field':field,'onset':str(lo),'duration':str(hi-lo),'a':labels[0],'b':labels[1]})
    return {'status':'compared_literal_labels_not_consensus','differences':diffs}


def melody_observation(sequence, start, end):
    if sequence is None:return None
    notes=[e for e in sequence['events'] if e['midi'] is not None and start<=F(e['onset'])<end]
    rest=sum((max(F(0),min(end,F(e['onset'])+F(e['duration']))-max(start,F(e['onset'])))
              for e in sequence['events'] if e['midi'] is None),F(0))
    return {'attacks':len(notes),'rest_quarters':str(rest),
            'onsets':[str(F(e['onset'])-start) for e in notes],
            'durations':[e['duration'] for e in notes],
            'intervals':[b['midi']-a['midi'] for a,b in zip(notes,notes[1:])],
            'scope':'attacks_inside_window; sustained entry notes are not new attacks; original note durations may cross window',
            'role':sequence['role']}


def observe(root, works):
    root=Path(root).resolve(); works=sorted(set(works))
    if not works or any(not re.fullmatch(r'[BM][A-Z0-9]{3}',w) for w in works):raise ValueError('invalid_work_ids')
    files=sorted(p for p in root.glob('*/*/Krn/*_score.krn')
                 if p.name.split('_')[0] in works and re.fullmatch(r'[BM][A-Z0-9]{3}_(00|01)_\d{2}_score.krn',p.name))
    if {p.name.split('_')[0] for p in files}!=set(works):raise ValueError('unknown_work')
    rows=[]; units=[]
    for path in files:
        work,var,ordinal,_=path.stem.split('_'); phrase=f'{work}_{var}_{ordinal}'
        row={'id':phrase,'work':work,'variation':var,'phrase_ordinal':ordinal,
             'composer':path.parents[2].name,'score':source(path,root),'annotations':[],
             'generation_eligible':False,'cadence_class':None,'cadence_status':'not_inferred_from_terminal_chord'}
        score=None; sequence=None; valid={}
        try:
            score=parse(path.read_text(encoding='utf-8'))
            row.update(score_status='timed',meter=score['meter'],span=score['span'],bars=score['bars'],grace_events=score['grace_events'])
        except ValueError as exc:row.update(score_status='unsupported',score_reason=str(exc))
        if score:
            try:
                sequence=upper_staff(path)
                if F(sequence['span'])!=F(score['span']):raise ValueError('melody_span_mismatch')
                row.update(melody_status='observed',ending=ending(sequence))
            except Exception as exc:
                sequence=None; row.update(melody_status='unavailable',melody_reason=f'{type(exc).__name__}: {exc}')
        for ann in sorted(path.parent.parent.joinpath('Joined').glob(phrase+'*_?.krn')):
            match=re.fullmatch(re.escape(phrase)+r'([a-z]+)_([ab])',ann.stem)
            if not match:continue
            item={**source(ann,root),'annotator':match[2],'content_label':match[1]}
            try:
                joined=parse(ann.read_text(encoding='utf-8'))
                item.update(parsed_meter=joined['meter'],parsed_span=joined['span'])
                if score is None:raise ValueError('source_score_unavailable_for_alignment')
                validate_alignment(score,joined)
                if match[2] in valid:raise ValueError('duplicate_annotator')
                valid[match[2]]=joined
                item.update(status='aligned',tracks=annotation_tracks(joined,F(0),F(joined['span'])))
            except ValueError as exc:item.update(status='unavailable',reason=str(exc))
            row['annotations'].append(item)
        if score and valid:
            row['status']='context_available'
            row['comparison']=comparison({k:annotation_tracks(v,F(0),F(score['span'])) for k,v in valid.items()},score['span'])
            for window in windows(score):
                lo,hi=F(window['start']),F(window['end'])
                tracks={k:annotation_tracks(v,lo,hi) for k,v in valid.items()}
                unit={**window,'id':f"{phrase}:{window['length_bars']}:{window['bar_ordinals'][0]}",
                      'phrase_id':phrase,'work':work,'composer':row['composer'],'variation':var,'meter':score['meter'],
                      'annotators':tracks,'comparison':comparison(tracks,str(hi-lo)),
                      'melody':melody_observation(sequence,lo,hi),'generation_eligible':False,
                      'cadence_class':None,'boundary':'contiguous_full_bars_within_one_human_phrase_not_new_phrase_labels'}
                units.append(unit)
        else:row['status']='context_unavailable'
        rows.append(row)
    annotation_rows=[a for r in rows for a in r['annotations']]
    summary={'attempted_phrases':len(rows),'timed_scores':sum(r['score_status']=='timed' for r in rows),
             'phrases_with_aligned_annotation':sum(r['status']=='context_available' for r in rows),
             'annotation_files':len(annotation_rows),'aligned_annotations':sum(a['status']=='aligned' for a in annotation_rows),
             'window_counts':dict(Counter(str(u['length_bars']) for u in units)),
             'score_skip_reasons':dict(Counter(r['score_reason'] for r in rows if 'score_reason' in r)),
             'annotation_skip_reasons':dict(Counter(a['reason'] for a in annotation_rows if 'reason' in a)),
             'phrases_with_annotation_differences':sum(bool(r.get('comparison',{}).get('differences')) for r in rows)}
    return {'format':'musicanote-phrase-context-library','version':1,'works_requested':works,
            'status':'inspection_only_no_training_no_population_estimate','generation_eligible':False,
            'source_url':'https://github.com/jcdevaney/TAVERN','attribution':'TAVERN, Devaney et al.',
            'license':'CC-BY-SA-4.0','license_sha256':hashlib.sha256((root/'LICENSE').read_bytes()).hexdigest(),
            'scope':'selected works, theme and first variation; human phrase boundaries, written order, repeats not expanded',
            'summary':summary,'phrases':rows,'windows':units}


def export_reference(library, unit_id):
    matches=[u for u in library['windows'] if u['id']==unit_id]
    if len(matches)!=1:raise ValueError('unknown_or_duplicate_unit')
    unit=matches[0]; phrase=next(p for p in library['phrases'] if p['id']==unit['phrase_id'])
    return {'format':'musicanote-phrase-context','version':1,'reference':unit,
            'provenance':{k:library[k] for k in ('source_url','attribution','license','license_sha256')},
            'source_score':phrase['score'],'source_annotations':[{k:a[k] for k in ('path','sha256','annotator')}
                           for a in phrase['annotations'] if a['status']=='aligned'],
            'author_decision':None,'user_selection':None,'generation_eligible':False,
            'use':'자료의 구조를 참고한 작성 결정을 별도로 적어야 합니다. 원곡 선율이나 생성 모델 출력이 아닙니다.'}


def main():
    p=argparse.ArgumentParser(description='사람이 나눈 프레이즈 안의 연속 마디와 화성 시각 참조')
    p.add_argument('--root',type=Path);p.add_argument('--works',nargs='+')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--library',type=Path);p.add_argument('--unit')
    args=p.parse_args()
    if args.library:
        if not args.unit:p.error('--library에는 --unit이 필요합니다')
        result=export_reference(json.loads(args.library.read_text(encoding='utf-8')),args.unit)
    else:
        if not args.root or not args.works:p.error('--root와 --works가 필요합니다')
        result=observe(args.root,args.works)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    if not args.library:
        from musigen.phrase_context_page import write_page
        write_page(result,args.out.with_suffix('.html'))
    print(json.dumps(result.get('summary',{'unit':args.unit}),ensure_ascii=False))


if __name__=='__main__':main()
