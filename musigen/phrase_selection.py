"""Append explicit P2 choice and prepare a separate 16-bar work for existing piece."""
import copy
import datetime as dt
import json
import re
from pathlib import Path
from musigen.motif_candidates import read_json, digest, dump
from musigen.phrase_candidates import selected_motif, identity

def choose_phrase(work,selection):
    work=Path(work).resolve();design,motif=selected_motif(work)
    data=read_json(work/'stage2_phrases/candidates.json')
    if data.get('stage')!='phrase' or data.get('format')!='musicanote-candidates' or data.get('version')!=1 or data.get('status')!='ready':raise ValueError('유효한 프레이즈 후보 묶음이 필요합니다')
    if data['set_id']!=identity(data) or data['design_sha256']!=digest(design) or data['motif_selection_id']!=motif['selection']['selection_id']:raise ValueError('모티프 선택·설계·프레이즈 묶음이 바뀌었습니다. 후보를 다시 만드세요')
    rows={r['id']:r for r in data['candidates']}
    if re.fullmatch(r'p[1-9]\d*',str(selection)):payload={'chosen':str(selection),'shown':list(rows),'reason':''}
    else:
        payload=read_json(selection)
        if payload.get('format')!='musicanote-selection' or payload.get('version')!=1 or payload.get('stage')!='phrase' or payload.get('set_id')!=data['set_id'] or payload.get('design_sha256')!=data['design_sha256']:raise ValueError('현재 프레이즈 묶음의 선택 내보내기가 아닙니다')
    chosen=payload.get('chosen');shown=payload.get('shown');reason=payload.get('reason','')
    if not isinstance(chosen,str) or chosen not in rows or not isinstance(shown,list) or any(not isinstance(x,str) or x not in rows for x in shown) or len(set(shown))!=len(shown) or chosen not in shown:raise ValueError('프레이즈 선택 id·표시 후보 목록을 확인하세요')
    if not isinstance(reason,str) or len(reason)>1000:raise ValueError('선택 이유는 1,000자 이내입니다')
    record={'time':dt.datetime.now(dt.timezone.utc).isoformat(),'stage':'phrase','work':str(work),'shown':shown,'chosen':chosen,
            'origin':{chosen:rows[chosen]['origin']},'reason':reason,'design_sha256':data['design_sha256'],
            'set_id':data['set_id'],'motif_selection_id':data['motif_selection_id']}
    record['selection_id']=digest(record)
    row=rows[chosen]
    pd=copy.deepcopy(row['design']);pd['title']=design.get('title','선택 주제')+' · 두 번의 이야기'
    pd['form'] += [{'label':'돌아온 악상','bars':[9,16],'function':'return','motifs':['a'],'cadence':'authentic'}]
    score=copy.deepcopy(row['score']);second=copy.deepcopy(score['blocks'][0]);second['bars']='9-16'
    functions=row['functions'][0]['functions']
    second['phrase']['accompaniment']={name:('waltz' if name in ('presentation','antecedent','consequent') else 'bass') for name in functions}
    score['blocks'].append(second)
    from musigen.piece import build
    from musigen.checks import check
    checked=check(build(pd,score),pd)
    if checked['errors']:raise ValueError('16마디 연결 검사: '+'; '.join(checked['errors']))
    # Every input and assembled score is validated before persistent writes.
    nextwork=work/'piece_work'/record['selection_id'];nextwork.mkdir(parents=True,exist_ok=True)
    dump(nextwork/'design.json',pd);dump(nextwork/'score.json',score);dump(nextwork/'checks.json',checked)
    dump(nextwork/'selection.json',record)
    with (work/'selections.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
    dump(work/'selected_phrase.json',{'format':'musicanote-selected-phrase','version':1,'selection':record,'candidate':row,'piece_work':str(nextwork)})
    return {**record,'piece_work':str(nextwork),'note':'16마디 초안은 반주가 달라지는 반복입니다. 완성도 판정·기본 적용 아님.'}
