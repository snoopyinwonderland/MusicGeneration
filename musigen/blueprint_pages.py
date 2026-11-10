"""기존 감상 화면을 재사용하는 상세 화성 출력의 두 보기."""
import copy
import html
import os
import shutil
from fractions import Fraction
from pathlib import Path
from musigen.expression import playback
from musigen.listen import _write_page, _instrumentation


def write_pages(piece,plan,details,report,out,checks):
    out=Path(out)
    runtime=Path(os.environ.get('MUSICOMP_ROOT',''))/'node_modules/verovio/dist/verovio-toolkit-wasm.js'
    if runtime.exists():
        (out/'assets').mkdir(exist_ok=True)
        shutil.copyfile(runtime,out/'assets/verovio.js')
    entries=[]
    for key,title,path in [('melody_harmony','멜로디 + 상세 화성',report['melody_harmony']),
                           ('piano_solo','피아노 솔로',report.get('piano_solo'))]:
        if not path:continue
        xml=Path(path).read_text(encoding='utf-8')
        design=copy.deepcopy(plan['design']);design['title']+=' · '+title
        instrumentation=_instrumentation(xml)
        if key=='melody_harmony':instrumentation['label']='피아노 · 화성 요약'
        # musicomp writes separate RH/LH parts, whereas the lead has two staves in one part.
        if key=='piano_solo' and len(instrumentation['staffs'])==2:
            instrumentation['staffs']['2']['lh']=True
        perf=playback(piece)
        check_view=checks
        if key=='piano_solo':
            # Do not present source-score checks as arranged-score checks.
            perf={'bars':perf['bars'],'dynamics':[],'expression':[],'articulations':[]}
            check_view={'stats':{'seconds':float(piece.bars*piece.bar_len)*60/piece.qpm},'sections':[],
                        'errors':[],'warnings':['편곡 검사는 별도 arrangement/report.json 참조. 이 화면의 표현 재생은 기본값입니다.'],'notes':[]}
        harmony=[{**e['roman'],'q':float(Fraction(e['onset'])),
                  'bar':e['bar'],'symbol':e['symbol']} for e in details['events']]
        pdf=out/(key+'.pdf')
        entry={'piece':key,'xml':xml,'design':design,'checks':check_view,
               'info':{'version':'v001','reason':f'짧은 모티프의 {piece.bars}마디 발전 및 상세 화성 전달 검증','preserve':[],'preserve_broken':[]},
               'performance':perf,'instrumentation':instrumentation,'harmony':harmony,
               '_pdf':str(pdf) if pdf.is_file() else None}
        target=out/(key+'.html')
        _write_page([entry],target,None,True)
        text=target.read_text(encoding='utf-8')
        text=text.replace('요청 원문:', '제작 내용:')
        if runtime.exists():text=text.replace('https://cdn.jsdelivr.net/npm/verovio@6.3.0/dist/verovio-toolkit-wasm.js','assets/verovio.js')
        text=text.replace('<body>','<body><nav style="padding:12px;background:#e6eee5"><a href="index.html">두 악보와 화성 설계표</a> · <a href="harmony.json" download>상세 화성 JSON 받기</a></nav>')
        target.write_text(text,encoding='utf-8')
        entries.append((title,target.name))
    esc=lambda v:html.escape(str(v))
    functions={'tonic':'으뜸 기능','predominant':'딸림 준비','dominant':'딸림 기능','other':'기타'}
    rows=''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in
        (e['bar'],e['offset'],e['duration'],e['symbol'],e['roman']['display'],e['bass'],
         ' · '.join(e['tones']),' · '.join(e['voicing']),functions.get(e.get('function'),''),e.get('cadence','')))+'</tr>' for e in details['events'])
    links=''.join('<a class="button" href="'+url+'">'+esc(title)+' 악보·듣기</a>' for title,url in entries)
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MUSICANOTE · 모티프에서 한 곡으로</title>
<style>body{background:#f5f3ed;color:#243c35;font:16px/1.6 system-ui;margin:0}main{max-width:1180px;margin:auto;padding:28px}h1{font-size:32px}.button{display:inline-block;padding:14px;background:#285c4b;color:white;border-radius:8px;margin:8px 12px 8px 0;text-decoration:none}.scroll{overflow:auto;background:white;padding:16px;border-radius:12px}table{border-collapse:collapse;white-space:nowrap;width:100%;font-size:14px}th,td{padding:10px;border-bottom:1px solid #ddd;text-align:left}.note{background:#e4ece5;padding:16px;border-radius:8px}</style><main>
<small>MUSICANOTE Virtual Composer</small><h1>모티프에서 한 곡으로</h1><h2>'''+esc(plan['design']['title'])+'''</h2><p>입력 모티프 → 구절별 발전 설계 → 멜로디와 상세 화성 → 기존 musicomp 피아노 편곡</p>'''+links+'''
<p class="note">작곡자가 작성한 첫 초안입니다. 화성 악보는 왼손에 전체 구성음을 펼쳐 보이는 설계용 악보이고, 피아노 솔로는 기존 반주 라이브러리로 만든 연주용 편곡입니다. 종지·기능은 작곡 의도이며 자동 분석의 정답 라벨이 아닙니다.</p>
<p><a href="melody_harmony.musicxml" download>화성 악보 MusicXML</a> · <a href="melody_harmony.mid" download>MIDI</a> · <a href="harmony.json" download>상세 화성 JSON</a> · <a href="development.json" download>발전 설계 JSON</a></p>
<h2>왼손 화성 설계</h2><p>시작과 길이는 4분음표 단위입니다. 시작 0은 해당 마디의 첫 박입니다. 선율과의 관계·출처·구절 계획은 JSON에 포함합니다.</p><div class="scroll"><table><thead><tr>'''+''.join('<th>'+x+'</th>' for x in ['마디','시작','길이','코드','로마자','베이스','전체 구성음','왼손 배치','기능 의도','종지 의도'])+'''</tr></thead><tbody>'''+rows+'''</tbody></table></div></main></html>'''
    (out/'index.html').write_text(page,encoding='utf-8')
    return str(out/'index.html')
