"""명시적으로 작성한 기능 화음. 자동 인식이나 화음 치환은 하지 않는다.

근거: 2026-11-10 사용자 요청(증6화음, 세컨더리 화음, 전조).
MusicXML kind=Italian/French/German 및 music21 RomanNumeral의 철자 사용.
"""
import re
from dataclasses import dataclass
from music21 import roman, key as mkey
from musicomp.core.score import pitch_tpc
from musicomp.theory import tpc_name
from musigen.accomp import Chord, QUALITY, parse_chord
from musigen.harmony_labels import label, display
from musigen.notation import parse_pitch

AUGMENTED={'It6':'Italian','Fr43':'French','Ger65':'German'}


@dataclass(frozen=True)
class FunctionalChord(Chord):
    @property
    def kind(self):
        return self.quality


def resolve(event,key):
    figure=event.get('figure')
    if figure is None:
        ch=parse_chord(event['symbol'])
        return ch,label(ch,key),None
    if not isinstance(figure,str) or not re.fullmatch(
            r'(It6|Fr43|Ger65|N6|[b#]?[ivIV]+[oø+]?(?:64|65|43|42|7|6)?(?:/[b#]?[ivIV]+)?)',figure):
        raise ValueError('지원하는 기능 기호를 쓰세요: V7/V, viio7/ii, iv, N6, It6, Fr43, Ger65')
    local=mkey.Key(tpc_name(key.tonic_tpc).replace('b','-'),'minor' if key.minor else 'major')
    rn=roman.RomanNumeral(figure,local)
    tones=tuple((p.pitchClass,pitch_tpc(p)) for p in rn.pitches)
    bass=pitch_tpc(rn.bass())
    if figure in AUGMENTED:
        if event.get('symbol'):
            raise ValueError('증6화음은 symbol 대신 figure로 지정하세요. 이명동음 7화음으로 대체하지 않습니다')
        # For native MusicXML functional-sixth kinds, root is the reference tonic,
        # not a claimed acoustic root (music21.harmony.CHORD_TYPES).
        ch=FunctionalChord(figure,key.tonic_tpc,figure,bass,tones)
    else:
        root=tpc_name(pitch_tpc(rn.root()))
        candidates=[]
        for quality in QUALITY:
            try:
                candidate=parse_chord(root+quality+('/'+tpc_name(bass) if bass!=pitch_tpc(rn.root()) else ''))
                if {t for _,t in candidate.tones}=={t for _,t in tones}:candidates.append(candidate)
            except ValueError:pass
        if not candidates:raise ValueError(f'{figure}: 지원 코드로 모든 철자를 보존할 수 없습니다')
        ch=candidates[0]
        if event.get('symbol'):
            authored=parse_chord(event['symbol'])
            if {t for _,t in authored.tones}!={t for _,t in ch.tones} or authored.bass_tpc!=bass:
                raise ValueError('symbol과 figure의 구성음 또는 베이스가 다릅니다')
            ch=authored
    target=rn.secondaryRomanNumeralKey
    target_tpc=pitch_tpc(target.tonic) if target else key.tonic_tpc+1 if figure in AUGMENTED else None
    analysis={'figure':figure,'engine_figure':rn.figure,
              'display':{'It6':'It⁺⁶','Fr43':'Fr⁺⁶','Ger65':'Ger⁺⁶'}.get(figure,display(figure)),
              'key':f'{tpc_name(key.tonic_tpc)} '+('단조' if key.minor else '장조'),
              'bass':tpc_name(bass),'note':'작곡자가 지정한 기능; 해결은 별도 확인','extension':None}
    intent={'kind':'augmented_sixth' if figure in AUGMENTED else 'secondary' if target else 'functional',
            'target_tpc':target_tpc,'target_root':tpc_name(target_tpc) if target_tpc is not None else None,
            'target_key':str(target) if target else None,'status':'composer_intent'}
    if figure in AUGMENTED:
        intent['tendency_tones']=[{'from':tpc_name(key.tonic_tpc-4),'to':tpc_name(target_tpc),'semitones':-1},
                                   {'from':tpc_name(key.tonic_tpc+6),'to':tpc_name(target_tpc),'semitones':1}]
    return ch,analysis,intent


def resolution_report(events):
    for i,event in enumerate(events):
        intent=event.get('functional_intent')
        if not intent or intent['target_root'] is None:continue
        nxt=events[i+1] if i+1<len(events) else None
        event['resolution_check']={'scope':'next_harmony_only_not_full_voice_leading',
            'next_bar':nxt['bar'] if nxt else None,
            'target_root_or_bass_present':bool(nxt and intent['target_root'] in (nxt['root'],nxt['bass'])),
            'note':'다음 화음의 근음/베이스만 확인합니다. 성부별 해결·종지 확정 검사가 아닙니다.'}
        if intent.get('tendency_tones'):
            movements=[]
            source=[parse_pitch(p) for p in event['voicing']]
            target=[parse_pitch(p) for p in nxt['voicing']] if nxt else []
            for tendency in intent['tendency_tones']:
                starting=[m for m,t in source if tpc_name(t)==tendency['from']]
                matched=bool(starting) and all(any(end==m+tendency['semitones'] and tpc_name(t)==tendency['to']
                                                    for end,t in target) for m in starting)
                movements.append({**tendency,'matched_in_written_lh':matched})
            event['resolution_check']['augmented_sixth_tendency_movements']=movements
            event['resolution_check']['note']+=' 증6화음의 두 경향음만 실제 왼손 배치의 반음 이동을 추가 확인합니다.'
