"""Local melody evidence census. Role-labelled lines and unknown voices stay separate."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
import gzip,hashlib,json,re,sqlite3,time,zlib
from pathlib import Path
from musigen.corpus_features import read_xml,midi_features

VERSION=1
ROLES={'documented_melody','named_melody','lyric_voice','single_line_score','unknown_voice'}
PRIMARY=ROLES-{'unknown_voice'}
EXT={'.xml','.musicxml','.mxl','.mid','.midi','.kar','.krn'}
KNOWN_HASHES=None


def initialize_worker(known_hashes):
    global KNOWN_HASHES
    KNOWN_HASHES=set(known_hashes)


def packed(events):
    return [[str(on),str(dur),pitch] for on,dur,pitch in events]


def unpacked(events):
    return [(F(a),F(b),int(c)) for a,b,c in events]


def fingerprint(events):
    first,pitch=events[0][0],events[0][2]
    return hashlib.sha256(json.dumps([[str(a-first),str(b),c-pitch] for a,b,c in events],separators=(',',':')).encode()).hexdigest()


def features(events):
    """Per-line facts, with denominators. No phrase inference or quality rating."""
    ints=[b[2]-a[2] for a,b in zip(events,events[1:])]
    gaps=[b[0]-a[0]-a[1] for a,b in zip(events,events[1:])]
    intervals=Counter(ints);durations=Counter(str(b) for a,b,c in events)
    leaps=[i for i,v in enumerate(ints[:-1]) if abs(v)>4]
    reversals=sum(ints[i]*ints[i+1]<0 for i in leaps)
    span=events[-1][0]+events[-1][1]-events[0][0]
    high=max(n[2] for n in events)
    return {'attacks':len(events),'interval_pairs':len(ints),'intervals':dict(intervals),
        'duration_counts':dict(durations),'pitch_range':high-min(n[2] for n in events),
        'step_pairs':sum(0<abs(n)<=2 for n in ints),'repeated_pitch_pairs':intervals[0],
        'rest_gaps':sum(g>0 for g in gaps),'rest_quarters':str(sum((max(F(0),g) for g in gaps),F(0))),
        'overlap_pairs':sum(g<0 for g in gaps),'span_quarters':str(span),
        'leaps_with_successor':len(leaps),'leaps_then_opposite_direction':reversals,
        'climax_position':float((next(a for a,b,c in events if c==high)-events[0][0])/span) if span else None}


def line(track,role,basis,events):
    events=sorted(events)
    if len(events)<8:return None
    if any(d<=0 for _,d,_ in events):return None
    # Distinct pitches at the same onset are polyphony, never a top-note melody.
    if len({n[0] for n in events})!=len(events):return None
    return {'track':str(track),'role':role,'basis':basis,'fingerprint':fingerprint(events),
            'events':zlib.compress(json.dumps(packed(events),separators=(',',':')).encode()),'features':features(events)}


def xml_lines(path,source):
    root=read_xml(path);groups=defaultdict(list);lyrics=Counter();problems=Counter();names={p.get('id'):p.findtext('part-name','') for p in root.findall('part-list/score-part')}
    for part in root.findall('part'):
        div=None;meter=None;absolute=F(0);active={}
        for bar,measure in enumerate(part.findall('measure')):
            cursor=F(0);extent=F(0);previous=None
            for el in measure:
                if el.tag=='attributes':
                    if el.find('divisions') is not None:
                        div=F(el.findtext('divisions'))
                        if div<=0:raise ValueError('nonpositive divisions')
                    t=el.find('time')
                    if t is not None and t.find('beats') is not None:
                        meter=F(4*sum(int(s) for s in t.findtext('beats').split('+')),int(t.findtext('beat-type')))
                elif el.tag in ('backup','forward'):
                    if div is None:raise ValueError('cursor before divisions')
                    delta=F(el.findtext('duration','0'))/div
                    if delta<0:raise ValueError('negative cursor duration')
                    cursor+=delta if el.tag=='forward' else -delta
                    if cursor<0:raise ValueError('negative cursor')
                    extent=max(extent,cursor);previous=None
                elif el.tag=='note':
                    if el.find('grace') is not None:problems['grace_not_timed']+=1;continue
                    if div is None:raise ValueError('note before divisions')
                    dur=F(el.findtext('duration','0'))/div
                    if dur<=0:raise ValueError('nonpositive note duration')
                    chord=el.find('chord') is not None
                    if chord and previous is None:raise ValueError('orphan chord')
                    onset=previous if chord else cursor
                    if not chord:previous=cursor;cursor+=dur
                    extent=max(extent,onset+dur)
                    pitch=el.find('pitch')
                    if pitch is None:continue
                    alter=F(pitch.findtext('alter','0'))
                    if alter.denominator!=1:problems['microtonal_excluded']+=1;continue
                    midi=12*(int(pitch.findtext('octave'))+1)+dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[pitch.findtext('step')]+int(alter)
                    key=(part.get('id'),el.findtext('staff','1'),el.findtext('voice','1'))
                    lyrics[key]+=len(el.findall('lyric'))
                    ties={t.get('type') for t in el.findall('tie')};tk=(key,midi);on=absolute+onset
                    if 'stop' in ties and tk in active:
                        event=groups[key][active[tk]]
                        if event[0]+event[1]!=on:raise ValueError('discontinuous tie')
                        event[1]+=dur
                    else:
                        if 'stop' in ties:problems['orphan_tie_stop']+=1
                        groups[key].append([on,dur,midi]);active[tk]=len(groups[key])-1
                    if 'start' not in ties:active.pop(tk,None)
            # Preserve incomplete written measures rather than fabricate missing rests.
            absolute+=extent if extent else meter or F(0)
    candidate=[]
    for key,events in groups.items():
        name=names.get(key[0],'');role='unknown_voice';basis='written staff/voice; main melody not identified'
        if source.startswith('kysing') and re.search(r'\bS1\b',name,re.I):role='documented_melody';basis='KYSing S1 vocal track, converter source survey 2026-10-05'
        elif re.search(r'\b(melody|vocal|voice|soprano|tenor|singing)\b|멜로디|주선율',name,re.I):role='named_melody';basis='explicit part name; may be an ensemble vocal line'
        elif lyrics[key]>=8:role='lyric_voice';basis='at least 8 lyric-marked notes; lyric-bearing voice, not certified sole theme'
        elif len(groups)==1:role='single_line_score';basis='only one pitched staff/voice; at least 8 attacks'
        item=line('/'.join(key),role,basis,events)
        if item:candidate.append(item)
        else:problems['polyphonic_or_short_voice']+=1
    meta={'title':root.findtext('work/work-title') or root.findtext('movement-title') or path.stem,
        'creators':[e.text for e in root.findall('identification/creator') if e.text],
        'parts':names,'issues':dict(problems),'pitch_basis':'written_not_concert','repeats':'not_expanded'}
    return meta,candidate


def midi_lines(path,source):
    data=midi_features(path,include_notes=True);out=[];issues=Counter(data['warnings'])
    for tr in data['tracks']:
        groups=defaultdict(list)
        for start,end,ch,pitch,vel in tr['note_events']:
            if ch!=9 and end>start:groups[ch].append((F(start,data['ppq']),F(end-start,data['ppq']),pitch))
        for ch,notes in groups.items():
            role='unknown_voice';basis='MIDI track/channel; melody role unknown'
            if source=='kysing-midi' and tr['name'].upper()=='S1' and ch==3:role='documented_melody';basis='KYSing S1/channel 4 vocal melody'
            elif source.endswith('/pop909') and tr['name'].upper()=='MELODY':role='documented_melody';basis='POP909 author MELODY track'
            elif re.search(r'\b(melody|vocal|vocals|voice|singing)\b|멜로디|주선율',tr['name'],re.I):role='named_melody';basis='explicit MIDI track name'
            item=line(f"{tr['track']}/{ch}",role,basis,notes)
            if item:out.append(item)
            else:issues['polyphonic_or_short_track']+=1
    return {'title':path.stem,'issues':dict(issues),'meters':data['meters'],
        'pitch_basis':'sounding_midi','timing':'performance_ticks_not_quantized'},out


def kern_lines(path,source):
    """Strict single **kern spine only. Spine manipulation/polyphony is deferred."""
    rows=path.read_text(encoding='utf-8-sig').splitlines();column=None;at=F(0);events=[];active=None
    title=path.stem
    for row in rows:
        if row.startswith('!!!OTL:'):title=row.split(':',1)[1].strip()
        if row.startswith('**'):
            cells=row.split('\t');cols=[i for i,c in enumerate(cells) if c=='**kern']
            if len(cols)!=1:raise ValueError('kern multiple note spines: role unresolved')
            column=cols[0];continue
        if not row or row.startswith('!') or row.startswith('='):continue
        if row.startswith('*'):
            if any(c in ('*^','*v','*x','*+') for c in row.split('\t')):raise ValueError('kern dynamic spines unsupported')
            continue
        if column is None:raise ValueError('kern missing spine')
        cells=row.split('\t')
        if len(cells)<=column:raise ValueError('kern spine count')
        token=cells[column]
        if token=='.':continue
        if ' ' in token:raise ValueError('kern chord')
        if 'q' in token:continue
        m=re.search(r'(0+|[1-9][0-9]*)(\.*)',token)
        if not m:raise ValueError('kern duration')
        den,dots=m.groups();dur=F(4,int(den)) if int(den) else F(4*2**len(den))
        dur*=sum((F(1,2**i) for i in range(len(dots)+1)),F(0))
        if 'r' not in token:
            p=re.search(r'([a-g]+|[A-G]+)([#n-]*)',token)
            if not p or len(set(p[1]))!=1:raise ValueError('kern pitch')
            letters,acc=p.groups();octave=3+len(letters) if letters.islower() else 4-len(letters)
            midi=12*(octave+1)+dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[letters[0].upper()]+acc.count('#')-acc.count('-')
            if (']' in token or '_' in token) and active is not None:
                if events[active][2]!=midi or events[active][0]+events[active][1]!=at:raise ValueError('kern tie')
                events[active][1]+=dur
            else:events.append([at,dur,midi]);active=len(events)-1
            if '[' not in token and '_' not in token:active=None
        at+=dur
    item=line('kern', 'single_line_score','single static **kern note spine',events)
    return {'title':title,'pitch_basis':'written_not_concert','repeats':'not_expanded'},[item] if item else []


def inspect_file(job):
    path,source=job;path=Path(path)
    result={'path':str(path),'source':source,'status':'error','lines':[]}
    try:
        before=path.stat()
        if before.st_size>100_000_000:raise ValueError('file over 100 MB: deferred')
        result['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        if KNOWN_HASHES is not None and result['sha256'] in KNOWN_HASHES:
            after=path.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('source changed during read')
            result.update(status='duplicate_bytes',metadata={'same_bytes_as_previously_read_sha256':result['sha256']})
            return result
        if path.suffix.lower() in ('.xml','.musicxml','.mxl'):meta,lines=xml_lines(path,source)
        elif path.suffix.lower()=='.krn':meta,lines=kern_lines(path,source)
        else:meta,lines=midi_lines(path,source)
        after=path.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('source changed during read')
        result.update(status='read',metadata=meta,lines=lines)
        if KNOWN_HASHES is not None:KNOWN_HASHES.add(result['sha256'])
    except Exception as e:result['reason']=type(e).__name__+': '+str(e)[:180]
    return result


def connect(path):
    db=sqlite3.connect(path);db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=NORMAL')
    db.executescript('CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, source TEXT, sha TEXT, status TEXT, reason TEXT, metadata TEXT); CREATE INDEX IF NOT EXISTS file_sha ON files(sha); CREATE TABLE IF NOT EXISTS lines(fingerprint TEXT PRIMARY KEY, path TEXT, source TEXT, track TEXT, role TEXT, basis TEXT, events BLOB, features TEXT); CREATE INDEX IF NOT EXISTS line_role ON lines(role);')
    return db


def selection(row):
    sid,path=row['source'],Path(row['path']);ext=path.suffix.lower()
    if sid=='aihub-gugak' or sid.startswith('korean-traditional-music/'):return 'excluded_unconfirmed_traditional_source'
    if sid in ('pdmx-search-xml','kysing-xml','kysing-leadsheets'):return 'derived_mirror_primary_source_selected'
    if ext not in EXT:return 'metadata_audio_archive_or_unsupported_format'
    if sid.endswith('/pop909') and 'versions' in path.parts:return 'alternate_arrangement_same_work'
    return None


def run(out,workers=4,limit=0):
    out=Path(out);db=connect(out/'melodies.sqlite3');done={r[0] for r in db.execute('SELECT path FROM files')}
    seen={r[0] for r in db.execute("SELECT sha FROM files WHERE status IN ('read','duplicate_bytes')") if r[0]}
    jobs=[];coverage=defaultdict(Counter)
    with gzip.open(out/'files.jsonl.gz','rt',encoding='utf-8') as f:
        for text in f:
            row=json.loads(text);reason=selection(row);coverage[row['source']]['inventory_files']+=1
            if reason:coverage[row['source']][reason]+=1;continue
            coverage[row['source']]['eligible_files']+=1
            if row['path'] not in done:jobs.append((row['path'],row['source']))
    # Complete named datasets first; no random/title sampling. limit is explicitly a partial run.
    jobs.sort(key=lambda j:(0 if j[1]=='kysing-midi' else 1 if j[1].endswith('/pop909') else 2 if j[1].startswith('local-musicxml') else 3,j[1],j[0]))
    if limit:jobs=jobs[:limit]
    started=time.time();n=0
    def bounded(pool):
        remaining=iter(jobs);pending=deque()
        for _ in range(workers*3):
            job=next(remaining,None)
            if job is not None:pending.append(pool.submit(inspect_file,job))
        while pending:
            yield pending.popleft().result()
            job=next(remaining,None)
            if job is not None:pending.append(pool.submit(inspect_file,job))
    with ProcessPoolExecutor(max_workers=workers,initializer=initialize_worker,initargs=(seen,)) as pool:
        for r in bounded(pool):
            sha=r.get('sha256');status=r['status']
            if status=='read' and sha in seen:status='duplicate_bytes'
            elif status=='read':
                seen.add(sha)
                for v in r['lines']:
                    db.execute('INSERT INTO lines VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET path=excluded.path,source=excluded.source,track=excluded.track,role=excluded.role,basis=excluded.basis WHERE lines.role="unknown_voice" AND excluded.role!="unknown_voice"',
                        (v['fingerprint'],r['path'],r['source'],v['track'],v['role'],v['basis'],v['events'],json.dumps(v['features'])))
            db.execute('INSERT INTO files VALUES(?,?,?,?,?,?)',(r['path'],r['source'],sha,status,r.get('reason'),json.dumps(r.get('metadata',{}),ensure_ascii=False)))
            n+=1
            if n%250==0:
                db.commit();progress={'done_this_run':n,'jobs_this_run':len(jobs),'seconds':round(time.time()-started),'lines':db.execute('SELECT count(*) FROM lines').fetchone()[0]}
                (out/'progress.json').write_text(json.dumps(progress),encoding='utf-8');print(json.dumps(progress),flush=True)
    db.commit()
    for sid,status,count in db.execute('SELECT source,status,count(*) FROM files GROUP BY source,status'):coverage[sid][status]+=count
    report={'version':VERSION,'scope':'local observations and similarity reference, not automatic training',
        'sources':{s:dict(c) for s,c in coverage.items()},'unique_lines':db.execute('SELECT count(*) FROM lines').fetchone()[0],
        'roles':dict(db.execute('SELECT role,count(*) FROM lines GROUP BY role')),'limit_this_run':limit}
    report['remaining_eligible']=sum(c['eligible_files']-c['read']-c['duplicate_bytes']-c['error'] for c in coverage.values())
    (out/'melody-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');db.close();return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description='명시 선율과 미확정 성부를 분리하는 로컬 자료 전수 검사');p.add_argument('--out',type=Path,required=True);p.add_argument('--workers',type=int,default=4);p.add_argument('--limit',type=int,default=0);a=p.parse_args();print(json.dumps(run(a.out,a.workers,a.limit),ensure_ascii=False))
