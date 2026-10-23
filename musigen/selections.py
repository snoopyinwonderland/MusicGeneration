"""Explicit user choices only: append-only P5 journal and validated next-stage input."""
import copy
import datetime as dt
import json
import os
import re
from pathlib import Path
from musigen.motif_candidates import read_json, digest

def identity(data):
    value=copy.deepcopy(data); value.pop('set_id',None)
    for row in value['candidates']:
        for k in ('xml','notes','quarters'): row['preview'].pop(k,None)
    return digest(value)

def choose(work, selection):
    if re.fullmatch(r"p[1-9]\d*",str(selection)) or (not re.fullmatch(r"m[1-9]\d*",str(selection)) and read_json(selection).get("stage")=="phrase"):
        from musigen.phrase_selection import choose_phrase
        return choose_phrase(work, selection)
    work=Path(work).resolve()
    design=read_json(work/'design.json'); data=read_json(work/'stage1_motifs/candidates.json')
    if data.get('format')!='musicanote-candidates' or data.get('version')!=1 or data.get('stage')!='motif':
        raise ValueError('모티프 후보 묶음 형식을 확인하세요')
    if data['design_sha256']!=digest(design): raise ValueError('설계가 바뀌었습니다. 모티프 후보를 다시 만드세요')
    if data['set_id']!=identity(data): raise ValueError('후보 묶음이 변경되었습니다. 다시 생성하세요')
    if data['status']=='stopped': raise ValueError('다양성 중단 상태에서는 선택을 다음 단계로 넘길 수 없습니다')
    candidates={c['id']:c for c in data['candidates']}
    if re.fullmatch(r'm[1-9]\d*',str(selection)):
        payload={'chosen':str(selection),'shown':list(candidates),'reason':''}
    else:
        payload=read_json(selection)
        if not isinstance(payload,dict) or payload.get('format')!='musicanote-selection' or payload.get('version')!=1 or payload.get('stage')!='motif':
            raise ValueError('선택 내보내기 JSON 형식이 아닙니다')
        if payload.get('set_id')!=data['set_id'] or payload.get('design_sha256')!=data['design_sha256']:
            raise ValueError('이전 설계 또는 다른 후보 묶음의 선택입니다. 현재 비교 페이지에서 다시 선택하세요')
    chosen=payload.get('chosen');shown=payload.get('shown');reason=payload.get('reason','')
    if not isinstance(chosen,str) or chosen not in candidates: raise ValueError('후보 id를 찾을 수 없습니다')
    if not isinstance(shown,list) or not all(isinstance(x,str) and x in candidates for x in shown) or len(set(shown))!=len(shown) or chosen not in shown:
        raise ValueError('본 후보 목록에는 선택 후보와 유효한 후보 id가 있어야 합니다')
    if not isinstance(reason,str) or len(reason)>1000: raise ValueError('선택 이유는 1,000자 이내 문장입니다')
    candidate=candidates[chosen]
    record={'time':dt.datetime.now(dt.timezone.utc).isoformat(),'stage':'motif','work':str(work),
            'shown':shown,'chosen':chosen,'origin':{chosen:candidate['origin']},'reason':reason,
            'design_sha256':data['design_sha256'],'set_id':data['set_id']}
    record['selection_id']=digest(record)
    selected={'format':'musicanote-selected-motif','version':1,'selection':record,
              'motif':{k:copy.deepcopy(v) for k,v in candidate.items() if k not in ('preview','features')},
              'features':candidate['features']}
    # Validate every input before any persistent mutation. The journal is append-only.
    temp=work/'selected_motif.json.tmp'
    temp.write_text(json.dumps(selected,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    try:
        with (work/'selections.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(record,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
        temp.replace(work/'selected_motif.json')
    finally:
        temp.unlink(missing_ok=True)
    return record
