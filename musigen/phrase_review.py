"""Compare an authored phrase revision with a frozen complete-piece performance."""
import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path
from musigen.blueprint import prepare,write_xml,dump,digest,verify_roundtrip
from musigen.blueprint_solo import realize,write_pages
from musigen.development_comparison import controls,verify_written
from musigen.checks import check


def evidence(library,uses,changed):
    rows={r['id']:r for r in library['phrases'] if r['status']=='observed'}
    if not uses or set(changed)!={b for u in uses for b in u['bars']}:raise ValueError('변경 마디와 적용 기록이 다릅니다')
    for u in uses:
        if not u.get('observation') or not u.get('decision'):raise ValueError('관찰과 작성자 결정을 구별해 기록하세요')
        if not u.get('reference_ids') or any(i not in rows for i in u['reference_ids']):raise ValueError('관찰된 프레이즈 ID가 필요합니다')
    return {'observed_ids':sorted({i for u in uses for i in u['reference_ids']}),
            'interpretation':'author_decisions_using_references_not_learned_generation'}


def assemble(base,motif,plan):
    read=lambda n:json.loads((Path(base)/n).read_text(encoding='utf-8'))
    original=read('development.json');old_motif=read('motif.json')
    if motif!=old_motif:raise ValueError('비교 모티프가 바뀌었습니다')
    a,_,da=prepare(motif,original);sa,_=realize(a,original,read('solo_score.json'))
    verify_written(sa,Path(base)/'piano_solo.musicxml')
    b,_,db=prepare(motif,plan)
    if original['harmony']!=plan['harmony']:raise ValueError('화성 설계가 바뀌었습니다')
    sb=copy.deepcopy(b);sb.notes=[n for n in sb.notes if n.hand=='rh']+[copy.deepcopy(n) for n in sa.notes if n.hand=='lh']
    sb.expression=copy.deepcopy(sa.expression)
    return (original,plan),(a,b),(sa,sb),(da,db)


def run(base,work,out,protected=8,pages_only=False):
    base,work,out=map(Path,(base,work,out));read=lambda n:json.loads((work/n).read_text(encoding='utf-8'))
    motif,plan,library,decisions=[read(n) for n in ('motif.json','development.json','references.json','decisions.json')]
    plans,leads,solos,details=assemble(base,motif,plan)
    report=controls(*solos,protected);controls(*leads,protected)
    from musigen.melodic_connection import compare_connections
    report['melodic_connections']=compare_connections(*solos)
    report['evidence']=evidence(library,decisions['uses'],report['changed_melody_bars'])
    report['input_sha256']=digest([motif,plan,library,decisions])
    report['baseline_xml_sha256']=hashlib.sha256((base/'piano_solo.musicxml').read_bytes()).hexdigest()
    report['baseline_score_sha256']=digest(json.loads((base/'solo_score.json').read_text(encoding='utf-8')))
    if pages_only:
        old=json.loads((out/'comparison.json').read_text(encoding='utf-8'))
        for k in ('input_sha256','baseline_xml_sha256','baseline_score_sha256'):
            if old[k]!=report[k]:raise ValueError('입력이 바뀌었습니다. 새 출력 폴더가 필요합니다')
    elif out.exists() and any(out.iterdir()):raise ValueError('새 출력 폴더가 필요합니다')
    out.mkdir(parents=True,exist_ok=True);report['versions']={}
    for key,p,lead,solo,harmony in zip(('a','b'),plans,leads,solos,details):
        dest=out/key;dest.mkdir(exist_ok=True);pieces={'melody_harmony':lead,'piano_solo':solo}
        checks={kind:check(piece,p['design']) for kind,piece in pieces.items()}
        if any(c['errors'] for c in checks.values()):raise ValueError(str(checks))
        for kind,piece in pieces.items():
            target=dest/(kind+'.musicxml')
            if not pages_only:write_xml(piece,target)
            verify_roundtrip(piece,target) if kind=='melody_harmony' else verify_written(piece,target)
            dump(dest/(kind+'_checks.json'),checks[kind])
        dump(dest/'harmony.json',harmony)
        from musigen.blueprint_solo import performed_harmony
        dump(dest/'performed_harmony.json',performed_harmony(solo,harmony))
        view=copy.deepcopy(p);view['design']['title']+=' · '+key.upper()
        write_pages(dest,view,harmony,pieces,checks,decisions['feedback'])
        page=(dest/'index.html').read_text(encoding='utf-8').replace('<main>','<main><p><a href="../index.html">← 발전안 비교</a></p>')
        (dest/'index.html').write_text(page,encoding='utf-8')
        report['versions'][key]={'rest_quarters':checks['piano_solo']['phrasing']['rest_quarters'],
             'phrases':[r['bars'] for r in checks['piano_solo']['phrasing']['phrases']],
             'warnings':checks['piano_solo']['warnings'],'errors':checks['piano_solo']['errors']}
    for n in ('motif.json','development.json','references.json','decisions.json'):shutil.copyfile(work/n,out/n)
    report['status']='awaiting_listening_not_automatically_selected';dump(out/'comparison.json',report)
    import html
    e=html.escape
    cards=''.join(f'<article><h2>{e(label)}</h2><p>{e(text)}</p><a class="listen" href="{k}/piano_solo.html">피아노 솔로 듣기</a><p><a href="{k}/index.html">멜로디＋상세 화성 · XML/PDF</a></p></article>' for k,label,text in [(k,decisions['presentation'][k]['label'],decisions['presentation'][k]['description']) for k in ('a','b')])
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>주제의 귀환과 마침 | MUSICANOTE</title>
<style>body{margin:0;background:#f6f3eb;color:#243b32;font:16px/1.8 system-ui}main{max-width:1040px;margin:auto;padding:38px 24px}h1{font-size:36px}section{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:28px 0}article,aside{border-radius:16px;padding:24px;background:#fffefa;border:1px solid #d1d9cd}a{color:#285b43}.listen{display:inline-block;padding:10px 20px;background:#315944;color:white;border-radius:8px;text-decoration:none}aside{background:#e8eee2}small{color:#5a6b60}@media(max-width:700px){section{grid-template-columns:1fr}h1{font-size:29px}}</style>
<main><small>MUSICANOTE VIRTUAL COMPOSER</small><h1>주제의 귀환과 마침</h1><p>PIECE_FACTS</p><p>CONTROL_TEXT</p><section>CARDS</section><aside><strong>FOCUS_TITLE</strong><p>FOCUS_TEXT</p></aside><h2>관찰과 작곡 결정</h2><p>자료의 반복 관계, 긴 끝음과 뒤 쉼을 참고했습니다. 구체적인 조각내기·음높이·적용 마디는 작성자의 선택입니다. 자동 점수로 B가 더 좋다고 판정하지 않습니다.</p><p><a href="comparison.json">보존·프레이즈 검사</a> · <a href="decisions.json">마디별 근거</a> · <a href="references.json">자료와 출처</a></p><p><small>TAVERN · Devaney 외 · CC BY-SA 4.0. 작곡가 스타일 생성이나 새로운 학습 모델의 결과는 아닙니다.</small></p></main></html>'''.replace('CARDS',cards)
    page=page.replace('주제의 귀환과 마침',e(decisions['presentation'].get('title','주제의 귀환과 마침')))
    values={'PIECE_FACTS':f'{solos[0].title} · {solos[0].bars}마디', 'CONTROL_TEXT':f'첫 {protected}마디, 전체 화성·왼손·빠르기·셈여림·페달을 같게 두고 선율 발전을 비교합니다.', 'FOCUS_TITLE':decisions['presentation']['focus_title'],'FOCUS_TEXT':decisions['presentation']['focus']}
    for token,value in values.items():page=page.replace(token,e(value))
    from musigen.review_choice import manifest,section
    page=page.replace('</main>',section(manifest(out,report))+'</main>')
    (out/'index.html').write_text(page,encoding='utf-8');return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description='완성곡의 동일 조건 프레이즈 발전 비교')
    p.add_argument('--baseline',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--protected-bars',type=int,default=8);p.add_argument('--pages-only',action='store_true');a=p.parse_args()
    r=run(a.baseline,a.work,a.out,a.protected_bars,a.pages_only)
    print(json.dumps({k:r[k] for k in ('changed_melody_bars','versions')},ensure_ascii=False))
