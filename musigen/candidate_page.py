"""P1 comparison UI, packaged for local files and static hosting."""
import json
import os
import shutil
from pathlib import Path

def write_page(data,out):
    out=Path(out);assets=out.parent/'assets';assets.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).parent
    runtime=Path(os.environ.get('MUSICOMP_ROOT',root.parent.parent/'Music Composition'))/'node_modules/verovio/dist/verovio-toolkit-wasm.js'
    source='https://cdn.jsdelivr.net/npm/verovio@6.3.0/dist/verovio-toolkit-wasm.js'
    if runtime.exists():
        shutil.copyfile(runtime,assets/'verovio.js');source='assets/verovio.js'
    shutil.copyfile(root/'assets/piano/ATTRIBUTION.md',assets/'piano-ATTRIBUTION.md')
    # Embed the existing bank so exported comparison pages also play via file://.
    bank=json.loads((root/'assets/piano/piano.json').read_text(encoding='utf-8'))
    text=(root/'candidate_template.html').read_text(encoding='utf-8')
    for key,value in [('DATA',data),('BANK',bank)]:
        text=text.replace('/*'+key+'*/',json.dumps(value,ensure_ascii=False).replace('</','<\\/'))
    text=text.replace('/*VEROVIO_SRC*/',source).replace('/*PLAYER*/',(root/'candidate_player.js').read_text(encoding='utf-8'))
    if data.get('stage') == 'phrase':
        text=text.replace('모티프 후보 비교 · MUSICANOTE','프레이즈 후보 비교 · MUSICANOTE')
    out.write_text(text,encoding='utf-8')
