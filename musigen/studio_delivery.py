"""Bind an authored, verified score revision to a local studio request. No model call."""
import argparse
import hashlib
import html
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from musigen.blueprint import digest, dump, prepare, verify_roundtrip
from musigen.studio import validate_request

REQUEST_ID=re.compile(r'request-[0-9a-f]{32}')
REVISION=re.compile(r'v[0-9]{3,}')
TITLES={'melody_harmony':'멜로디 + 상세 왼손 화성','piano_solo':'피아노 솔로'}
JSON_FILES=('motif.json','development.json','solo_score.json','recipe.json','references.json',
            'development_trace.json','tonal_references.json','realization.json','feedback.json',
            'accompaniment_report.json','accompaniment_context.json','performed_harmony.json',
            'inner_voice_plan.json')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contained(root,relative):
    """Only ordinary files/directories under the declared root; reject link ancestors."""
    root=Path(root).resolve();part=Path(relative)
    if part.is_absolute() or '..' in part.parts:raise ValueError('잘못된 상대 경로입니다')
    dest=root/part
    if not dest.resolve().is_relative_to(root):raise ValueError('출력 폴더 밖의 경로입니다')
    for p in [dest,*dest.parents]:
        if p==root:break
        if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):raise ValueError('연결 경로는 사용하지 않습니다')
    return dest


def request_folder(root,request_id):
    if not isinstance(request_id,str) or not REQUEST_ID.fullmatch(request_id):raise ValueError('요청 ID를 확인하세요')
    folder=contained(root,'requests/'+request_id)
    if not folder.is_dir():raise ValueError('저장한 요청을 찾지 못했습니다')
    return folder


def verify_request(data,motif,plan,lead,details):
    validate_request(data)
    if digest(data['motif'])!=digest(motif):raise ValueError('저장한 모티프와 결과의 입력이 다릅니다')
    p=data['preferences'];basics=plan['design']['basics']
    actual={'key':basics['key']+' '+basics['mode'],'meter':lead.meter,'tempo':lead.qpm,'bars':lead.bars}
    for name,value in actual.items():
        if p[name]!=value:raise ValueError(f'요청의 {name}와 결과가 다릅니다: {p[name]} / {value}')
    if not p['modulation'] and len(details['key_plan'])>1:raise ValueError('요청에서 전조를 허용하지 않았습니다')
    from musigen.harmony_labels import label
    from musigen.functional_harmony import AUGMENTED
    for e,(_,ch) in zip(details['events'],lead.analysis_chords):
        intent=e.get('functional_intent') or {}
        if not p['augmented_sixth'] and ch.quality in AUGMENTED:raise ValueError('요청에서 증6화음을 허용하지 않았습니다')
        # Plain chord symbols also receive a secondary-function check; no hidden V/V via G7.
        secondary=intent.get('kind')=='secondary'
        if ch.quality not in AUGMENTED:secondary|='/' in label(ch,lead.bar_keys[e['bar']],secondary=True)['figure']
        if not p['secondary'] and secondary:raise ValueError('요청에서 세컨더리 화음을 허용하지 않았습니다')
    return actual


def verify_xml_metadata(piece,path):
    root=ET.parse(path).getroot();beats,unit=piece.meter.split('/')
    times=root.findall('.//attributes/time')
    if not times or any((t.findtext('beats'),t.findtext('beat-type'))!=(beats,unit) for t in times):
        raise ValueError('실제 MusicXML의 박자가 설계와 다릅니다')
    tempi=root.findall('.//sound[@tempo]')
    if not tempi or any(float(t.get('tempo'))!=piece.qpm for t in tempi):raise ValueError('실제 MusicXML의 빠르기가 설계와 다릅니다')
    if len(root.findall('./part'))!=1 or len(root.findall('./part/measure'))!=piece.bars:raise ValueError('실제 MusicXML의 마디 수가 다릅니다')


def verify_scores(folder,data):
    from musigen.blueprint_solo import realize
    from musigen.development_comparison import verify_written
    from musigen.checks import check
    motif,plan=read(folder/'motif.json'),read(folder/'development.json')
    lead,_,details=prepare(motif,plan)
    facts=verify_request(data,motif,plan,lead,details)
    pieces={'melody_harmony':lead}
    if 'piano_solo' in data['preferences']['outputs']:
        pieces['piano_solo']=realize(lead,plan,read(folder/'solo_score.json'))[0]
    checks={}
    for kind,piece in pieces.items():
        xml=folder/(kind+'.musicxml')
        verify_written(piece,xml);verify_roundtrip(piece,xml);verify_xml_metadata(piece,xml)
        checks[kind]=check(piece,plan['design'])
        if checks[kind]['errors']:raise ValueError(kind+': '+'; '.join(checks[kind]['errors']))
        if not (folder/(kind+'.pdf')).read_bytes().startswith(b'%PDF-'):raise ValueError('PDF 파일을 확인하세요')
    return plan,details,pieces,checks,facts


def write_result_pages(folder,plan,details,pieces,checks,request,revision):
    from musigen import MUSICOMP_ROOT
    from musigen.listen import _write_page, _instrumentation, VEROVIO_CDN
    from musigen.expression import playback
    from musigen.functional_harmony import AUGMENTED
    from fractions import Fraction
    (folder/'assets').mkdir()
    shutil.copyfile(MUSICOMP_ROOT/'node_modules/verovio/dist/verovio-toolkit-wasm.js',folder/'assets/verovio.js')
    esc=lambda x:html.escape(str(x));cards=[]
    for kind,piece in pieces.items():
        xml=(folder/(kind+'.musicxml')).read_text(encoding='utf-8')
        harmony=[{**e['roman'],'q':float(Fraction(e['onset'])),'bar':e['bar'],'symbol':e['symbol'],
            'symbol_display':e['roman']['display'] if e['quality'] in AUGMENTED else None} for e in details['events']]
        instrumentation=_instrumentation(xml);instrumentation['label']=TITLES[kind]
        entry={'piece':kind,'xml':xml,'design':plan['design'],'checks':checks[kind],
            'info':{'version':revision,'reason':request['preferences']['prompt'],'preserve':[],'preserve_broken':[]},
            'performance':playback(piece),'instrumentation':instrumentation,'harmony':harmony,'_pdf':str(folder/(kind+'.pdf'))}
        target=folder/(kind+'.html');_write_page([entry],target,None,True)
        text=target.read_text(encoding='utf-8').replace(VEROVIO_CDN,'assets/verovio.js')
        target.write_text(text.replace('<body>','<body><nav style="padding:12px 24px"><a href="index.html">← 요청과 두 악보</a></nav>'),encoding='utf-8')
        warnings=checks[kind]['warnings']
        cards.append(f'<article><h2>{TITLES[kind]}</h2><p><a href="{kind}.html">악보 보며 피아노로 듣기 →</a></p><p><a href="{kind}.musicxml" download>XML 받기</a> · <a href="{kind}.pdf" download>PDF 받기</a></p><p>자동 검사: 오류 0 · 경고 {len(warnings)}개</p>'+(''.join('<p class="note">'+esc(w)+'</p>' for w in warnings))+'</article>')
    (folder/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(plan['design']['title'])+' | MUSICANOTE</title><style>*{box-sizing:border-box}body{margin:0;background:#f4f2eb;color:#203e38;font:16px/1.7 system-ui}main{max-width:1000px;margin:auto;padding:36px 22px}a{color:#25664e}h1{font-size:38px}.scores{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{background:white;border:1px solid #dce4db;border-radius:14px;padding:24px}.note{font-size:13px}nav{display:flex;flex-wrap:wrap;gap:16px;margin:20px 0}@media(max-width:700px){.scores{grid-template-columns:1fr}}</style><main><a href="../../../../index.html#requests">← 모티프 입력과 요청 목록</a><h1>'+esc(plan['design']['title'])+'</h1><p>완성 초안 · 청취 검수 전. 요청의 모티프·조성·박자·빠르기·마디 수를 실제 악보와 확인했습니다.</p><p>'+esc(plan['design'].get('impression',{}).get('arc',''))+'</p><section class="scores">'+''.join(cards)+'</section><nav><a href="harmony.json" download>상세 왼손 화성 JSON</a><a href="../../request.json">원래 요청</a><a href="delivery.json">전달 검증 기록</a></nav></main></html>',encoding='utf-8')


def publish(root,request_id,piece):
    root=Path(root).resolve();folder=request_folder(root,request_id);source=Path(piece).resolve()
    request_path=contained(folder,'request.json');data=validate_request(read(request_path));request_hash=sha(request_path)
    lock=contained(folder,'.delivery.lock')
    try:handle=lock.open('x')
    except FileExistsError:raise ValueError('이 요청의 전달 작업이 진행 중입니다') from None
    try:
        results=contained(folder,'results');results.mkdir(exist_ok=True)
        used=[int(p.name[1:]) for p in results.iterdir() if REVISION.fullmatch(p.name)]
        revision=f'v{max(used,default=0)+1:03d}';target=contained(results,revision)
        with tempfile.TemporaryDirectory(prefix='.delivery-',dir=folder) as temp:
            stage=Path(temp)
            names=list(JSON_FILES)+[k+suffix for k in data['preferences']['outputs'] for suffix in ('.musicxml','.pdf')]
            for name in names:
                src=contained(source,name)
                if src.is_file():shutil.copyfile(src,stage/name)
            plan,details,pieces,checks,facts=verify_scores(stage,data)
            dump(stage/'harmony.json',details)
            for k,v in checks.items():dump(stage/(k+'_checks.json'),v)
            write_result_pages(stage,plan,details,pieces,checks,data,revision)
            if (stage/'inner_voice_plan.json').is_file() and 'piano_solo' in pieces:
                from musigen.inner_voices import run
                run(stage,read(stage/'inner_voice_plan.json'))
            if (stage/'recipe.json').is_file() and 'piano_solo' in pieces:
                if (stage/'tonal_references.json').is_file():
                    from musigen.tonal_plan import write_page
                    moves=read(stage/'development_trace.json').get('tonal_moves',[])
                    if moves:write_page(moves,read(stage/'tonal_references.json'),stage)
                from musigen.development_story import run
                run(stage)
            manifest={'format':'musicanote-studio-delivery','version':1,'request_id':request_id,'revision':revision,
                'request_sha256':request_hash,'title':plan['design']['title'],'facts':facts,
                'status':'draft_ready','listener_approval':None,'delivered_utc':datetime.now(timezone.utc).isoformat(),
                'composer_reference':data['preferences'].get('composer','none'),
                'style_status':'requested_reference_not_style_certification',
                'outputs':{k:{'warnings':v['warnings'],'errors':v['errors']} for k,v in checks.items()},
                'files':{p.relative_to(stage).as_posix():sha(p) for p in sorted(stage.rglob('*')) if p.is_file()}}
            dump(stage/'delivery.json',manifest)
            if sha(request_path)!=request_hash:raise ValueError('전달 중 요청이 변경됐습니다')
            # Reserve a fresh immutable revision; previous revisions are never overwritten.
            target.mkdir()
            for item in stage.iterdir():shutil.move(str(item),str(target/item.name))
        status=read(contained(folder,'status.json'))
        status.update(status='draft_ready',revision=revision,delivery_sha256=sha(target/'delivery.json'),listener_approval=None)
        tmp=contained(folder,'status.next.json');dump(tmp,status);tmp.replace(folder/'status.json')
        return manifest
    finally:
        handle.close();lock.unlink()


def catalog(root):
    requests=contained(root,'requests')
    if not requests.is_dir():return []
    rows=[]
    for path in sorted(requests.iterdir()):
        if not REQUEST_ID.fullmatch(path.name):continue
        row={'id':path.name,'status':'unavailable'}
        try:
            folder=request_folder(root,path.name);data=validate_request(read(contained(folder,'request.json')))
            status=read(contained(folder,'status.json'))
            row.update(status=status['status'],origin=status.get('origin','user'),received_utc=status['received_utc'],
                motif_name=data['motif'].get('name','이름 없는 모티프'),preferences=data['preferences'],
                request_url=f'requests/{path.name}/request.json')
            if status['status']=='draft_ready':
                revision=status['revision']
                if not isinstance(revision,str) or not REVISION.fullmatch(revision):raise ValueError('결과 버전 오류')
                result=contained(folder,'results/'+revision);manifest=contained(result,'delivery.json');delivery=read(manifest)
                if sha(manifest)!=status['delivery_sha256'] or delivery['request_sha256']!=sha(folder/'request.json'):raise ValueError('요청·전달 기록이 변경됐습니다')
                for name,wanted in delivery['files'].items():
                    if sha(contained(result,name))!=wanted:raise ValueError('전달 파일이 변경됐습니다')
                base=f'requests/{path.name}/results/{revision}/'
                row['result']={'title':delivery['title'],'revision':revision,'url':base+'index.html',
                    'story_url':base+'development_story.html' if 'development_story.html' in delivery['files'] else None,
                    'harmony_url':base+'harmony.json','outputs':{k:{**v,'url':base+k+'.html','xml':base+k+'.musicxml','pdf':base+k+'.pdf'} for k,v in delivery['outputs'].items()}}
        except (OSError,ValueError,KeyError,TypeError,AttributeError):
            row.update(status='unavailable',error='요청 또는 결과가 변경·누락됐습니다. 다시 검증해 주세요.');row.pop('result',None)
        rows.append(row)
    return sorted(rows,key=lambda r:r.get('received_utc',''),reverse=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description='작성 완료한 악보를 저장 요청에 대조해 전달');p.add_argument('--root',type=Path,required=True);p.add_argument('--request',required=True);p.add_argument('--piece',type=Path,required=True)
    a=p.parse_args();result=publish(a.root,a.request,a.piece);print(json.dumps({'request':a.request,'revision':result['revision'],'outputs':list(result['outputs'])},ensure_ascii=False))
