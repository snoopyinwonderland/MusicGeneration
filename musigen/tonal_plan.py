"""Check explicit tonal decisions against source evidence and the written score."""
import copy
from fractions import Fraction as F
import html
import re
from musigen.blueprint import digest
from musigen.functional_harmony import resolve
from musigen.piece import parse_key
from musigen.tonal_reference import get_reference, key_name


def key_data(text):
    if not isinstance(text,str) or not re.fullmatch(r'[A-G](?:bb|##|b|#)? (major|minor)',text):
        raise ValueError('조성은 C major / F# minor 형식으로 지정하세요')
    k=parse_key(text)
    return k,{'fifths':k.tonic_tpc,'minor':k.minor,'name':key_name(k.tonic_tpc,k.minor)}


def validate(recipe,library,piece,harmony):
    moves=[m for s in recipe['stages'] for m in s.get('tonal_moves',[])]
    if not moves:return []
    if library is None or recipe.get('tonal_library_sha256')!=digest(library):
        raise ValueError('국소 조성 참조 파일과 설계의 지문이 일치해야 합니다')
    events=harmony['events'];trace=[];offset=0;seen=set()
    for stage in recipe['stages']:
        for move in stage.get('tonal_moves',[]):
            n=move['at_bar'];kind=move['kind']
            if type(n)is not int or not 1<=n<=stage['length']:raise ValueError('조성 결정의 구간 안 마디 오류')
            bar=offset+n;off=F(move.get('offset','0'))
            if off<0 or off>=piece.bar_len or (bar,off) in seen:raise ValueError('조성 결정의 시각 중복·범위 오류')
            seen.add((bar,off))
            if not move.get('observation') or not move.get('decision'):raise ValueError('조성 자료의 관찰과 작성 결정을 구별하세요')
            ref,work=get_reference(library,move['reference_id'])
            if kind!=ref['kind'] or kind not in ('local_key_change','tonicization'):raise ValueError('전조와 으뜸화의 참조 종류를 바꿀 수 없습니다')
            fk,from_key=key_data(move['from_key']);tk,to_key=key_data(move['to_key'])
            if (from_key['minor'],to_key['minor'],to_key['fifths']-from_key['fifths'])!=(ref['from_key']['minor'],ref['to_key']['minor'],ref['to_key']['fifths']-ref['from_key']['fifths']):
                raise ValueError('참조의 장단조·철자 관계를 같은 이조로 옮겨야 합니다')
            if from_key==to_key:raise ValueError('조성 이동의 시작과 목적이 같습니다')
            matches=[e for e in events if e['bar']==bar and F(e['offset'])==off]
            if len(matches)!=1:raise ValueError('조성 결정 시각에 명시적 화성 사건이 필요합니다')
            event=matches[0]
            if kind=='local_key_change':
                if off or bar<=1 or piece.bar_keys[bar-1]!=fk or piece.bar_keys[bar]!=tk:
                    raise ValueError('설계한 국소 조성 변화가 실제 마디 조성과 다릅니다')
            else:
                intent=event.get('functional_intent') or {}
                if piece.bar_keys[bar]!=fk or intent.get('kind')!='secondary' or intent.get('target_tpc')!=tk.tonic_tpc or str(intent.get('target_key','')).endswith('minor')!=tk.minor:
                    raise ValueError('으뜸화는 현재 국소 조성을 유지하는 실제 세컨더리 화음과 맞아야 합니다')
            evidence={}
            if move.get('pivot'):
                if kind!='local_key_change':raise ValueError('피벗은 국소 조성 변화에 지정하세요')
                pivot=move['pivot'];pb=pivot['bar'];po=F(pivot.get('offset','0'))
                if type(pb)is not int or not 1<=pb<bar or piece.bar_keys[pb]!=fk:raise ValueError('피벗은 앞 조성의 선행 마디에 있어야 합니다')
                found=[e for e in events if e['bar']==pb and F(e['offset'])==po]
                if len(found)!=1:raise ValueError('피벗 시각의 화성이 없습니다')
                a,_,_=resolve({'figure':pivot['from_figure']},fk);b,_,_=resolve({'figure':pivot['to_figure']},tk)
                actual=dict(piece.analysis_chords)[F(found[0]['onset'])]
                signatures=[({t for pc,t in ch.tones},ch.bass_tpc) for ch in (a,b,actual)]
                if not signatures[0]==signatures[1]==signatures[2]:raise ValueError('피벗의 두 해석과 실제 구성음·베이스가 다릅니다')
                evidence['pivot']={**copy.deepcopy(pivot),'tones':found[0]['tones'],'bass':found[0]['bass'],'exact_spelling_match':True}
            if move.get('confirmation'):
                c=move['confirmation'];cb=c['bar']
                if kind!='local_key_change' or type(cb)is not int or not bar<=cb<=piece.bars or any(piece.bar_keys[b]!=tk for b in range(bar,cb+1)):
                    raise ValueError('종지 확인은 도착한 국소 조성 구간 안이어야 합니다')
                found=[e for e in events if e['bar']==cb and e.get('cadence')==c['cadence']]
                if len(found)!=1:raise ValueError('지정한 종지 의도가 실제 화성 설계에 없습니다')
                evidence['confirmation']={**c,'status':'composer_cadence_intent_not_independent_cadence_detection'}
            trace.append({'bar':bar,'offset':str(off),'kind':kind,'from_key':from_key,'to_key':to_key,
                'observation':move['observation'],'decision':move['decision'],'evidence':evidence,
                'reference':copy.deepcopy(ref),'source':copy.deepcopy(work),
                'actual_harmony':{k:event.get(k) for k in ('onset','symbol','figure','key','tones','bass','functional_intent','resolution_check')},
                'status':'reference_relation_and_authored_score_checked_not_listener_approved'})
        offset+=stage['length']
    return trace


def write_page(trace,library,out):
    esc=lambda x:html.escape(str(x))
    names={'local_key_change':'국소 조성 변화','tonicization':'일시적 으뜸화'}
    cards=[]
    for row in trace:
        r=row['reference'];source=r['source_event'];w=row['source']
        pivot=row['evidence'].get('pivot');confirm=row['evidence'].get('confirmation')
        evidence=(f'<p>공통화음: {pivot["bar"]}마디 · {esc(pivot["from_figure"])} → {esc(pivot["to_figure"])} · {esc(" · ".join(pivot["tones"]))}. 구성음·철자·베이스 일치.</p>' if pivot else '')
        if confirm:evidence+=f'<p>도착 조성의 {confirm["bar"]}마디 종지 계획: {esc(confirm["cadence"])}. 독립적인 종지 판정은 아닙니다.</p>'
        cards.append(f'<article><h2>{row["bar"]}마디 · {names[row["kind"]]}</h2><p class="keys">{esc(row["from_key"]["name"])} → {esc(row["to_key"]["name"])}</p><p><strong>자료 관찰</strong> {esc(row["observation"])}</p><p><strong>이번 곡의 결정</strong> {esc(row["decision"])}</p>{evidence}<details><summary>원 주석과 출처</summary><p>{esc(w["id"])} · 인쇄 {esc(source["mn"])}마디 / MC {esc(source["mc"])} · 원 주석 {esc(source["label"])} · TSV {source["source_line"]}행</p><p>원 조성 관계: {esc(r["from_key"]["name"])} → {esc(r["to_key"]["name"])}</p><p><a href="{esc(w["source_url"])}">DCML 원 자료</a> · {esc(w["license"])}</p></details></article>')
    s=library['summary'];excluded=''.join(f'<li>{esc(w["id"])}: {esc(w.get("reason"))}</li>' for w in library['works'] if w['status']!='validated')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>조성 이동과 모티프 발전 | MUSICANOTE</title><style>*{box-sizing:border-box}body{background:#f3f1e9;color:#243b32;font:16px/1.75 system-ui;margin:0}main{max-width:1000px;padding:38px 24px;margin:auto}h1{font-size:clamp(30px,5vw,42px);line-height:1.3}h2{font-size:23px}.brand{font-size:12px;letter-spacing:.13em}article{background:#fffefa;padding:24px;border:1px solid #d3dccd;border-radius:16px;margin:24px 0}.keys{font-size:25px;color:#315c43}a{color:#315c43}nav{display:flex;flex-wrap:wrap;gap:22px}details{font-size:14px}footer{font-size:14px;overflow-wrap:anywhere}</style><main><div class="brand">MUSICANOTE VIRTUAL COMPOSER</div><h1>조성 이동을 모티프 발전에 연결했습니다</h1><p>세컨더리 화음은 현재 조성 안에서 잠시 다른 화음을 향하고, 국소 조성 변화는 별도 구간으로 설계합니다. 아래 참조 관계와 실제 악보의 조성·화성·공통화음을 대조했습니다.</p><nav><a href="index.html">작품과 두 악보</a><a href="tonal_references.json" download>검증한 참조 JSON</a><a href="development_trace.json" download>발전 설계 검증 JSON</a></nav>CARDS<footer><p>COVERAGE</p><p>검증 범위: 표의 마디·음표·화성 시각 일치 및 원 MuseScore의 마디/보표/성부별 주석 일치. 원 악보의 모든 음표 시각을 재해석하거나 전조의 청취 타당성을 인증한 것은 아닙니다.</p><details><summary>보류한 자료</summary><ul>EXCLUDED</ul></details><p>DCML 저자 · CC BY-NC-SA 4.0 · 선택 참조 기능. 기본 생성·자동 스타일 학습·사용자 선택 기록은 바꾸지 않았습니다.</p></footer></main></html>'''
    page=page.replace('CARDS',''.join(cards)).replace('COVERAGE',esc(f"지정 {s['attempted_works']}악장 중 {s['validated_works']}개 검증 · 국소 조성 변화 {s['reference_counts'].get('local_key_change',0)}곳 · 으뜸화 {s['reference_counts'].get('tonicization',0)}곳. 이번 곡에는 작성자가 위 {len(trace)}곳을 참조했습니다.")).replace('EXCLUDED',excluded)
    (out/'tonal_development.html').write_text(page,encoding='utf-8')
