"""Author-directed A/B development audition with independently verified controls.

Opt-in only. Neither version is selected or ranked automatically. References are
observations, not a fitted composer-style model. Accompaniment is frozen once
from an existing musicomp score so that melody is the variable under audition.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import html
import json
import os
import shutil
from fractions import Fraction as F
from pathlib import Path

from musigen.blueprint import prepare, dump, digest, write_xml, verify_roundtrip
from musigen.checks import check
from musigen.expression import playback
from musigen.listen import _write_page, _instrumentation
from musigen.phrases import analyze
from musigen.piece import Note
from musicomp.realize.musicxml import read_parts


def signature(piece,hand,lo=F(0),hi=None):
    hi=hi if hi is not None else piece.bars*piece.bar_len
    return sorted((str(n.onset),str(n.dur),tuple(sorted(n.pitches)),n.voice,n.art,n.slur)
                  for n in piece.notes if n.hand==hand and lo<=n.onset<hi)


def controls(a,b,protected_bars):
    for field in ('key','meter','qpm','bars','pickup','bar_keys','directions','expression'):
        if getattr(a,field)!=getattr(b,field):raise ValueError(f'비교 조건이 다릅니다: {field}')
    if a.analysis_chords!=b.analysis_chords:raise ValueError('비교 화성이 다릅니다')
    if not 1<=protected_bars<=a.bars:raise ValueError('보존 마디 범위가 잘못되었습니다')
    if signature(a,'rh',hi=protected_bars*a.bar_len)!=signature(b,'rh',hi=protected_bars*b.bar_len):
        raise ValueError('보존 구간의 선율이 달라졌습니다')
    if signature(a,'lh')!=signature(b,'lh'):raise ValueError('비교 반주가 다릅니다')
    changes=[i for i in range(1,a.bars+1)
             if signature(a,'rh',a.bar_start(i),a.bar_end(i))!=signature(b,'rh',b.bar_start(i),b.bar_end(i))]
    return {'same_key_meter_tempo_dynamics_expression':True,'same_harmony':True,
            'same_left_hand':True,'left_hand_sha256':digest(signature(a,'lh')),
            'protected_bars':[1,protected_bars],'changed_melody_bars':changes,
            'pedal_spans':sum(e['kind']=='pedal' for e in a.expression)}


def common_left(path,end):
    parts=read_parts(path)
    if len(parts)==1 and parts[0].staves==2:
        notes=[n for n in parts[0].notes if n.staff==2]
    elif len(parts)==2 and parts[1].clefs==[('F',4)] and parts[1].program==1:
        notes=parts[1].notes
    else:raise ValueError('한 피아노의 두 오선 또는 RH/LH 두 파트가 필요합니다')
    result=[Note(n.onset,min(n.dur,end-n.onset),tuple(n.pitches),'lh',n.voice,
                 'frozen:musicomp',n.articulation,n.slur) for n in notes if 0<=n.onset<end]
    if not result:raise ValueError('공통 왼손 음표가 없습니다')
    return result


def verify_written(piece,path):
    parts=read_parts(path)
    if len(parts)!=1 or parts[0].staves!=2:raise ValueError('출력 피아노 오선 구조가 다릅니다')
    actual=copy.deepcopy(piece)
    actual.notes=[Note(n.onset,n.dur,tuple(n.pitches),'rh' if n.staff==1 else 'lh',n.voice,
                       'roundtrip',n.articulation) for n in parts[0].notes]
    # read_parts does not return slurs. Compare notes, spelling, voices and articulations.
    for hand in ('rh','lh'):
        if [s[:-1] for s in signature(piece,hand)]!=[s[:-1] for s in signature(actual,hand)]:
            raise ValueError(f'출력 재읽기에서 {hand} 음표가 달라졌습니다')
    return {'exact_notes_spelling_duration_voices':True}


def write_listen(piece,plan,details,checks,target,pdf=None):
    xml=target.with_suffix('.musicxml').read_text(encoding='utf-8')
    harmony=[{**e['roman'],'q':float(F(e['onset'])),'bar':e['bar'],'symbol':e['symbol']}
             for e in details['events']]
    entry={'piece':target.stem,'xml':xml,'design':plan['design'],'checks':checks,
           'info':{'version':'v001','reason':'같은 모티프와 반주에서 선율 발전 비교','preserve':[],'preserve_broken':[]},
           'performance':playback(piece),'instrumentation':_instrumentation(xml),'harmony':harmony,
           '_pdf':str(pdf) if pdf and pdf.is_file() else None}
    _write_page([entry],target,None,True)
    content=target.read_text(encoding='utf-8')
    content=content.replace('https://cdn.jsdelivr.net/npm/verovio@6.3.0/dist/verovio-toolkit-wasm.js','assets/verovio.js')
    content=content.replace('<body>','<body><nav style="padding:12px 24px;background:#e6eee5"><a href="index.html">← 두 버전 비교</a></nav>')
    target.write_text(content,encoding='utf-8')


def write_index(out,description,presentation):
    cards=[]
    for key in ('a','b'):
        label=html.escape(presentation['versions'][key]['label'])
        explain=html.escape(presentation['versions'][key]['description'])
        links=[]
        for kind,title in [('piano_solo','피아노 솔로'),('melody_harmony','멜로디 + 상세 화성')]:
            stem=f'{key}_{kind}'
            links.append(f'<div class="format"><a class="listen" href="{stem}.html">{title} 듣기 →</a>'
                         f'<span><a href="{stem}.musicxml" download>XML 받기</a> · <a href="{stem}.pdf" download>PDF 받기</a></span></div>')
        cards.append(f'<article><div class="tag">{key.upper()}</div><h2>{label}</h2><p>{explain}</p>'+''.join(links)+'</article>')
    body='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PAGE_TITLE | MUSICANOTE Virtual Composer</title><style>
*{box-sizing:border-box}body{margin:0;background:#f6f3eb;color:#24352e;font:16px/1.7 system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:46px 28px}header{border-bottom:1px solid #cbd5cb;padding-bottom:28px}
.brand{letter-spacing:.14em;font-size:12px;font-weight:700}h1{font-size:clamp(30px,4vw,48px);line-height:1.3;margin:18px 0}
.intro{max-width:720px;color:#506258}.facts{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0}.facts span{border:1px solid #bac9bc;padding:3px 13px;border-radius:20px;font-size:14px}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:32px 0}article{background:#fffefa;border:1px solid #d2d9cc;border-radius:18px;padding:26px}
.tag{width:40px;height:40px;border-radius:50%;background:#315944;color:white;text-align:center;line-height:40px}
h2{font-size:23px}article p{color:#55665c;min-height:58px}.format{padding:14px 0;border-top:1px solid #e4e8df}
a{color:#285b43;text-underline-offset:4px}.listen{display:block;font-weight:700;font-size:18px;margin-bottom:6px}.format span{font-size:14px}
aside{padding:24px;background:#e9eee4;border-radius:16px}footer{font-size:13px;color:#59675e;margin-top:28px}
@media(max-width:700px){.cards{grid-template-columns:1fr}main{padding:28px 18px}article p{min-height:0}}
</style><main><header><div class="brand">MUSICANOTE VIRTUAL COMPOSER / MOTIF STUDY 01</div>
<h1>PAGE_TITLE</h1><p class="intro">INTRO</p><div class="facts">FACTS</div></header>
<section class="cards">CARDS</section><aside><strong>어디를 들어볼까요?</strong><p>FOCUS</p>
<p>선율 비교 초안입니다. 이후 고른 방향으로 곡 전체를 확장합니다.</p></aside>
<footer>REFERENCE<p>출처 관찰을 참고해 대화에서 작성한 발전안입니다. 자동 학습 모델이나 청취 검증이 끝난 결과는 아닙니다.</p>
<a href="comparison.json">비교 검증 기록</a> · <a href="references.json">자료 관찰과 출처</a> · <a href="decisions.json">마디별 적용 근거</a>
<p><a href="a_harmony.json">A 상세 화성 JSON</a> · <a href="b_harmony.json">B 상세 화성 JSON</a></p></footer></main></html>'''
    for token,value in {'CARDS':''.join(cards),'REFERENCE':html.escape(description),
                        'PAGE_TITLE':html.escape(presentation['title']),
                        'INTRO':html.escape(presentation['intro']),'FOCUS':html.escape(presentation['focus']),
                        'FACTS':''.join('<span>'+html.escape(f)+'</span>' for f in presentation['facts'])}.items():
        body=body.replace(token,value)
    (out/'index.html').write_text(body,encoding='utf-8')


def run(work,out,accompaniment,protected_bars=2,pages_only=False):
    work,out,accompaniment=Path(work),Path(out),Path(accompaniment)
    read=lambda name:json.loads((work/name).read_text(encoding='utf-8'))
    motif=read('motif.json');plans=[read('baseline.json'),read('reference.json')]
    observations=read('references.json');decisions=read('decisions.json')
    observed={r['work']:r for r in observations['pairs'] if r['status']=='observed'}
    if not decisions['uses'] or any(r['work'] not in observed for r in decisions['uses']):
        raise ValueError('실제 관찰한 자료와 마디별 적용 근거가 필요합니다')
    prepared=[prepare(motif,p) for p in plans];a,b=[p[0] for p in prepared]
    report=controls(a,b,protected_bars)
    left=common_left(accompaniment,a.bars*a.bar_len)
    solos=[]
    for piece in (a,b):
        solo=copy.deepcopy(piece);solo.notes=[n for n in solo.notes if n.hand=='rh']+copy.deepcopy(left);solos.append(solo)
    report['solo_controls']=controls(*solos,protected_bars)
    if set(report['changed_melody_bars'])!={bar for d in decisions['uses'] for bar in d['bars']}:
        raise ValueError('변경 마디와 자료 적용 기록이 다릅니다')
    report.update(status='awaiting_listener_comparison',motif_sha256=digest(motif),
                  plan_sha256=[digest(p) for p in plans],references_sha256=digest(observations),decisions_sha256=digest(decisions),
                  accompaniment_source=str(accompaniment),
                  accompaniment_sha256=hashlib.sha256(accompaniment.read_bytes()).hexdigest(),
                  accompaniment_policy='freeze LH from source; clip only at comparison end; RH is authored melody')
    if not pages_only and out.exists() and any(out.iterdir()):raise ValueError('새 출력 폴더를 지정하세요')
    if pages_only:
        old=json.loads((out/'comparison.json').read_text(encoding='utf-8'))
        for k in ('motif_sha256','plan_sha256','references_sha256','decisions_sha256','accompaniment_sha256'):
            if old[k]!=report[k]:raise ValueError('입력이 바뀌었습니다. 새 출력 폴더를 사용하세요')
    out.mkdir(parents=True,exist_ok=True);(out/'assets').mkdir(exist_ok=True)
    runtime=Path(os.environ['MUSICOMP_ROOT'])/'node_modules/verovio/dist/verovio-toolkit-wasm.js'
    shutil.copyfile(runtime,out/'assets/verovio.js')
    for name in ('references.json','decisions.json','motif.json','baseline.json','reference.json'):
        shutil.copyfile(work/name,out/name)
    report['versions']={}
    for key,plan,(piece,_,details),solo in zip(('a','b'),plans,prepared,solos):
        dump(out/f'{key}_harmony.json',details)
        phrase=analyze(piece,plan['design'].get('phrase_plan',[]));dump(out/f'{key}_phrases.json',phrase)
        entry={'phrase_rest_quarters':phrase['rest_quarters'],'files':{}}
        for kind,built in [('melody_harmony',piece),('piano_solo',solo)]:
            stem=f'{key}_{kind}';path=out/(stem+'.musicxml')
            checks=check(built,plan['design'])
            if checks['errors']:raise ValueError('; '.join(checks['errors']))
            if not pages_only:write_xml(built,path)
            verification=verify_roundtrip(built,path) if kind=='melody_harmony' else verify_written(built,path)
            dump(out/(stem+'_checks.json'),checks)
            view=copy.deepcopy(plan);view['design']['title']+= ' · '+('피아노 솔로' if kind=='piano_solo' else '멜로디 + 상세 화성')
            write_listen(built,view,details,checks,out/(stem+'.html'),out/(stem+'.pdf'))
            entry['files'][kind]={'roundtrip':verification,'warnings':checks['warnings']}
        report['versions'][key]=entry
    dump(out/'comparison.json',report)
    write_index(out,decisions['description'],decisions['presentation'])
    return report


def main():
    p=argparse.ArgumentParser(description='동일 조건의 모티프 발전 비교 감상본')
    p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--accompaniment',type=Path,required=True);p.add_argument('--protected-bars',type=int,default=2)
    p.add_argument('--pages-only',action='store_true')
    a=p.parse_args();r=run(a.work,a.out,a.accompaniment,a.protected_bars,a.pages_only)
    print(json.dumps({k:r[k] for k in ('status','changed_melody_bars','versions')},ensure_ascii=False))


if __name__=='__main__':main()
