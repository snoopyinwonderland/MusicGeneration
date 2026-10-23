"""P2 candidates consume only an explicitly recorded P1 choice."""
import copy
from pathlib import Path
from musigen.motif_candidates import read_json, digest, dump, settings, features
from musigen.motif_clip import read_events
from musigen.notation import Ev
from musigen.piece import build
from musigen.checks import check
from musigen.piano_io import write_musicxml
from musigen.candidate_page import write_page
from musigen.design import bar_len
from musigen.phrase_grammar import LABELS

def selected_motif(work):
    work=Path(work)
    if not (work/'selected_motif.json').is_file():raise ValueError('P1에서 실제 모티프를 먼저 선택하세요')
    design=read_json(work/'design.json');selected=read_json(work/'selected_motif.json')
    if selected.get('format')!='musicanote-selected-motif' or selected.get('version')!=1:raise ValueError('P1에서 실제 모티프를 먼저 선택하세요')
    record=selected['selection'];unsigned=dict(record);sid=unsigned.pop('selection_id',None)
    if sid!=digest(unsigned) or record.get('stage')!='motif' or record['design_sha256']!=digest(design):raise ValueError('모티프 선택 또는 설계가 변경되었습니다')
    journal=[read_json_line(line) for line in (work/'selections.jsonl').read_text(encoding='utf-8').splitlines() if line]
    choices=[r for r in journal if r.get('stage')=='motif']
    if not choices or choices[-1]!=record:raise ValueError('최근 실제 선택 기록과 일치하지 않습니다')
    data=read_json(work/'stage1_motifs/runs'/record['set_id']/'candidates.json')
    from musigen.selections import identity
    if identity(data)!=record['set_id']:raise ValueError('보존된 모티프 묶음이 변경되었습니다')
    row=next((c for c in data['candidates'] if c['id']==record['chosen']),None)
    if not row or selected['motif']!={k:v for k,v in row.items() if k not in ('features','preview')}:raise ValueError('선택 모티프 내용이 변경되었습니다')
    return design,selected

def read_json_line(line):
    import json
    return json.loads(line)

def identity(data):
    value=copy.deepcopy(data);value.pop('set_id',None)
    for row in value['candidates']:
        for k in ('xml','notes','quarters'):row['preview'].pop(k,None)
    return digest(value)

def generate(design,selected,count=4):
    if type(count)is not int or count not in (3,4):raise ValueError('프레이즈 후보 수는 3 또는 4입니다')
    basics,constraints,key,prof,lo,hi=settings(design)
    rows=[];pieces={}
    variants=[('sentence','문장형 · 조각과 반복 진행'),('period','악절형 · 질문과 응답'),
              ('hybrid','혼합형 · 질문 뒤 이어짐'),('sentence','문장형 · 리듬 축소')]
    for i,(kind,label) in enumerate(variants[:count],1):
        cid=f'p{i}'
        phrase={'type':kind,'motif':'a','range':[lo,hi]}
        if i==4:phrase['functions']={'continuation':{'bars':[5,6],'technique':['diminution'],'harmonic_rhythm':'faster'}}
        pd={'title':design.get('title','프레이즈')+' · '+label,'basics':copy.deepcopy(basics),
            'theme':{'motifs':{'a':{'hand':'rh'}}},'impression':copy.deepcopy(design.get('impression',{})),
            'form':[{'label':label,'bars':[1,8],'function':'statement','motifs':['a'],'cadence':'authentic'}],
            'analysis':{'phrases':True},'climax':{'bar':6,'how':'이어짐의 음역·밀도 정점 관찰 (잠정)'}}
        score={'motifs':{'a':copy.deepcopy(selected['motif'])},'blocks':[{'bars':'1-8','phrase':phrase}]}
        piece=build(pd,score);checked=check(piece,pd)
        if checked['errors']:raise ValueError(cid+': '+'; '.join(checked['errors']))
        # Features reuse the measured P1 summary; formal observations are separate.
        ev=[];pos=piece.bar_start(1)
        for n in piece.in_bars(1,8,'rh'):
            if n.onset>pos:ev.append(Ev(n.onset-pos))
            ev.append(Ev(n.dur,tuple(m for m,t in n.pitches),tuple(t for m,t in n.pitches)));pos=n.onset+n.dur
        f=features(ev,8*bar_len(basics['meter']));f['contour_label']=label
        f['harmonic_implication']='반종지 → 정격종지' if kind!='sentence' else '제시 → 이어짐 → 정격종지'
        row={'id':cid,'origin':{'kind':'generator','grammar':'caplin-provisional-v1'},'features':f,
             'design':pd,'score':score,'functions':piece.phrase_plans,'observations':checked['phrase_functions'],
             'preview':{'bars':8,'warnings':checked['warnings']}}
        rows.append(row);pieces[cid]=(piece,checked)
    data={'format':'musicanote-candidates','version':1,'stage':'phrase','design':copy.deepcopy(design),
          'design_sha256':digest(design),'motif_selection_id':selected['selection']['selection_id'],
          'selected_motif':selected['selection']['chosen'],'requested':count,'status':'ready','candidates':rows,
          'diagnostics':{'basis':'Caplin(1998) 3–5장에 따른 기능 구분. 구체적 음·반주·수치는 잠정.',
            'selection':'사용자가 선택한 모티프만 사용. 품질 향상 여부는 청취 판단 대기.',
            'source':'https://www.music.mcgill.ca/~caplin/teaching-classical-form.pdf'}}
    data['set_id']=identity(data)
    return data,pieces

def run(work,count=4):
    work=Path(work);design,selected=selected_motif(work);data,pieces=generate(design,selected,count)
    stage=work/'stage2_phrases';archive=stage/'runs'/data['set_id'];archive.mkdir(parents=True,exist_ok=True)
    for row in data['candidates']:
        folder=archive/row['id'];folder.mkdir(exist_ok=True)
        piece,checked=pieces[row['id']]
        xml=write_musicxml(piece,folder/'preview.musicxml')
        for name,value in [('design',row['design']),('score',row['score']),('checks',checked)]:dump(folder/(name+'.json'),value)
        row['preview'].update({'xml':xml.read_text(encoding='utf-8'),
            'notes':[{'q':float(n.onset),'d':float(n.dur),'p':[m for m,t in n.pitches],'hand':n.hand} for n in piece.notes],
            'quarters':float(piece.bars*piece.bar_len)})
    dump(archive/'candidates.json',data);dump(stage/'candidates.json',data);write_page(data,stage/'index.html')
    return {'path':str(stage/'index.html'),'status':'ready','count':len(data['candidates']),'set_id':data['set_id']}
