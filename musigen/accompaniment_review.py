"""A/B observations with exact melody/harmony/expression controls and frozen LH."""
import argparse
import hashlib
import html
import json
from pathlib import Path
from musigen.blueprint import prepare,dump
from musigen.blueprint_solo import realize
from musigen.development_comparison import signature,verify_written
from musigen.accompaniment_context import observe


def load(folder):
    folder=Path(folder);read=lambda n:json.loads((folder/n).read_text(encoding='utf-8'))
    plan=read('development.json');lead,_,harmony=prepare(read('motif.json'),plan)
    solo,_=realize(lead,plan,read('solo_score.json'))
    verify_written(solo,folder/'piano_solo.musicxml')
    return solo,plan,observe(solo,plan['design'])


def compare(before,after):
    a,pa,oa=load(before);b,pb,ob=load(after)
    for name,good in [('주선율',signature(a,'rh')==signature(b,'rh')),('조성',a.bar_keys==b.bar_keys),
        ('화성',a.analysis_chords==b.analysis_chords),('박자·빠르기',(a.meter,a.qpm,a.bar_len,a.bars)==(b.meter,b.qpm,b.bar_len,b.bars)),
        ('표현',(a.expression,a.directions)==(b.expression,b.directions))]:
        if not good:raise ValueError(name+'가 바뀌어 반주 비교로 표시할 수 없습니다')
    changed=[n for n in range(1,a.bars+1) if signature(a,'lh',a.bar_start(n),a.bar_end(n))!=signature(b,'lh',b.bar_start(n),b.bar_end(n))]
    return {'status':'awaiting_listener_feedback','controls':'melody, harmony, local keys, meter, tempo, expression exact',
        'changed_lh_bars':changed,'before':oa,'after':ob,
        'files':{key:{'path':str(Path(folder).resolve()),'piano_solo_sha256':hashlib.sha256((Path(folder)/'piano_solo.musicxml').read_bytes()).hexdigest()} for key,folder in [('before',before),('after',after)]}}


def write_page(report,out):
    esc=lambda x:html.escape(str(x));rows=[]
    for a,b in zip(report['before']['bars'],report['after']['bars']):
        omission=lambda r:' / '.join(h['symbol']+': '+', '.join(h['missing_core_tones']) for h in r['harmony'] if h['missing_core_tones']) or '없음'
        bass=lambda r:r['first_attack']['bass'] if r['first_attack'] else '쉼'
        rows.append(f'<tr><td>{a["bar"]}</td><td>{a["attacks"]} → {b["attacks"]}</td><td>{esc(bass(a))} → {esc(bass(b))}</td><td>{esc(omission(a))}</td><td>{esc(omission(b))}</td><td>{esc(b["trailing_rest"])}</td></tr>')
    cards=[]
    for folder,label,desc in [('baseline','A · 기존 반주','비교 기준이 되는 반주입니다.'),('planned','B · 구간별 반주 계획','아래의 작성 계획과 실제로 연주되는 음표를 함께 확인할 수 있습니다.')]:
        cards.append(f'<article><h2>{label}</h2><p>{desc}</p><a class="button" href="{folder}/piano_solo.html">피아노로 듣기 · 악보 보기 →</a><p><a href="{folder}/piano_solo.musicxml" download>MusicXML 받기</a> · <a href="{folder}/piano_solo.pdf" download>PDF 받기</a></p></article>')
    plans=[]
    seen=set()
    for b in report['after']['bars']:
        p=b['plan']
        if p and tuple(p['bars']) not in seen:
            seen.add(tuple(p['bars']));plans.append(f'<li><strong>{p["bars"][0]}–{p["bars"][1]}마디 · {esc(p["role"])}</strong><br>{esc(p["decision"])}</li>')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>프레이즈와 반주 | MUSICANOTE</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f2e9;color:#243b32;font:16px/1.75 system-ui}main{max-width:1100px;margin:auto;padding:44px 24px}.brand{font-size:12px;letter-spacing:.13em}h1{font-size:clamp(30px,5vw,46px);line-height:1.3}.intro{max-width:780px}a{color:#285f48}.cards{display:grid;grid-template-columns:1fr 1fr;gap:22px}article,aside{background:#fffefa;border:1px solid #d2dacd;border-radius:16px;padding:26px;margin:20px 0}.button{font-weight:700}h2{font-size:23px}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px;min-width:730px}td,th{text-align:left;padding:10px;border-bottom:1px solid #dce1d5}li{margin:14px 0}.note,footer{font-size:14px;color:#526159}footer{overflow-wrap:anywhere}@media(max-width:700px){.cards{grid-template-columns:1fr;gap:0}main{padding:24px 16px}}
</style><main><div class="brand">MUSICANOTE VIRTUAL COMPOSER / ACCOMPANIMENT STUDY</div><h1>같은 선율, 다른 반주의 호흡</h1><p class="intro">멜로디·화성·조성·빠르기·셈여림은 같습니다. 반주의 움직임과 화음 배치를 비교해 보세요. 표현 지시도 동일하게 유지했습니다.</p><section class="cards">CARDS</section><aside><h2>들어 볼 곳</h2><p>아래 구간별 계획의 시작과 끝을 비교해 보세요. 낮은 음역의 연결, 주제 아래의 쉼, 종결의 균형을 들어 볼 수 있습니다.</p><p>왼손 변경 마디: CHANGED. 선율·상세 화성 악보는 두 버전이 같습니다.</p><a href="baseline/melody_harmony.html">공통 멜로디 + 상세 화성</a> · <a href="baseline/melody_harmony.musicxml" download>XML</a> · <a href="baseline/melody_harmony.pdf" download>PDF</a></aside><h2>구간별 작성 계획</h2><ol>PLANS</ol><h2>실제로 울리는 반주 확인</h2><p class="note">‘생략’은 각 화음 구간의 왼손에서 3음·7음이 한 번도 울리지 않은 경우입니다. 오른손을 포함한 전체 화음의 부족이나 음악적 오류를 뜻하지 않습니다. 최저음은 마디 첫 발음의 MIDI 번호이며 펼침화음의 실제 베이스 성부를 추정한 값은 아닙니다.</p><div class="table"><table><thead><tr><th>마디</th><th>발음 수 A → B</th><th>첫 최저음 A → B</th><th>A의 생략</th><th>B의 생략</th><th>B의 끝 쉼(4분음표)</th></tr></thead><tbody>ROWS</tbody></table></div><footer><p>기술 검증을 마친 비교 초안이며 청취 평가는 아직 없습니다. 자료를 적용하지 못한 마디는 작성한 반주를 유지하고 이유를 남겼습니다.</p><a href="comparison.json">전후 검증 JSON</a> · <a href="planned/accompaniment_report.json">반주 자료·선택 및 유지 사유</a> · <a href="planned/tonal_development.html">국소 조성 근거</a></footer></main></html>'''
    for token,value in [('CARDS',''.join(cards)),('CHANGED',esc('·'.join(map(str,report['changed_lh_bars'])))),('PLANS',''.join(plans)),('ROWS',''.join(rows))]:page=page.replace(token,value)
    if not (out/'planned/tonal_development.html').is_file():
        page=page.replace(' · <a href="planned/tonal_development.html">국소 조성 근거</a>','')
    (out/'index.html').write_text(page,encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();report=compare(a.before,a.after)
    # Existing listening folders must be explicitly prepared under the report root.
    if a.before.resolve()!= (a.out/'baseline').resolve() or a.after.resolve()!=(a.out/'planned').resolve():raise ValueError('비교 폴더는 출력 아래 baseline과 planned로 준비하세요')
    if (a.out/'index.html').exists():raise ValueError('새 비교 페이지를 지정하세요')
    dump(a.out/'comparison.json',report);write_page(report,a.out)
    print(json.dumps({'changed_lh_bars':report['changed_lh_bars'],'controls':report['controls']},ensure_ascii=False))
