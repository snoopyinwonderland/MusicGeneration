"""Opt-in, read-only TAVERN phrase-pair observations; no corpus promotion or training.

Human phrase files supply the boundaries. Matching phrase ordinals are candidates,
not proof of identical melodic roles. Only an unambiguous monophonic upper staff
is measured; we never flatten chords into a guessed melody.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path


def source(path, root):
    return {'path':path.relative_to(root).as_posix(),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def upper_staff(path):
    from music21 import converter, note, meter
    # parseData avoids writing parser caches into the corpus.
    score=converter.parseData(Path(path).read_text(encoding='utf-8'),format='humdrum')
    if not score.parts:raise ValueError('no_parts')
    part=score.parts[0].flatten()
    meters=sorted({t.ratioString for t in part.getElementsByClass(meter.TimeSignature)})
    if len(meters)!=1:raise ValueError('missing_or_changing_meter')
    events=[];cursor=F(0)
    for n in sorted(part.notesAndRests,key=lambda n:n.offset):
        on,dur=F(n.offset),F(n.duration.quarterLength)
        if n.duration.isGrace or dur<=0:raise ValueError('grace_or_zero_duration')
        if not isinstance(n,(note.Note,note.Rest)):raise ValueError('chord_in_upper_staff')
        if on<cursor:raise ValueError('overlapping_upper_staff')
        if on>cursor:events.append({'onset':str(cursor),'duration':str(on-cursor),'midi':None})
        if not n.isRest and n.pitch.midi!=int(n.pitch.midi):raise ValueError('microtonal_pitch')
        pitch=None if n.isRest else int(n.pitch.midi)
        tie=getattr(n,'tie',None)
        if tie and tie.type in ('continue','stop'):
            if not events or events[-1]['midi']!=pitch or cursor!=on:
                raise ValueError('unmatched_tie')
            events[-1]['duration']=str(F(events[-1]['duration'])+dur)
        else:events.append({'onset':str(on),'duration':str(dur),'midi':pitch})
        cursor=on+dur
    if not any(e['midi'] is not None for e in events):raise ValueError('no_pitched_events')
    return {'events':events,'span':str(cursor),'meters':meters,
            'role':'upper_staff_monophonic_candidate_not_expert_melody'}


def features(sequence):
    events=sequence['events'];pitched=[e for e in events if e['midi'] is not None]
    neighbors=windows=0
    for a,b,c in zip(events,events[1:],events[2:]):
        if any(e['midi'] is None for e in (a,b,c)):continue
        windows+=1
        # Local return by a semitone or tone, with no intervening rest.
        neighbors+=int(a['midi']==c['midi'] and abs(a['midi']-b['midi']) in (1,2))
    return {'attacks':len(pitched),'span_quarters':sequence['span'],
            'rest_quarters':str(sum((F(e['duration']) for e in events if e['midi'] is None),F(0))),
            'neighbor_return_windows':neighbors,'pitched_triplet_windows':windows}


def compare(theme,variation):
    if theme['span']!=variation['span'] or theme['meters']!=variation['meters']:
        raise ValueError('unequal_span_or_meter')
    anchors=[e for e in theme['events'] if e['midi'] is not None]
    onsets={F(e['onset']):e['midi'] for e in variation['events'] if e['midi'] is not None}
    shared=sum(F(e['onset']) in onsets for e in anchors)
    same=sum(onsets.get(F(e['onset']),-100)%12==e['midi']%12
             for e in anchors if F(e['onset']) in onsets)
    return {'theme':features(theme),'variation':features(variation),
            'theme_attack_denominator':len(anchors),'shared_attack_onsets':shared,
            'same_pitch_class_at_shared_onsets':same,
            'interpretation':'descriptive_only_not_melodic_identity_or_quality_score'}


def observe(root):
    root=Path(root);rows=[]
    for theme in sorted(root.glob('*/*/Krn/*_00_01_score.krn')):
        work=theme.name.split('_')[0]
        variation=theme.with_name(f'{work}_01_01_score.krn')
        row={'work':work,'composer':theme.parents[2].name,'theme':source(theme,root),
             'pair_basis':'first_phrase_ordinal_theme_to_first_variation',
             'generation_eligible':False}
        if not variation.exists():
            row.update(status='skipped',reason='missing_first_variation');rows.append(row);continue
        row['variation']=source(variation,root)
        # Keep annotators distinct; do not parse or silently repair their Roman labels.
        joined=theme.parent.parent/'Joined'
        row['annotations']={role:[source(p,root) for p in sorted(joined.glob(f'{work}_{v}_01*_?.krn'))]
                            for role,v in [('theme','00'),('variation','01')]}
        try:
            a,b=upper_staff(theme),upper_staff(variation)
            if not all(row['annotations'].values()):raise ValueError('missing_human_phrase_annotation')
            row.update(status='observed',metrics=compare(a,b))
        except Exception as exc:
            row.update(status='skipped',reason=f'{type(exc).__name__}: {exc}')
        rows.append(row)
    return {'format':'musicanote-variation-observations','version':1,
            'source_url':'https://github.com/jcdevaney/TAVERN',
            'attribution':'TAVERN: Theme And Variation Encodings with Roman Numerals; Devaney et al.',
            'license':'CC-BY-SA-4.0','license_sha256':hashlib.sha256((root/'LICENSE').read_bytes()).hexdigest(),
            'scope':'one ordinal pair per work; first phrase, theme and first variation only',
            'status':'inspection_only_no_fitted_model_no_holdout_evaluation',
            'attempted_pairs':len(rows),'observed_pairs':sum(r['status']=='observed' for r in rows),
            'pairs':rows}


def main():
    p=argparse.ArgumentParser(description='TAVERN 주제/변주 첫 악구의 선택적 읽기 전용 관찰')
    p.add_argument('--tavern',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    args=p.parse_args()
    if args.out.exists():raise ValueError('새 출력 파일을 지정하세요')
    data=observe(args.tavern);args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:data[k] for k in ('attempted_pairs','observed_pairs')},ensure_ascii=False))


if __name__=='__main__':main()
