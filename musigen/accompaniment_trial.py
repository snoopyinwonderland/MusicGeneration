"""Audit opt-in accompaniment on fixed authored inputs across explicitly chosen cases."""
import argparse
import copy
import html
import json
import re
from pathlib import Path
from musigen.blueprint import digest,dump
from musigen.accompaniment_review import compare,write_page


def controlled_inputs(a,b):
    """Only the declared accompaniment plan may differ; no manual LH confound."""
    a,b=copy.deepcopy(a),copy.deepcopy(b)
    if a['development']['design'].get('accompaniment_plan'):
        raise ValueError('A에는 반주 계획 옵션이 없어야 합니다')
    policy=b['development']['design'].pop('accompaniment_plan',None)
    if not policy:raise ValueError('B에 명시한 반주 계획이 필요합니다')
    a['development']['design'].pop('accompaniment_plan',None)
    if a!=b:raise ValueError('모티프·설계·직접 반주·표현 등 작성 입력이 달라 옵션만의 비교가 아닙니다')
    if 'corpus_accompaniment' in a['realization']['score']:
        raise ValueError('작성 입력에 기존 자료 선택 스냅샷을 넣을 수 없습니다')
    return {'authored_inputs_sha256':digest(a),'changed_input':'design.accompaniment_plan',
            'policy_sha256':digest(policy),'scope':'fixed authored LH as well as melody, harmony and expression'}


def fixed_sources(a,b):
    fields=('engine_sha256','library','pacing_model','grade')
    if any(k not in a or k not in b or a[k]!=b[k] for k in fields):
        raise ValueError('A/B 자료·검색기·밀도 모델·급수가 다릅니다')
    return {k:a[k] for k in fields}


def audit_case(folder):
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    sides=[folder/n for n in ('baseline','planned')]
    inputs=[{n:read(p/(n+'.json')) for n in ('motif','development','realization')} for p in sides]
    controls=controlled_inputs(*inputs)
    reports=[read(p/'accompaniment_report.json') for p in sides]
    sources=fixed_sources(*reports)
    comparison=compare(*sides)
    checks={side:{kind:{k:read(folder/side/(kind+'_checks.json'))[k] for k in ('errors','warnings')}
                  for kind in ('melody_harmony','piano_solo')} for side in ('baseline','planned')}
    summary={'title':inputs[0]['development']['design']['title'],
             'meter':inputs[0]['development']['design']['basics']['meter'],
             'bars':len(comparison['after']['bars']),'controls':controls,'sources':sources,
             'changed_lh_bars':comparison['changed_lh_bars'],'checks':checks,
             'before':comparison['before']['summary'],'after':comparison['after']['summary'],
             'applied_bars':{side:r['applied_bars'] for side,r in zip(('baseline','planned'),reports)},
             'candidate_preflight':reports[1].get('candidate_preflight'),
             'pedal_spans':{side:read(folder/side/'result.json')['pedal_spans'] for side in ('baseline','planned')},
             'status':'awaiting_listener_feedback','user_selection':None}
    dump(folder/'comparison.json',comparison);dump(folder/'trial_case.json',summary)
    write_page(comparison,folder)
    esc=lambda x:html.escape(str(x))
    warnings=[]
    for side,label in [('baseline','A'),('planned','B')]:
        for kind,title in [('melody_harmony','멜로디+화성'),('piano_solo','피아노 솔로')]:
            for level in ('errors','warnings'):
                warnings.extend(f'<li>{label} {title}: {esc(w)}</li>' for w in checks[side][kind][level])
    banner='<aside><h2>같은 작성 입력의 옵션 비교</h2><p>직접 쓴 왼손까지 고정하고 B에만 반주 계획을 추가했습니다. B의 요구 미충족 마디: '+esc(summary['after']['unmet_plan_bars'] or '없음')+'</p>'
    banner+='<details><summary>자동 검사 경고·오류</summary><ul>'+(''.join(warnings) or '<li>없음</li>')+'</ul></details><a href="trial_case.json">입력 통제와 자료 지문</a> · <a href="../index.html">두 시험곡 목록</a></aside>'
    p=folder/'index.html';p.write_text(p.read_text(encoding='utf-8').replace('<section class="cards">',banner+'<section class="cards">'),encoding='utf-8')
    return summary


def run(root):
    root=Path(root);manifest=json.loads((root/'trial_input.json').read_text(encoding='utf-8'))
    cases=manifest['cases'];ids=[r['id'] for r in cases]
    if not ids or len(set(ids))!=len(ids) or any(not isinstance(i,str) or not re.fullmatch('[a-z][a-z0-9_]*',i) for i in ids):
        raise ValueError('서로 다른 안전한 시험 id가 필요합니다')
    result={'request':manifest['request'],'status':'technical_observations_not_quality_ranking','cases':{}}
    for row in cases:result['cases'][row['id']]=audit_case(root/row['id'])
    dump(root/'trial_report.json',result)
    esc=lambda x:html.escape(str(x));cards=[]
    for row in cases:
        r=result['cases'][row['id']];a,b=r['before'],r['after']
        warning_counts=[len(r['checks'][side]['piano_solo']['warnings']) for side in ('baseline','planned')]
        cards.append(f'''<article><div class="meter">{esc(r['meter'])} · {r['bars']}마디</div><h2>{esc(r['title'])}</h2><p>{esc(row['focus'])}</p>
<a class="button" href="{row['id']}/index.html">A/B 악보와 피아노 듣기 →</a><p>왼손 3음·7음 생략 구간: {a['spans_missing_core_tones']}/{a['harmony_spans']} → {b['spans_missing_core_tones']}/{b['harmony_spans']}<br>B 요구 미충족 마디: {esc(b['unmet_plan_bars'] or '없음')}<br>솔로 자동 검사 경고 A → B: {warning_counts[0]} → {warning_counts[1]}</p></article>''')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>두 박자의 반주 | MUSICANOTE</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f1e8;color:#253c34;font:16px/1.75 system-ui}main{max-width:1120px;margin:auto;padding:46px 26px}.brand{font-size:12px;letter-spacing:.12em}h1{font-size:clamp(30px,5vw,44px);line-height:1.3}h2{font-size:24px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}article,aside{background:#fffefa;border:1px solid #d4dccf;border-radius:16px;padding:25px;margin:18px 0}.meter{color:#5c715e;font-size:14px}.button{display:inline-block;background:#315d45;color:white;text-decoration:none;padding:10px 17px;border-radius:8px}a{color:#285f48}footer{font-size:14px}@media(max-width:700px){.grid{grid-template-columns:1fr;gap:0}main{padding:26px 16px}}
</style><main><div class="brand">MUSICANOTE VIRTUAL COMPOSER / ACCOMPANIMENT STUDIES</div><h1>두 박자에서 살펴본 반주</h1><p>서정적인 3/4와 쉼으로 시작하는 4/4. 각 곡의 선율·화성·직접 반주를 고정하고,<br>구간별 반주 조건을 더했을 때 무엇이 달라지는지 비교했습니다.</p><section class="grid">CARDS</section><aside><h2>들어 보는 순서</h2><p>A는 기존 자료 검색, B는 같은 검색에 구성음·시작 음역 조건을 더한 판입니다. 각 곡의 1–4마디에서 시작해 주제가 길어지는 중간과 마지막 종결을 비교해 보세요.</p><p>숫자는 왼손의 각 화음 구간에서 3음·7음이 한 번도 울리지 않은 경우를 셉니다. 전체 악보의 화음 부족이나 음악적 오류 판정은 아닙니다. 자동 검사 경고와 조건 미충족 마디도 각 비교 화면에 표시합니다.</p><p>모티프 발전과 화성은 작성자의 설계이며, 두 사례만으로 일반적인 품질이나 작곡가 스타일을 입증하지 않습니다. 아직 선택된 판은 없습니다.</p></aside><footer><a href="trial_report.json">시험 조건·자료·검증 기록</a><p>각 악보에서 MusicXML·PDF를 받을 수 있습니다.</p></footer></main></html>'''.replace('CARDS',''.join(cards))
    (root/'index.html').write_text(page,encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    a=p.parse_args();r=run(a.root)
    print(json.dumps({k:{'before':v['before'],'after':v['after']} for k,v in r['cases'].items()},ensure_ascii=False))
