"""Open a generated lead sheet in the native musicomp workbench."""
import atexit
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import quote

from musigen import MUSICOMP_ROOT

_lock = threading.Lock()
_servers = {}


def open_workbench(root, identity):
    if not isinstance(identity, str) or not re.fullmatch('[a-f0-9]{32}', identity):
        raise ValueError('곡을 확인하세요.')
    root = Path(root).resolve()
    piece = root / 'compositions' / identity
    if not (piece / 'melody.musicxml').is_file():
        raise ValueError('저장된 선율 악보를 찾을 수 없습니다.')
    title = json.loads((piece / 'piece.json').read_text('utf8'))['title']
    name = re.sub(r'[^\w가-힣 -]', '_', title)[:48].strip() or '모티프'
    filename = f'{name}-{identity}.musicxml'
    state = root.with_name(root.name + '-arranger')
    with _lock:
        uploads = state / 'uploads'
        uploads.mkdir(parents=True, exist_ok=True)
        target = uploads / filename
        if not target.exists():
            tmp = target.with_suffix('.tmp')
            tmp.write_bytes((piece / 'melody.musicxml').read_bytes())
            tmp.replace(target)
        current = _servers.get(root)
        if not current or current[0].poll() is not None:
            with tempfile.TemporaryDirectory() as temp:
                ready = Path(temp) / 'port'
                env = {**os.environ, 'MUSICOMP_PYTHON':sys.executable, 'MUSICOMP_OUTPUT_DIR':str(state/'scores'),
                       'MUSICOMP_UPLOAD_DIR':str(uploads), 'MUSICOMP_HOST':'127.0.0.1'}
                (state/'scores').mkdir(exist_ok=True)
                with (state/'server.log').open('a', encoding='utf8') as log:
                    proc = subprocess.Popen(['node', str(Path(__file__).resolve().parents[1]/'editor/arranger.mjs'),
                                             str(MUSICOMP_ROOT.resolve()), str(state), str(ready)],
                                            env=env, stdin=subprocess.PIPE, stdout=log, stderr=log,
                                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                try:
                    for _ in range(300):
                        if ready.exists() and (port := ready.read_text().strip()).isdigit():
                            break
                        if proc.poll() is not None:
                            raise RuntimeError('편곡기를 시작하지 못했습니다. '+str(state/'server.log'))
                        time.sleep(.1)
                    else:
                        raise RuntimeError('편곡기 시작 시간이 초과되었습니다.')
                except BaseException:
                    if proc.poll() is None: proc.terminate()
                    proc.stdin.close()
                    raise
                _servers[root] = proc, int(port)
                atexit.register(proc.stdin.close)
        port = _servers[root][1]
    return {'url':f'http://127.0.0.1:{port}/?score={quote(filename)}'}
