"""Compile explicit phrase stages into the existing blueprint/solo workflow.

This is a reusable authoring interface, not an automatic harmony/style generator.
"""
import argparse
import copy
import json
from fractions import Fraction as F
from pathlib import Path
from musigen.blueprint import prepare,dump,digest
from musigen.blueprint_solo import run as render
from musigen.piece import _bars

ROLES={'statement':'statement','response':'statement','development':'development','contrast':'contrast','return':'return','cadence':'coda'}


def compile_recipe(motif,recipe,library):
    if recipe.get('format')!='musicanote-development-recipe' or recipe.get('version')!=1:raise ValueError('발전 과정 형식 오류')
    observed={r['id'] for r in library['phrases'] if r['status']=='observed'}
    design=copy.deepcopy(recipe['design']);design['form']=[];design['phrase_plan']=[]
    blocks=[];solo_blocks=[];trace=[];offset=0
    if not recipe.get('stages'):raise ValueError('빈 발전 과정')
    for stage in recipe['stages']:
        length=stage['length'];role=stage['role'];refs=stage['reference_ids']
        if type(length)is not int or length<1 or role not in ROLES:raise ValueError('구간 길이·역할 오류')
        if not refs or any(r not in observed for r in refs):raise ValueError('관찰된 참조 ID가 필요합니다')
        if not stage.get('observation') or not stage.get('decision'):raise ValueError('자료 관찰과 작성자 결정을 구별하세요')
        span=[offset+1,offset+length]
        section={'label':stage['label'],'bars':span,'function':ROLES[role]}
        if stage.get('cadence'):section['cadence']=stage['cadence']
        design['form'].append(section)
        design['phrase_plan'].append({'bars':span,'role':stage['label'],'plan':stage['decision']})
        cursor=1
        for block in stage['blocks']:
            a,z=_bars(block['bars'],length)
            if a!=cursor:raise ValueError('구간 안의 마디는 빈틈·겹침 없이 이어져야 합니다')
            cursor=z+1;b=copy.deepcopy(block);b['bars']=str(offset+a) if a==z else f'{offset+a}-{offset+z}'
            if 'copy' in b:
                ca,cz=_bars(b['copy'],length)
                if cz>=a:raise ValueError('복사는 구간 안의 앞 마디만 참조합니다')
                b['copy']=str(offset+ca) if ca==cz else f'{offset+ca}-{offset+cz}'
            if 'lh' not in b:raise ValueError('각 블록에 명시적인 반주가 필요합니다')
            solo_blocks.append(copy.deepcopy(b));b.pop('lh');b.pop('chords',None);blocks.append(b)
        if cursor!=length+1:raise ValueError('구간 끝까지 마디가 필요합니다')
        trace.append({'bars':span,'role':role,'reference_ids':refs,'observation':stage['observation'],'decision':stage['decision']})
        offset+=length
    plan={'format':'musicanote-development','version':1,'design':design,'score':{'blocks':blocks},
          'harmony':copy.deepcopy(recipe['harmony']),
          'references':[{'kind':'author_interpreted_observations','source':library['source_url'],
                         'license':library['license'],'ids':sorted({r for s in trace for r in s['reference_ids']})}]}
    lead,_,_=prepare(motif,plan)  # protects the exact opening and checks harmony coverage
    for row in trace:
        lo,hi=lead.bar_start(row['bars'][0]),lead.bar_end(row['bars'][1])
        notes=[n for n in lead.notes if n.hand=='rh' and lo<=n.onset<hi]
        sounding=sum((min(n.onset+n.dur,hi)-n.onset for n in notes),F(0))
        row['actual']={'attacks':len(notes),'rest_quarters':str(hi-lo-sounding),
                       'material_sources':sorted({n.src for n in notes}),
                       'pitch_range':[min(m for n in notes for m,t in n.pitches),max(m for n in notes for m,t in n.pitches)] if notes else None}
    score={'blocks':solo_blocks,'motifs':{'input':copy.deepcopy(motif)},'expression':copy.deepcopy(recipe.get('expression',[]))}
    realization={'format':'musicanote-piano-realization','version':1,'score':score,
                 'feedback':{'user_text':recipe['request'],'scope':'다른 모티프의 작성 과정 재사용 시험; 사용자 선택 기록 아님'}}
    return plan,realization,{'recipe_sha256':digest(recipe),'library_sha256':digest(library),'motif_sha256':digest(motif),
                             'status':'authored_recipe_not_fitted_generator','stages':trace}


def run(work,out,corpus=False,pages_only=False):
    work,out=Path(work),Path(out);read=lambda n:json.loads((work/n).read_text(encoding='utf-8'))
    motif,recipe,library=[read(n) for n in ('motif.json','recipe.json','references.json')]
    plan,realization,trace=compile_recipe(motif,recipe,library)
    compiled=work/'compiled';compiled.mkdir(exist_ok=True)
    for n,v in [('motif.json',motif),('development.json',plan),('realization.json',realization)]:dump(compiled/n,v)
    result=render(compiled,out,corpus,pages_only)
    dump(out/'development_trace.json',trace);dump(out/'recipe.json',recipe);dump(out/'references.json',library)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description='명시적인 프레이즈 발전 과정을 두 악보로 실현')
    p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--corpus-accompaniment',action='store_true');p.add_argument('--pages-only',action='store_true');a=p.parse_args()
    print(json.dumps(run(a.work,a.out,a.corpus_accompaniment,a.pages_only),ensure_ascii=False))
