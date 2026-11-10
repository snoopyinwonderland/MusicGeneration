"""Explicit monophonic MusicXML region to a portable motif; never infer a lead voice."""
import argparse
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path
from musigen.corpus_features import xml_features
from musigen.motif_clip import read_events


def extract(path, part, staff, voice, start_measure, start_offset, end_measure, end_offset):
    path=Path(path)
    meta,rows=xml_features(path)
    rows=[r for r in rows if r['part']==part]
    def index(label):
        found=[i for i,r in enumerate(rows) if r['printed_bar']==str(label)]
        if len(found)!=1:raise ValueError('마디 번호가 없거나 중복됩니다')
        return found[0]
    a,z=index(start_measure),index(end_measure)
    start,end=F(start_offset),F(end_offset)
    if a>z or start<0 or end<0:raise ValueError('선택 순서 오류')
    selected=rows[a:z+1]
    lengths=[F(r['extent_quarters']) for r in selected]
    if any(n<=0 for n in lengths) or start>=lengths[0] or end>lengths[-1]:
        raise ValueError('명시적인 마디 길이 밖의 선택입니다')
    stop=sum(lengths[:-1],F(0))+end
    if start>=stop:raise ValueError('빈 선택')
    notes=[];base=F(0);warnings=[]
    for row,length in zip(selected,lengths):
        for n in row['notes']:
            if n['staff']!=str(staff) or n['voice']!=str(voice):continue
            on=base+F(n['on']);off=on+F(n['dur'])
            if n['grace']:
                if start<=on<stop:warnings.append('선택 구간의 장식음은 제외했습니다.')
                continue
            if off<=start or on>=stop:continue
            if n['ties']:raise ValueError('붙임줄이 있는 구간은 현재 악보 작업실에서 가져오세요')
            if n['unpitched'] or (not n['rest'] and not n['spelling']):raise ValueError('음높이 없는 사건')
            if on<start or off>stop:warnings.append('경계 밖 음가를 잘라 선택 길이만 가져왔습니다.')
            pitches=[]
            if not n['rest']:
                step,alter,octave=n['spelling'];alt=F(alter)
                if alt.denominator!=1:raise ValueError('미분음은 지원하지 않습니다')
                alt=int(alt);pitches=[step+('#'*alt if alt>=0 else 'b'*(-alt))+str(octave)]
            notes.append((max(on,start),min(off,stop),pitches))
        base+=length
    if not notes:raise ValueError('선택한 성부에 사건이 없습니다')
    events=[];cursor=start
    for on,off,pitches in sorted(notes):
        if on<cursor:raise ValueError('단선율 성부만 지원합니다: 겹친 음 또는 화음')
        if on>cursor:events.append({'duration':str(on-cursor),'pitches':[]})
        events.append({'duration':str(off-on),'pitches':pitches});cursor=off
    if cursor<stop:events.append({'duration':str(stop-cursor),'pitches':[]})
    clip={'format':'musicanote-motif','version':1,'name':'input','events':events,
          'source':{'file':path.name,'part':part,'staff':str(staff),'voice':str(voice),
                    'start':{'measure':str(start_measure),'offset':str(start)},
                    'end':{'measure':str(end_measure),'offset':str(end)},
                    'pitch':'written','repeats':'not-expanded'},'warnings':sorted(set(warnings))}
    read_events(clip)
    provenance={'source_path':str(path.resolve()),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'metadata':meta,'selection':clip['source'],'quarters':str(stop-start),
                'metric_context':'clip retains event durations, not original bar/pickup placement',
                'rights_status':'raw metadata only; no edition redistribution permission inferred'}
    return clip,provenance


if __name__=='__main__':
    p=argparse.ArgumentParser(description='기존 악보의 명시한 단선율 구간 가져오기')
    for name in ('source','part','staff','voice','start-measure','start-offset','end-measure','end-offset','out'):
        p.add_argument('--'+name,required=True)
    a=p.parse_args();out=Path(a.out)
    if out.exists():raise ValueError('새 출력 폴더를 지정하세요')
    clip,provenance=extract(a.source,a.part,a.staff,a.voice,a.start_measure,a.start_offset,a.end_measure,a.end_offset)
    out.mkdir(parents=True)
    for name,value in [('motif.json',clip),('source.json',provenance)]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'out':str(out),'events':len(clip['events']),'quarters':provenance['quarters']},ensure_ascii=False))
