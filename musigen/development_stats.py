"""Local-only P3 audit preparation and fail-closed aggregate promotion.

Never writes to source corpora. The existing melody/motif/phrase analysers run
without parameter tuning. Raw excerpts and audit decisions stay under output/.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from dataclasses import replace
from fractions import Fraction
import musigen

def dump(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def prepare(manifest,out):
    from musicomp.core.score import load_melody
    from musicomp.analysis.key import estimate_key
    from musicomp.analysis.motif import analyze_motifs
    from musicomp.analysis.phrase import segment_layers
    manifest=json.loads(Path(manifest).read_text(encoding='utf-8-sig'));out=Path(out)
    if out.exists() and any(out.iterdir()):raise ValueError('비어 있는 새 감사 폴더를 사용하세요')
    out.mkdir(parents=True,exist_ok=True)
    samples=[];errors=[];counts=Counter()
    for source in manifest['sources']:
        genre=source['genre']
        if counts[genre]>=30:continue
        if source.get('use_scope') not in ('local_research_only','licensed') or not source.get('license_reference'):raise ValueError('사용 범위·라이선스 검토 근거가 필요합니다')
        path=Path(source['file']);sid=hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            mel=load_melody(path,use_given_chords=False)
            # Fixed 48-bar sampling frame; omit its terminal segment below.
            mel=replace(mel,measures=mel.measures[:48])
            mel.notes=[n for n in mel.notes if n.onset<mel.total]
            if len(mel.measures)<10:continue
            keys=estimate_key(mel)
            motifs=analyze_motifs(mel)  # Default arguments, including cross-check.
            phrases,gaps=segment_layers(mel,keys.key,motifs)  # Default weights, melody only.
            local=[]
            for p in phrases[:-1][:min(3,30-counts[genre])]:
                first=max(0,p.first_bar-1);last=min(len(mel.measures)-1,p.last_bar+1)
                notation=[]
                for measure in mel.measures[first:last+1]:
                    notes=[n for n in mel.notes if measure.start<=n.onset<measure.end]
                    notation.append({'bar':measure.number,'length':str(measure.length),
                        'notes':[[str(n.onset-measure.start),str(n.dur),n.midi] for n in notes]})
                rels=[r for r in motifs.bar_relations if p.first_bar<=r.unit[0]<=p.last_bar]
                notes=mel.notes[p.first:p.last+1];peak=max(n.midi for n in notes)
                peak_onset=next(n.onset for n in notes if n.midi==peak)
                ending=notes[-1];nextnote=mel.notes[p.last+1] if p.last+1<len(mel.notes) else None
                row={'id':f'{genre}-{counts[genre]+len(local)+1:02}', 'genre':genre,'source':str(path),'source_sha256':sid,
                     'title':mel.title,'meter':f'{mel.beats}/{mel.beat_type}','key':keys.key.name,
                     'printed_bars':[mel.measures[p.first_bar].number,mel.measures[p.last_bar].number],
                     'start':str(p.start),'end':str(p.end),'length_bars':p.bars,'context':notation,
                     'end_note':[ending.midi,str(ending.dur)],'gap_after':str(nextnote.onset-ending.end) if nextnote else None,
                     'relations':[{'bar':mel.measures[r.unit[0]].number,'kind':r.kind,'model':r.model,'score':r.score} for r in rels],
                     'climax_position':float((peak_onset-p.start)/(p.end-p.start)) if p.end>p.start else None,
                     'type_prediction':None,'type_status':'기존 분석기는 sentence/period 유형을 출력하지 않음',
                     'inversion_fragment_status':'기존 bar relation에 inversion/fragment 분류가 없음. new/varied를 재명명하지 않음.',
                     'review':None,'use_scope':source['use_scope'],'license_reference':source['license_reference']}
                local.append(row)
            samples+=local;counts[genre]+=len(local)
            print(genre,counts[genre],path.name,flush=True)
        except Exception as exc:errors.append({'file':str(path),'error':str(exc)})
    dump(out/'audit.json',{'schema_version':1,'engine':'analyze_motifs(mel), segment_layers(mel,key,motifs): defaults',
        'sampling':'manifest order, first 3 nonterminal phrases per work; first 48 measures; 30 per genre; not representative population sampling',
        'samples':samples,'errors':errors,'counts':dict(counts)})
    return dict(counts)

def aggregate(audit):
    """No invented review labels, no publication of pitches or source excerpts."""
    result={'schema_version':1,'default_enabled':False,'basis':'인수인계: 장르당 30개 직접 감사, 경계 일치 70% 이상. 미판정은 일치로 세지 않음.',
            'genres':{},'unsupported':['automatic_sentence_period_type','inversion','fragment','continuation_function']}
    ids=[r['id'] for r in audit['samples']]
    if len(ids)!=len(set(ids)):raise ValueError('중복 감사 표본 id입니다')
    for genre in ('pop','jazz','classical'):
        rows=[r for r in audit['samples'] if r['genre']==genre]
        reviewed=[r for r in rows if isinstance(r.get('review'),dict)]
        for r in reviewed:
            v=r['review']
            if type(v.get('boundary_match')) is not bool or not isinstance(v.get('reason'),str) or not v['reason'].strip():raise ValueError('직접 검토에는 경계 판정과 이유가 필요합니다')
        yes=sum(r['review']['boundary_match'] for r in reviewed)
        enough=len(rows)==30 and len(reviewed)==30
        gate=enough and yes/30>=.7
        classification=bool(rows) and all(type(r.get('review',{}).get('type_match'))is bool and type(r.get('review',{}).get('transformation_match'))is bool for r in reviewed) and len(reviewed)==len(rows)
        licensed=bool(rows) and all(r['use_scope']=='licensed' for r in rows)
        publish=gate and licensed and classification
        summary={'sampled':len(rows),'reviewed':len(reviewed),'boundary_matches':yes,'denominator':30,
                 'boundary_rate':yes/30 if enough else None,'accuracy_gate_passed':gate,'ranking_eligible':publish,
                 'classification_audit_complete':classification,
                 'status':'eligible' if publish else 'license_review_required' if gate and not licensed else 'classification_audit_incomplete' if gate else 'boundary_below_70_percent' if enough else 'manual_audit_incomplete',
                 'license_references':sorted({r['license_reference'] for r in rows})}
        if publish:
            summary['phrase_length_counts']=dict(Counter(str(r['length_bars']) for r in rows))
            summary['relation_counts']=dict(Counter(x['kind'] for r in rows for x in r['relations']))
            summary['relation_denominator']=sum(len(r['relations']) for r in rows)
            summary['climax_mean_position']=sum(r['climax_position'] for r in rows if r['climax_position'] is not None)/len(rows)
        result['genres'][genre]=summary
    return result

def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('prepare');p.add_argument('manifest');p.add_argument('--out',required=True)
    p=sub.add_parser('aggregate');p.add_argument('audit');p.add_argument('--out',required=True)
    args=ap.parse_args()
    if args.cmd=='prepare':print(prepare(args.manifest,args.out))
    else:dump(args.out,aggregate(json.loads(Path(args.audit).read_text(encoding='utf-8-sig'))))

if __name__=='__main__':main()
