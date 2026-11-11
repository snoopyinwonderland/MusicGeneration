"""Verify declared motif transformations and expose the authored development path."""
import argparse
import html
import json
from fractions import Fraction as F
from pathlib import Path
from musicomp.theory import spell
from musigen.blueprint import dump,digest
from musigen.motif_clip import read_events
from musigen.motif import realise


def verify_uses(piece,motif,uses):
    if not isinstance(uses,list) or not uses:raise ValueError('모티프 사용 위치를 하나 이상 지정하세요')
    result=[];ids=set()
    for u in uses:
        if not isinstance(u,dict) or not {'id','bar','label','kind'}<=set(u) or set(u)-{'id','bar','label','kind','offset','ops','sequence'}:raise ValueError('모티프 대조 필드를 확인하세요')
        if not isinstance(u['id'],str) or not u['id'] or u['id'] in ids or not isinstance(u['label'],str) or not u['label'].strip():raise ValueError('서로 다른 ID와 설명이 필요합니다')
        ids.add(u['id']);bar=u['bar']
        if type(bar)is not int or not 1<=bar<=piece.bars:raise ValueError('모티프 대조 마디가 범위를 벗어납니다')
        if u['kind'] not in ('exact','rhythm','transform'):raise ValueError('exact/rhythm/transform 대조를 지정하세요')
        ops=u.get('ops',[]);seq=u.get('sequence',{'times':1,'step':0})
        if not isinstance(ops,list) or any(not isinstance(op,str) for op in ops):raise ValueError('변형은 연산 문자열 목록입니다')
        if u['kind']!='transform' and (ops or 'sequence' in u):raise ValueError('변형은 transform 대조에만 지정하세요')
        if not isinstance(seq,dict) or set(seq)!={'times','step'} or type(seq['times'])is not int or not 1<=seq['times']<=16 or type(seq['step'])is not int:raise ValueError('반복 횟수·이동을 확인하세요')
        if type(u.get('offset','0')) not in (int,str):raise ValueError('시각은 유리수로 지정하세요')
        try:off=F(u.get('offset','0'))
        except (ValueError,TypeError,ZeroDivisionError) as exc:raise ValueError('시각을 확인하세요') from exc
        if not 0<=off<piece.bar_len:raise ValueError('마디 안 시각 범위를 벗어납니다')
        expected=[];pos=F(0)
        for j in range(seq['times']):
            es=realise(read_events(motif),ops+([f"step:{j*seq['step']}"] if j else []),piece.bar_keys[bar])
            for e in es:
                if e.pitches:expected.append((pos,e.dur,tuple((m,t if t is not None else spell(m,piece.bar_keys[bar])) for m,t in zip(e.pitches,e.tpcs or (None,)*len(e.pitches)))))
                pos+=e.dur
        if not expected or pos<=0:raise ValueError('빈 모티프 변형은 대조할 수 없습니다')
        start=piece.bar_start(bar)+off;end=start+pos
        if end>piece.bar_end(piece.bars):raise ValueError('모티프 변형이 곡 끝을 넘습니다')
        notes=[n for n in piece.notes if n.hand=='rh' and n.onset<end and n.onset+n.dur>start]
        actual=[(n.onset-start,n.dur,n.pitches) for n in notes]
        if u['kind']=='rhythm':expected=[r[:2] for r in expected];actual=[r[:2] for r in actual]
        if actual!=expected:raise ValueError(f"{u['id']}: 선언한 모티프의 음·음가·쉼이 실제 악보와 다릅니다")
        result.append({**u,'start':str(start),'end':str(end),'duration':str(pos),'attacks':len(notes),'status':'verified_actual_notes'})
    return result


def run(folder):
    from musigen.accompaniment_review import load
    from musigen.development_recipe import compile_recipe
    folder=Path(folder);read=lambda n:json.loads((folder/n).read_text(encoding='utf-8'))
    motif,recipe,refs=[read(n) for n in ['motif.json','recipe.json','references.json']]
    tonal=read('tonal_references.json') if (folder/'tonal_references.json').is_file() else None
    plan,_,trace=compile_recipe(motif,recipe,refs,tonal)
    if plan!=read('development.json') or trace!=read('development_trace.json'):raise ValueError('작성 과정과 고정 출력의 설계가 다릅니다')
    piece,_,_=load(folder);uses=verify_uses(piece,motif,recipe.get('motif_uses'))
    report={'status':'authored_development_verified_not_listener_approved','motif_sha256':digest(motif),
        'recipe_sha256':digest(recipe),'claims':uses,'stages':trace['stages'],
        'tonal_moves':len(trace.get('tonal_moves',[])),'reference_scope':'자료의 관찰을 참고한 작성자의 설계. 자동 학습·작곡가 스타일 재현 아님.'}
    dump(folder/'development_story.json',report)
    esc=lambda x:html.escape(str(x));cards=[]
    for row,stage in zip(trace['stages'],recipe['stages']):
        found=[u for u in uses if row['bars'][0]<=u['bar']<=row['bars'][1]]
        claims=''.join(f"<li>{u['bar']}마디 · {esc(u['label'])} — 음표 대조 완료</li>" for u in found)
        cards.append(f"<article><div class='range'>{row['bars'][0]}–{row['bars'][1]}마디</div><h2>{esc(stage['label'])}</h2><p>{esc(row['decision'])}</p><ul>{claims}</ul><p class='small'>실제 발음 {row['actual']['attacks']}회 · 선율 쉼 {esc(row['actual']['rest_quarters'])}박(4분음표)</p><details><summary>참고한 자료와 작성 판단</summary><p>{esc(row['observation'])}</p><p>참조: {esc(', '.join(row['reference_ids']))}</p></details></article>")
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>주제의 여정 | MUSICANOTE</title><style>*{box-sizing:border-box}body{font:16px/1.75 system-ui;background:#f5f1e8;color:#263c34;margin:0}main{max-width:1040px;margin:auto;padding:40px 24px}h1{font-size:40px}h2{font-size:23px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{padding:24px;background:#fffefa;border:1px solid #d4dccf;border-radius:15px}.range,.small{font-size:14px;color:#586e60}a{color:#315d45}nav{display:flex;flex-wrap:wrap;gap:20px;margin:24px 0}@media(max-width:680px){.grid{grid-template-columns:1fr}main{padding:24px 16px}}</style><main><a href="index.html">← 두 악보와 피아노</a><h1>작은 주제의 여정</h1><p>처음의 음형이 어떻게 응답하고 멀어졌다가 돌아오는지 살펴보세요.<br>표시한 변형은 실제 악보의 음·음가·쉼과 대조했습니다.</p><nav><a href="piano_solo.html">피아노로 듣기</a><a href="melody_harmony.html">멜로디 + 상세 화성</a><a href="inner_voices.html">종지의 내성</a><a href="tonal_development.html">조성 이동 근거</a></nav><section class="grid">CARDS</section><footer><p>SCOPE</p><a href="development_story.json">발전 검증 기록</a> · <a href="references.json">프레이즈 참조·출처</a></footer></main></html>'''
    for optional in ['inner_voices','tonal_development']:
        if not (folder/(optional+'.html')).is_file():
            import re
            page=re.sub(r'<a href="'+optional+r'\.html">[^<]+</a>','',page)
    attribution=f"{refs.get('attribution','')} · {refs.get('license','')} · {refs.get('source_url','')}"
    (folder/'development_story.html').write_text(page.replace('CARDS',''.join(cards)).replace('SCOPE',esc(report['reference_scope'])+'<br>'+esc(attribution)),encoding='utf-8')
    index=folder/'index.html';text=index.read_text(encoding='utf-8')
    if 'href="development_story.html"' not in text:index.write_text(text.replace('<main>','<main><nav><a href="development_story.html">모티프가 발전하는 과정 →</a></nav>',1),encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description='실제 악보와 모티프 발전 주장 대조');p.add_argument('--piece',type=Path,required=True);a=p.parse_args();r=run(a.piece);print(json.dumps({'claims':len(r['claims']),'stages':len(r['stages'])},ensure_ascii=False))
