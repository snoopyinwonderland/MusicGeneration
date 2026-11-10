"""로컬 모티프 입력 및 대화 작곡용 요청 보관. 모델 호출은 하지 않는다."""
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from fractions import Fraction
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from musigen.motif_clip import read_events
from musigen.listen import VEROVIO_CDN

KEYS=('C major','G major','D major','F major','Bb major','Eb major','A minor','E minor','D minor','G minor','C minor')


def validate_request(data):
    if not isinstance(data,dict) or data.get('format')!='musicanote-composition-request' or data.get('version')!=1:
        raise ValueError('작곡 요청 version 1이 필요합니다')
    if set(data)!={'format','version','motif','preferences'}:raise ValueError('작곡 요청 필드를 확인하세요')
    events=read_events(data['motif'])
    if not any(e.pitches for e in events) or any(len(e.pitches)>1 for e in events):
        raise ValueError('현재 작곡 입력은 쉼을 포함한 단선율입니다. 멜로디 성부만 선택하세요')
    p=data['preferences']
    fields={'prompt','key','meter','tempo','bars','secondary','augmented_sixth','modulation','outputs'}
    if not isinstance(p,dict) or not fields<=set(p) or set(p)-fields-{'composer'}:raise ValueError('작곡 조건 필드를 확인하세요')
    if p.get('composer','none') not in ('none','mozart','beethoven','chopin'):raise ValueError('희망 작곡가 스타일을 확인하세요')
    if not isinstance(p['prompt'],str) or len(p['prompt'])>3000:raise ValueError('작곡 방향은 3000자 이내로 적어 주세요')
    if p['key'] not in KEYS or p['meter'] not in ('3/4','4/4','6/8'):raise ValueError('조성·박자를 확인하세요')
    if type(p['tempo']) is not int or not 40<=p['tempo']<=180:raise ValueError('빠르기는 40–180입니다')
    if type(p['bars']) is not int or p['bars'] not in (16,24,32,48,64):raise ValueError('마디 수를 확인하세요')
    if any(type(p[k]) is not bool for k in ('secondary','augmented_sixth','modulation')):raise ValueError('화성 선택을 확인하세요')
    if not isinstance(p['outputs'],list) or 'melody_harmony' not in p['outputs'] or len(set(p['outputs']))!=len(p['outputs']) or set(p['outputs'])-{'melody_harmony','piano_solo'}:
        raise ValueError('기본 출력은 멜로디 + 상세 화성이며 피아노 솔로를 추가할 수 있습니다')
    beats,unit=map(int,p['meter'].split('/'))
    if sum(e.dur for e in events)>Fraction(4*beats,unit)*p['bars']:raise ValueError('입력 모티프가 요청한 곡보다 깁니다')
    return data


def save_request(root,data):
    validate_request(data)
    request_id='request-'+uuid.uuid4().hex
    folder=Path(root)/'requests'/request_id
    folder.mkdir(parents=True)
    reference=None
    if data['preferences'].get('composer','none')!='none':
        from musigen.composer_reference import write
        try:
            reference=write(data['preferences']['composer'],data['motif'],data['preferences']['meter'],folder/'style-reference')
        except (OSError,ValueError) as exc:
            reference={'status':'unavailable','error':str(exc)}
    for name,value in [('request.json',data),('motif.json',data['motif']),
                       ('status.json',{'status':'awaiting_composer','received_utc':datetime.now(timezone.utc).isoformat()})]:
        (folder/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if reference and reference['status']=='unavailable':
        (folder/'reference-error.json').write_text(json.dumps(reference,ensure_ascii=False),encoding='utf-8')
    return {'id':request_id,'status':'awaiting_composer','url':f'requests/{request_id}/request.json',
            'reference_bars':reference.get('matching_meter_bars') if reference else None,
            'reference_error':reference.get('error') if reference else None}


def write_studio(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    assets=out/'assets';assets.mkdir(exist_ok=True)
    source=Path(__file__).parent
    for name in ('studio.js','studio.css'):
        shutil.copyfile(source/name,assets/name)
    # Share the tested parser without attaching the listening-page UI handlers.
    core=(source/'motif_tools.js').read_text(encoding='utf-8').split('\n(() => {',1)[0]
    (assets/'motif-core.js').write_text(core,encoding='utf-8')
    shutil.copyfile(source/'assets/piano/piano.json',assets/'piano.json')
    shutil.copyfile(source/'assets/piano/ATTRIBUTION.md',assets/'piano-ATTRIBUTION.md')
    runtime=Path(os.environ.get('MUSICOMP_ROOT',str(source.parent.parent/'Music Composition')))/'node_modules/verovio/dist/verovio-toolkit-wasm.js'
    src=VEROVIO_CDN
    if runtime.is_file():shutil.copyfile(runtime,assets/'verovio.js');src='assets/verovio.js'
    text=(source/'studio.html').read_text(encoding='utf-8').replace('/*VEROVIO_SRC*/',src)
    (out/'index.html').write_text(text,encoding='utf-8')
    return out.resolve()


class StudioHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path!='/api/requests':self.send_error(404);return
        origin=self.headers.get('Origin')
        allowed={f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}
        if origin not in allowed or self.headers.get('Sec-Fetch-Site')=='cross-site':self.send_error(403);return
        if self.headers.get_content_type()!='application/json':self.send_error(415);return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=1024*1024:self.send_error(413);return
            data=json.loads(self.rfile.read(size))
            result=save_request(self.directory,data)
        except (ValueError,KeyError,TypeError,AttributeError) as exc:
            self.reply(400,{'error':str(exc)});return
        self.reply(201,result)

    def reply(self,status,data):
        body=json.dumps(data,ensure_ascii=False).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)


def serve(out,port=8794):
    root=write_studio(out)
    server=ThreadingHTTPServer(('127.0.0.1',port),partial(StudioHandler,directory=str(root)))
    print(f'모티프 입력: http://127.0.0.1:{server.server_port}/',flush=True)
    try:server.serve_forever()
    finally:server.server_close()
