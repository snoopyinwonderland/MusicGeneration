"""Explicit listening feedback for authored A/B pieces; never a training hook."""
import argparse
from datetime import datetime
import hashlib
import html
import json
from pathlib import Path
from uuid import UUID


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def manifest(directory, report):
    directory = Path(directory)
    files = {f'{side}/{kind}.musicxml': hashlib.sha256((directory/side/(kind+'.musicxml')).read_bytes()).hexdigest()
             for side in ('a', 'b') for kind in ('melody_harmony', 'piano_solo')}
    value = {'format': 'musicanote-piece-review', 'version': 1, 'stage': 'piece',
             'work': directory.name, 'shown': ['a', 'b'],
             'origin': {'a': 'composer', 'b': 'composer'}, 'blind': False,
             'design_sha256': report['input_sha256'], 'artifacts': files}
    value['comparison_sha256'] = digest(value)
    (directory/'choice_manifest.json').write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return value


def section(value):
    public = {k:value[k] for k in ('work', 'shown', 'design_sha256', 'comparison_sha256')}
    payload = json.dumps(public, ensure_ascii=False).replace('<', '\\u003c')
    return '''<aside id="listening-choice"><h2>듣고 난 뒤의 의견</h2>
<p>마음에 드는 판이 없으면 ‘둘 다 다시 다듬기’를 고르셔도 됩니다. 선택은 자동 학습에 사용하지 않습니다.</p>
<form id="choice-form"><fieldset style="border:0;padding:0;display:flex;gap:16px;flex-wrap:wrap"><legend>어느 판으로 이어 갈까요?</legend>
<label><input type="radio" name="verdict" value="a"> A · 기존판</label>
<label><input type="radio" name="verdict" value="b"> B · 연결 수정판</label>
<label><input type="radio" name="verdict" value="reject_all"> 둘 다 다시 다듬기</label>
<label><input type="radio" name="verdict" value="undecided"> 아직 결정하지 않음</label></fieldset>
<label style="display:block;margin-top:16px">이유 · 원하는 변화 (선택)<textarea id="choice-reason" maxlength="4000" rows="3" style="display:block;box-sizing:border-box;width:100%;margin:8px 0;font:inherit"></textarea></label>
<button id="choice-export" type="submit" disabled style="font:inherit;padding:8px 16px">의견 JSON 받기</button>
<p id="choice-message" role="status">선택한 뒤 파일로 받을 수 있습니다.</p></form></aside>
<script>(()=>{const info=PAYLOAD;const form=document.getElementById('choice-form');
form.addEventListener('change',()=>{document.getElementById('choice-export').disabled=!form.querySelector('input:checked')});
form.addEventListener('submit',event=>{event.preventDefault();const radio=form.querySelector('input:checked');if(!radio)return;
const verdict=radio.value;const record={format:'musicanote-listening-choice',version:1,event_id:crypto.randomUUID(),time:new Date().toISOString(),
stage:'piece',...info,verdict,chosen:['a','b'].includes(verdict)?verdict:null,reason:document.getElementById('choice-reason').value,evaluation:false};
try{localStorage.setItem('musicanote-review-'+info.comparison_sha256,JSON.stringify(record))}catch(e){}
const url=URL.createObjectURL(new Blob([JSON.stringify(record,null,2)+'\\n'],{type:'application/json'}));const a=document.createElement('a');
a.href=url;a.download=info.work+'-listening-choice.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
document.getElementById('choice-message').textContent='의견 파일을 만들었습니다. 파일을 대화에 전달하면 선택 기록에 반영합니다.'});})();</script>'''.replace('PAYLOAD', payload)


def validate(value, exported):
    if value.get('comparison_sha256') != digest({k:v for k,v in value.items() if k != 'comparison_sha256'}):
        raise ValueError('비교 명세의 지문이 다릅니다')
    if exported.get('format') != 'musicanote-listening-choice' or exported.get('version') != 1 or exported.get('evaluation') is not False:
        raise ValueError('실제 의견 내보내기 형식이 필요합니다. 시험 기록은 받지 않습니다')
    for key in ('stage', 'work', 'shown', 'design_sha256', 'comparison_sha256'):
        if exported.get(key) != value[key]:
            raise ValueError(f'다른 비교판의 의견입니다: {key}')
    verdict = exported.get('verdict')
    if verdict not in (*value['shown'], 'reject_all', 'undecided'):
        raise ValueError('알 수 없는 의견입니다')
    chosen = verdict if verdict in value['shown'] else None
    if exported.get('chosen') != chosen:
        raise ValueError('선택 후보와 의견이 다릅니다')
    UUID(exported['event_id'])
    timestamp = datetime.fromisoformat(exported['time'].replace('Z', '+00:00'))
    if timestamp.tzinfo is None:
        raise ValueError('선택 시간에 시간대가 필요합니다')
    reason = exported.get('reason', '')
    if not isinstance(reason, str) or len(reason) > 4000:
        raise ValueError('의견은 4000자 이하 문자열이어야 합니다')
    return {k:exported[k] for k in ('event_id', 'time', 'stage', 'work', 'shown', 'chosen',
            'verdict', 'reason', 'design_sha256', 'comparison_sha256')} | {
            'origin': value['origin'], 'source': 'explicit_import_of_browser_feedback',
            'blind': value['blind'], 'used_for_training': False}


def record(directory, exported):
    directory = Path(directory)
    value = json.loads((directory/'choice_manifest.json').read_text(encoding='utf-8'))
    result = validate(value, exported)
    for relative, expected in value['artifacts'].items():
        path = (directory/relative).resolve()
        if not path.is_relative_to(directory.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('악보 파일이 바뀌었습니다. 새 비교판에서 의견을 받아야 합니다')
    target = directory/'selections.jsonl'
    if target.exists():
        for line in target.read_text(encoding='utf-8').splitlines():
            old = json.loads(line)
            if old['event_id'] == result['event_id']:
                if old == result:
                    return False
                raise ValueError('같은 의견 ID의 내용이 다릅니다')
    with target.open('a', encoding='utf-8') as f:
        f.write(json.dumps(result, ensure_ascii=False)+'\n')
    return True


def main():
    p = argparse.ArgumentParser(description='직접 내보낸 청취 의견을 검증한 뒤 선택 이력에 추가합니다')
    p.add_argument('--comparison', type=Path, required=True)
    p.add_argument('--selection', type=Path, required=True)
    args = p.parse_args()
    added = record(args.comparison, json.loads(args.selection.read_text(encoding='utf-8')))
    print('의견을 기록했습니다' if added else '이미 기록한 의견입니다')


if __name__ == '__main__':
    main()
