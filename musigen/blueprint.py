"""모티프 + 작곡자가 작성한 발전 설계 → 상세 화성 악보, 선택적 기존 편곡.

새 학습 모델이 아니다. 대화에서 작성한 설계를 기존 motif 연산으로 실현한다.
정확한 분수 시점과 모든 화음 구성음은 출력 후 musicomp로 왕복 검증한다.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from fractions import Fraction as F
from xml.etree import ElementTree as ET

from musigen.accomp import parse_chord
from musigen.piece import build, Note
from musigen.motif_clip import read_events, pitch_name
from musigen.piano_io import piano_part, write_midi
from musigen.harmony_labels import label
from musicomp.theory import tpc_name


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def inversion(ch):
    # Added 2nd/6th and suspended tones are not classical inversion figures.
    order={0:0, 4:1, -3:1, 1:2, -6:2, 8:2}
    if ch.quality in ('7','maj7','m7','m7b5','dim7'):
        order.update({-2:3, 5:3, -9:3})
    return order.get(ch.bass_tpc-ch.root_tpc)


def prepare(motif, plan):
    if plan.get('format') != 'musicanote-development' or plan.get('version') != 1:
        raise ValueError('musicanote-development version 1 설계가 필요합니다')
    if set(plan)-{'format','version','design','score','harmony','references'}:
        raise ValueError('알 수 없는 발전 설계 필드입니다')
    original=read_events(motif)
    if not original or not any(e.pitches for e in original) or any(len(e.pitches)>1 for e in original):
        raise ValueError('입력 모티프는 쉼을 포함한 단선율이어야 합니다')
    score=copy.deepcopy(plan['score'])
    score.setdefault('motifs',{})['input']=copy.deepcopy(motif)
    piece=build(plan['design'],score)
    if piece.pickup:
        raise ValueError('첫 버전의 화성 교환은 온마디 시작만 지원합니다')
    if any(k!=piece.key for k in piece.bar_keys.values()):
        raise ValueError('첫 교환 버전은 단일 조성만 지원합니다. 국소 조성을 조용히 버리지 않습니다')
    if any(n.hand!='rh' or n.voice!=1 or len(n.pitches)!=1 for n in piece.notes):
        raise ValueError('설계 score에는 단선율 rh만 씁니다. 왼손은 harmony로 지정하세요')
    if any(ch for _,ch in piece.analysis_chords) or piece.expression:
        raise ValueError('화음은 harmony에만 지정하고 표현 페달은 편곡에서 결정하세요')
    piece.analysis_chords=[]
    expected=[];pos=F(0)
    for e in original:
        if e.pitches: expected.append((pos,e.dur,tuple(zip(e.pitches,e.tpcs))))
        pos+=e.dur
    actual=[(n.onset,n.dur,n.pitches) for n in piece.notes if n.onset<pos]
    if actual!=expected:
        raise ValueError('첫 제시는 입력 모티프의 음·음가·쉼을 그대로 보존해야 합니다')
    events=[];cursor=F(0);left=[]
    for i,event in enumerate(plan['harmony']):
        if set(event)-{'bar','offset','duration','symbol','function','cadence','voicing','note','source'}:
            raise ValueError('알 수 없는 화성 필드입니다')
        bar=event['bar'];off=F(event.get('offset','0'));dur=F(event['duration'])
        if type(bar)is not int or not 1<=bar<=piece.bars or off<0 or dur<=0 or off+dur>piece.bar_len:
            raise ValueError('화성은 마디 안의 양의 길이를 가져야 합니다')
        start=piece.bar_start(bar)+off
        if start!=cursor:raise ValueError('화성 시점은 순서대로 빈틈·겹침 없이 이어져야 합니다')
        ch=parse_chord(event['symbol'])
        if event.get('function') not in (None,'tonic','predominant','dominant','other'):
            raise ValueError('function은 tonic/predominant/dominant/other입니다')
        if event.get('cadence') not in (None,'PAC','IAC','HC','DC','PC','EC'):
            raise ValueError('종지 의도는 PAC/IAC/HC/DC/PC/EC입니다')
        if event.get('voicing'):
            ev=read_events({'format':'musicanote-motif','version':1,'events':[{'duration':str(dur),'pitches':event['voicing']}]})[0]
            pairs=tuple(sorted(zip(ev.pitches,ev.tpcs)))
        else:
            bass=43+(ch.bass_pc-43)%12
            tones={pc:t for pc,t in ch.tones};tones[ch.bass_pc]=ch.bass_tpc
            pairs=tuple(sorted((bass+(pc-ch.bass_pc)%12,t) for pc,t in tones.items()))
        required={t for pc,t in ch.tones}|{ch.bass_tpc}
        if not pairs or pairs[0][1]!=ch.bass_tpc or {t for m,t in pairs}!=required:
            raise ValueError('왼손 배치는 지정 베이스를 최저음으로 하며 전체 구성음을 정확히 포함해야 합니다')
        if pairs[-1][0]-pairs[0][0]>12:
            raise ValueError('화성 요약 악보의 왼손 배치는 한 옥타브 이내로 지정하세요')
        left.append(Note(start,dur,pairs,'lh',1,'harmony:authored'))
        piece.chords.append((start,ch));piece.analysis_chords.append((start,ch))
        key=piece.bar_keys[bar]
        roman=label(ch,key)
        relationships=[]
        for n in piece.notes:
            if n.onset<start+dur and n.onset+n.dur>start:
                m,t=n.pitches[0]
                relationships.append({'onset':str(n.onset),'duration':str(n.dur),'pitch':pitch_name(m,t),
                                      'chord_tone':m%12 in {pc for pc,t in ch.tones},
                                      'sustained_into_event':n.onset<start})
        events.append({**event,'offset':str(off),'duration':str(dur),'onset':str(start),
            'key':tpc_name(key.tonic_tpc)+(' minor' if key.minor else ' major'),
            'roman':roman,'root':tpc_name(ch.root_tpc),'quality':ch.quality,
            'bass':tpc_name(ch.bass_tpc),'tones':[tpc_name(t) for pc,t in ch.tones],
            'inversion':inversion(ch) if ch.bass_tpc in {t for pc,t in ch.tones} else None,
            'voicing':[pitch_name(m,t) for m,t in pairs],
            'cadence_status':'composer_intent_not_verified' if event.get('cadence') else None,
            'melody_relation':relationships,'source':event.get('source',{'kind':'composer','status':'proposed'})})
        cursor=start+dur
    if cursor!=piece.bars*piece.bar_len:raise ValueError('모든 마디의 화성을 지정해야 합니다')
    piece.notes=sorted(piece.notes+left,key=lambda n:(n.onset,n.hand,n.voice))
    return piece,score,{'format':'musicanote-harmony','version':1,'time_unit':'quarter_note',
        'motif_sha256':digest(motif),'plan_sha256':digest(plan),'events':events,
        'phrase_plan':plan['design'].get('phrase_plan',[]),'references':plan.get('references',[]),
        'arranger_contract':{'musicxml':'timing, chord tones, bass and melody',
            'sidecar_only':['function','cadence intent','emotion','provenance','voicing intent'],
            'note':'musicomp는 sidecar를 아직 읽지 않으며 지정 화음으로 편곡합니다. 보이싱 유지 보장은 아님.'}}


def verify_roundtrip(piece,path):
    from musicomp.core.score import load_melody
    mel=load_melody(path,use_given_chords=True)
    expected=[(n.onset,n.dur,*n.pitches[0]) for n in piece.notes if n.hand=='rh']
    actual=[(n.onset,n.dur,n.midi,n.tpc) for n in mel.notes]
    if actual!=expected:raise ValueError('MusicXML 재읽기에서 주선율이 달라졌습니다')
    chords=piece.analysis_chords;end=piece.bars*piece.bar_len
    wanted=[(on,chords[i+1][0] if i+1<len(chords) else end,{t for pc,t in ch.tones}|{ch.bass_tpc},ch.bass_tpc) for i,(on,ch) in enumerate(chords)]
    got=[(c.onset,c.end,set(c.tpcs),c.bass_tpc) for c in mel.given_chords]
    if wanted!=got:raise ValueError('MusicXML 재읽기에서 화음 시점·구성음·베이스가 달라졌습니다')
    return {'melody_notes':len(actual),'harmony_events':len(got),'exact':True}


def write_xml(piece,path):
    from musicomp.realize.musicxml import HarmonySymbol, write_score
    from musicomp.core.score import Measure
    part=piano_part(piece)
    # Explicit repeated events carry their own duration/intent; do not suppress them.
    part.harmonies=[HarmonySymbol(on,ch.root_tpc,ch.kind,ch.bass_tpc,ch.quality)
                    for on,ch in piece.analysis_chords]
    measures=[Measure(i,str(i+1),i*piece.bar_len,piece.bar_len,piece.bar_len) for i in range(piece.bars)]
    beats,unit=map(int,piece.meter.split('/'))
    path=write_score(path,piece.title,[part],measures,beats,unit,piece.key.sharps,piece.key.minor,tempo=piece.qpm)
    tree=ET.parse(path)
    for h,(_,ch) in zip(tree.findall('.//harmony'),piece.analysis_chords):
        h.set('placement','below')
        if ch.quality in ('6','m6'):
            h.find('kind').text='minor-sixth' if ch.quality=='m6' else 'major-sixth'
        if ch.quality in ('add9','madd9','7sus4'):
            degree=ET.SubElement(h,'degree')
            ET.SubElement(degree,'degree-value').text='7' if ch.quality=='7sus4' else '9'
            ET.SubElement(degree,'degree-alter').text='-1' if ch.quality=='7sus4' else '0'
            ET.SubElement(degree,'degree-type').text='add'
    tree.write(path,encoding='utf-8',xml_declaration=True)
    return path


def run(work,out,arrange=False):
    work=Path(work);out=Path(out)
    read=lambda name:json.loads((work/name).read_text(encoding='utf-8'))
    motif,plan=read('motif.json'),read('development.json')
    piece,score,details=prepare(motif,plan)
    if out.exists() and any(out.iterdir()):raise ValueError('새 출력 폴더를 지정하세요. 기존 결과는 덮어쓰지 않습니다')
    out.mkdir(parents=True,exist_ok=True)
    dump(out/'motif.json',motif);dump(out/'development.json',plan);dump(out/'harmony.json',details)
    xml=write_xml(piece,out/'melody_harmony.musicxml')
    verified=verify_roundtrip(piece,xml)
    midi=write_midi(xml,out/'melody_harmony.mid')
    from musigen.checks import check
    checks=check(piece,plan['design']);dump(out/'checks.json',checks)
    if checks['errors']:raise ValueError('; '.join(checks['errors']))
    report={'status':'technical_preview_not_listener_approved','roundtrip':verified,
            'melody_harmony':str(xml),'midi':str(midi) if midi else None,'arranged':False}
    if arrange:
        from musicomp.pipeline import arrange as arrange_existing
        arr=arrange_existing(str(xml),str(out/'arrangement'),harmony='given',piano='retrieval',
                             grade=plan['design']['basics'].get('grade',6),
                             style_plan=[{'from_bar':1,'style':'lyrical'}])
        solo=Path(arr)/'stage1_piano_solo.musicxml'
        if not solo.is_file():raise RuntimeError('musicomp 피아노 솔로 출력이 없습니다')
        report.update(arranged=True,piano_solo=str(solo),
                      arrangement_report=str(Path(arr)/'report.json'))
    dump(out/'result.json',report)
    from musigen.blueprint_pages import write_pages
    report['page']=write_pages(piece,plan,details,report,out,checks)
    dump(out/'result.json',report)
    return report
