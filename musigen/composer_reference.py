"""작곡가별 train 마디와 연결 위치를 보존하는 선택적 비상업 참조 검색.

근거: 2026-11-10 사용자 요청. 학습 모델·품질 점수·완성곡 생성기가 아니다.
"""
import gzip
import hashlib
import json
import os
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
from musigen.motif_clip import read_events

COMPOSERS={'mozart':('Mozart','mozart-sonatas'),'beethoven':('Beethoven','beethoven-sonatas'),
           'chopin':('Chopin','chopin-mazurkas')}


def source_path():
    import musicomp
    root=Path(os.environ['MUSICOMP_ROOT']) if os.environ.get('MUSICOMP_ROOT') else Path(musicomp.__file__).parent.parent
    return root/'musicomp/knowledge/data/classical/bars.jsonl.gz'


def features(notes,length):
    notes=sorted(notes,key=lambda n:F(n['on']))
    intervals=[b['midi']-a['midi'] for a,b in zip(notes,notes[1:])]
    covered=F(0);end=F(0)
    for n in notes:
        a=max(F(0),F(n['on']));z=min(length,a+F(n['dur']))
        covered+=max(F(0),z-max(a,end));end=max(end,z)
    return {'onsets':[str(F(n['on'])) for n in notes],'durations':[str(F(n['dur'])) for n in notes],
            'intervals':intervals,'density':len(notes)/float(length),'rest_ratio':float(1-covered/length),
            'step_ratio':sum(abs(i)<=2 for i in intervals)/len(intervals) if intervals else 0}


def index_rows(rows,composer):
    if composer not in COMPOSERS:raise ValueError('작곡가는 mozart/beethoven/chopin 중에서 선택하세요')
    name,corpus=COMPOSERS[composer];result=[]
    for r in rows:
        if r.get('composer')!=name or r.get('corpus')!=corpus or r.get('split')!='train':continue
        if not r.get('library_assessment',{}).get('eligible') or not r.get('melody'):continue
        if r.get('license')!='CC-BY-NC-SA-4.0':continue
        result.append({'id':f"{r['song']}:{r['bar']}",'song':r['song'],'bar':r['bar'],
            'printed_bar':r.get('source',{}).get('mn'),'work_group':r['work_group'],'composer':name,
            'corpus':corpus,'split':'train','license':r['license'],'meter':r['meter'],'bar_len':r['bar_len'],
            'key':r['key'],'phrase':r.get('phrase'),'phrase_method':r.get('phrase_method'),
            'cadence':r.get('cadence'),'cadence_annotations':r.get('cadence_annotations'),
            'figure_candidate':r.get('figure_candidate'),'lh_density':r.get('summary',{}).get('lh_density'),
            'harmony':[{'on':c['on'],'end':c['end'],'label':c.get('annotation',{}).get('label'),
                        'localkey':c.get('annotation',{}).get('localkey'),'bass_pc':c.get('bass_pc')} for c in r.get('chords',[])],
            'melody_features':features(r['melody'],F(r['bar_len'])),
            'melody_is_human_labeled':False,'source':r.get('source')})
    known={(r['song'],r['bar']):r['id'] for r in result}
    for r in result:
        r['previous']=known.get((r['song'],r['bar']-1));r['next']=known.get((r['song'],r['bar']+1))
    return result


def build(composer,motif,meter='4/4',source=None):
    path=Path(source) if source else source_path()
    with gzip.open(path,'rt',encoding='utf-8') as handle:
        index=index_rows((json.loads(line) for line in handle if line.strip()),composer)
    if not index:raise ValueError('해당 작곡가의 적격 train 마디가 없습니다. 다른 작곡가로 대체하지 않습니다')
    beats,unit=map(int,meter.split('/'));length=F(4*beats,unit)
    if length<=0:raise ValueError('유효한 박자가 필요합니다')
    notes=[];on=F(0)
    for e in read_events(motif):
        if len(e.pitches)>1:raise ValueError('참조 검색은 단선율 모티프를 받습니다')
        if on>=length:break
        if e.pitches:notes.append({'on':str(on),'dur':str(min(e.dur,length-on)),'midi':e.pitches[0]})
        on+=e.dur
    query=features(notes,length)
    candidates=[r for r in index if r['meter']==meter and F(r['bar_len'])==length]
    def distance(r):
        f=r['melody_features']
        return abs(f['density']-query['density'])+abs(f['rest_ratio']-query['rest_ratio'])+abs(f['step_ratio']-query['step_ratio'])
    selected=[];works=set()
    for r in sorted(candidates,key=lambda r:(distance(r),r['id'])):
        if r['work_group'] in works:continue
        selected.append({**r,'distance':round(distance(r),6)});works.add(r['work_group'])
        if len(selected)==5:break
    summary={'status':'reference_search_only_not_generated_music','composer':composer,
        'source':str(path),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'license':'CC-BY-NC-SA-4.0','eligible_train_bars':len(index),'eligible_works':len({r['work_group'] for r in index}),
        'matching_meter_bars':len(candidates),'meters':dict(Counter(r['meter'] for r in index)),
        'phrase_position_bars':sum(bool(r['phrase']) for r in index),
        'cadence_bars':sum(bool(r['cadence'] or r['cadence_annotations']) for r in index),
        'connected_next_bars':sum(r['next'] is not None for r in index),
        'query_scope':'first_bar_only','query':query,'references':selected,
        'ranking':'잠정 검색 거리: 음 밀도·쉼 비율·2반음 이내 진행 비율의 차이 합. 학습된 품질 점수가 아님.',
        'limits':['적격 마디의 빈틈을 채우지 않음; 완전한 프레이즈 라이브러리가 아님',
                  '선율은 상보표 최고음 후보이며 사람의 선율 주석이 아님',
                  '작품별 최대 한 사례; 동일 박자가 없으면 빈 검색 결과',
                  '쇼팽 자료는 마주르카 중심; 녹턴·에튀드 스타일을 대표하지 않음']}
    return index,summary


def write(composer,motif,meter,out):
    out=Path(out)
    if out.exists() and any(out.iterdir()):raise ValueError('새 참조 출력 폴더를 지정하세요')
    index,summary=build(composer,motif,meter)
    out.mkdir(parents=True,exist_ok=True)
    with (out/'bar-index.jsonl').open('w',encoding='utf-8') as handle:
        for row in index:handle.write(json.dumps(row,ensure_ascii=False)+'\n')
    (out/'references.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary
