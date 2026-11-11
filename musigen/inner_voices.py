"""Audit explicitly assigned inner lines against actual frozen notes.

Pitch order in an arpeggio/chord is never used as a voice identity. Expectations
and permitted gaps are authored, not universal style rules or learned weights.
"""
import argparse
import html
import json
from fractions import Fraction as F
from pathlib import Path
from musicomp.theory import tpc_name
from musigen.notation import parse_pitch,STEP_PC
from musigen.blueprint import digest,dump
from musigen.musical_checks import chord_at
from musigen.accompaniment_context import chord_degrees


def fingerprint(piece):
    from musigen.corpus_accomp import _pack
    return digest({'notes':[_pack(n) for n in sorted(piece.notes,key=lambda n:(n.onset,n.hand,n.voice))],
        'meter':piece.meter,'qpm':piece.qpm,'bars':piece.bars,
        'harmony':[(str(on),None if ch is None else [ch.symbol,ch.tones,ch.bass_tpc]) for on,ch in piece.analysis_chords]})


def pitch_name(m,t):
    name=tpc_name(t);alter=name.count('#')-name.count('b')
    octave=(m-STEP_PC[name[0]]-alter)//12-1
    return name+str(octave)


def _staff_step(pitch):
    m,t=parse_pitch(pitch);name=tpc_name(t);alter=name.count('#')-name.count('b')
    octave=(m-STEP_PC[name[0]]-alter)//12-1
    return octave*7+'CDEFGAB'.index(name[0])


def audit(piece,plan):
    if not isinstance(plan,dict) or set(plan)!={'format','version','score_sha256','voices'} or plan['format']!='musicanote-inner-voices' or plan['version']!=1:
        raise ValueError('명시적 내성 계획 version 1이 필요합니다')
    if plan['score_sha256']!=fingerprint(piece):raise ValueError('악보가 바뀌어 내성 지정의 지문이 다릅니다')
    if not isinstance(plan['voices'],list) or not plan['voices']:raise ValueError('하나 이상의 성부 지정이 필요합니다')
    seen_ids=set();assigned=set();rows=[]
    for voice in plan['voices']:
        if not isinstance(voice,dict) or set(voice)!={'id','label','events'} or not all(isinstance(voice[k],str) and voice[k].strip() for k in ('id','label')):
            raise ValueError('성부 ID·이름·음 목록을 확인하세요')
        if voice['id'] in seen_ids:raise ValueError('성부 ID가 겹칩니다')
        seen_ids.add(voice['id']);events=voice['events']
        if not isinstance(events,list) or len(events)<2:raise ValueError('성부마다 두 음 이상 지정하세요')
        points=[]
        for i,e in enumerate(events):
            fields={'bar','offset','hand','voice','pitch'}
            if not isinstance(e,dict) or not fields<=set(e) or set(e)-fields-{'next'}:raise ValueError('음 지정 필드를 확인하세요')
            if type(e['bar']) is not int or not 1<=e['bar']<=piece.bars or e['hand']!='lh' or type(e['voice']) is not int or e['voice']<1:
                raise ValueError('실제 왼손의 마디·기보 성부를 지정하세요')
            if type(e['offset']) not in (str,int) or not isinstance(e['pitch'],str):raise ValueError('음 시각은 유리수 문자열, 음높이는 철자와 옥타브로 지정하세요')
            try:offset=F(e['offset']);pitch=parse_pitch(e['pitch'])
            except (ValueError,TypeError,ZeroDivisionError) as exc:raise ValueError('음 시각·철자를 확인하세요') from exc
            if not 0<=offset<piece.bar_len:raise ValueError('마디 안 시각 범위를 벗어났습니다')
            at=piece.bar_start(e['bar'])+offset
            matched=[n for n in piece.notes if n.hand==e['hand'] and n.voice==e['voice'] and n.onset==at and pitch in n.pitches]
            if len(matched)!=1:raise ValueError('지정한 철자·옥타브·발음 시각의 음을 하나로 확인할 수 없습니다')
            ident=(at,e['hand'],e['voice'],pitch)
            if ident in assigned:raise ValueError('같은 실제 음을 서로 다른 성부로 중복 지정할 수 없습니다')
            assigned.add(ident);n=matched[0]
            if points and at<points[-1]['end']:raise ValueError('동일 내성의 실제 음이 겹칩니다')
            if i==len(events)-1 and 'next' in e:raise ValueError('마지막 음에는 다음 진행 검사를 둘 수 없습니다')
            if i<len(events)-1 and 'next' not in e:raise ValueError('각 연결의 작성 의도가 필요합니다')
            points.append({'input':e,'onset':at,'end':at+n.dur,'pitch':pitch,'source':n.src})
        links=[]
        for a,b in zip(points,points[1:]):
            expect=a['input']['next']
            if not isinstance(expect,dict) or not {'kind','reason'}<=set(expect) or set(expect)-{'kind','reason','max_gap','max_semitones','source_degree'}:
                raise ValueError('내성 진행의 의도·근거를 확인하세요')
            if expect['kind'] not in ('hold','step_up','step_down','within') or not isinstance(expect['reason'],str) or not expect['reason'].strip():raise ValueError('지원하는 진행과 작성 근거가 필요합니다')
            if type(expect.get('max_gap','0')) not in (str,int):raise ValueError('허용 쉼은 유리수로 지정하세요')
            try:gap_limit=F(expect.get('max_gap','0'))
            except (ValueError,TypeError,ZeroDivisionError) as exc:raise ValueError('허용 쉼은 음수가 아닌 유리수입니다') from exc
            if gap_limit<0:raise ValueError('허용 쉼은 음수가 아니어야 합니다')
            limit=expect.get('max_semitones')
            if limit is not None and expect['kind']!='within':raise ValueError('도약 한도는 within 진행에만 지정하세요')
            if expect['kind']=='within' and (type(limit)is not int or not 0<=limit<=24):raise ValueError('도약 한도는 작성자가 0–24반음으로 지정하세요')
            degree=expect.get('source_degree');ch=chord_at(piece.analysis_chords,a['onset'])
            if degree is not None and (type(degree)is not int or degree not in (3,7) or ch is None or a['pitch'][1] not in chord_degrees(ch,[degree])):
                raise ValueError('작성한 출발 구성음 역할이 실제 화성과 다릅니다')
            motion=b['pitch'][0]-a['pitch'][0];steps=_staff_step(b['input']['pitch'])-_staff_step(a['input']['pitch']);gap=b['onset']-a['end']
            kind=expect['kind'];met=(a['pitch']==b['pitch'] if kind=='hold' else motion in (1,2) and steps==1 if kind=='step_up' else motion in (-1,-2) and steps==-1 if kind=='step_down' else abs(motion)<=limit)
            links.append({'from':a['input'],'to':b['input'],'semitones':motion,'written_steps':steps,'gap_quarters':str(gap),
                'status':'gap_exceeds_plan' if gap>gap_limit else 'met_authored_intent' if met else 'motion_outside_plan',
                'continuity':'contiguous' if gap==0 else 'interrupted','source':a['source'],'target_source':b['source']})
        rows.append({'id':voice['id'],'label':voice['label'],'links':links})
    links=[r for v in rows for r in v['links']]
    return {'format':'musicanote-inner-voice-report','version':1,'score_sha256':fingerprint(piece),'plan_sha256':digest(plan),
        'scope':'작성자가 지정한 왼손 연결만 대조. 자동 성부 분리·전체 대위법·청취 품질 판정 아님.',
        'voices':rows,'summary':{'links':len(links),'met':sum(r['status']=='met_authored_intent' for r in links),
            'outside_plan':sum(r['status']=='motion_outside_plan' for r in links),'gaps':sum(r['status']=='gap_exceeds_plan' for r in links),
            'interrupted_links':sum(r['continuity']=='interrupted' for r in links),'assigned_pitch_events':len(assigned),
            'total_lh_pitch_events':sum(len(n.pitches) for n in piece.notes if n.hand=='lh')}}


def write_page(report,out):
    esc=lambda x:html.escape(str(x));rows=[]
    labels={'met_authored_intent':'작성 의도 충족','motion_outside_plan':'진행 재검토','gap_exceeds_plan':'허용 쉼 초과'}
    for v in report['voices']:
        for r in v['links']:
            loc=lambda e:f"{e['bar']}마디 +{e['offset']} · {e['pitch']}"
            rows.append(f"<tr><td>{esc(v['label'])}</td><td>{esc(loc(r['from']))} → {esc(loc(r['to']))}</td><td>{r['semitones']}</td><td>{esc(r['gap_quarters'])}</td><td>{labels[r['status']]}</td><td>{esc(r['from']['next']['reason'])}</td></tr>")
    s=report['summary'];page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>내성의 연결 | MUSICANOTE</title><style>body{font:16px/1.7 system-ui;background:#f5f1e8;color:#253c34;margin:0}main{max-width:1080px;margin:auto;padding:36px 22px}a{color:#285f48}.table{overflow:auto}table{border-collapse:collapse;background:#fffefa;width:100%}td,th{text-align:left;padding:12px;border-bottom:1px solid #d4dccf}h1{font-size:34px}.note{background:white;border-radius:12px;padding:18px}</style><main><a href="index.html">← 악보와 피아노</a><h1>화음 안에서 이어지는 선</h1><p>SUMMARY</p><p class="note">SCOPE 음순서를 성부로 추정하지 않았습니다. 쉼을 사이에 둔 연결은 연속 발음과 구별합니다. 시각과 쉼의 단위는 4분음표입니다.</p><div class="table"><table><thead><tr><th>성부</th><th>연결</th><th>반음 이동</th><th>쉼</th><th>결과</th><th>작성 의도</th></tr></thead><tbody>ROWS</tbody></table></div><p><a href="inner_voices.json">음표 대조 기록</a> · <a href="inner_voice_plan.json">성부 지정</a></p></main></html>'''
    page=page.replace('SUMMARY',f"지정한 {s['links']}개 연결 중 {s['met']}개가 작성 의도를 충족했습니다. 왼손 음 사건 {s['total_lh_pitch_events']}개 중 {s['assigned_pitch_events']}개를 지정했습니다.").replace('SCOPE',esc(report['scope'])).replace('ROWS',''.join(rows))
    (Path(out)/'inner_voices.html').write_text(page,encoding='utf-8')


def run(folder,plan):
    from musigen.accompaniment_review import load
    folder=Path(folder);piece,_,_=load(folder)
    result=audit(piece,plan);dump(folder/'inner_voice_plan.json',plan);dump(folder/'inner_voices.json',result);write_page(result,folder)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description='명시한 내성과 실제 음표의 연결 대조');p.add_argument('--piece',type=Path,required=True);p.add_argument('--plan',type=Path,required=True)
    a=p.parse_args();r=run(a.piece,json.loads(a.plan.read_text(encoding='utf-8')));print(json.dumps(r['summary'],ensure_ascii=False))
