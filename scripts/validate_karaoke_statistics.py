"""Cross-check vocal notes using Composition's separate SMF note reader."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import zlib

from musigen.karaoke_statistics import analyze, rap_mask, encoded
from kysing_leadsheet.kysing_leadsheet import read_smf, notes_of, track_name


def main(root, count):
    db=sqlite3.connect((root/'statistics.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    all_paths=[p for p, in db.execute("SELECT path FROM files WHERE status='ok' ORDER BY path")]
    selected=sorted({all_paths[round(i*(len(all_paths)-1)/max(1,count-1))] for i in range(count)})
    checks=[]
    for path in selected:
        payload,=db.execute('SELECT payload FROM files WHERE path=?',(path,)).fetchone()
        stored=json.loads(zlib.decompress(payload));r=stored['record'];notes=[];meters=[];chord_times=[]
        _,division,tracks=read_smf(path)
        for track in tracks:
            name=track_name(track).strip().upper()
            if name=='S1':
                notes.extend([a,b,p] for a,b,p,ch in notes_of(track) if ch==3)
            for tick,kind,typ,payload in track:
                if kind!='meta':continue
                if typ==0x58:meters.append((tick,payload[0],2**payload[1]))
                if name=='CHORD' and typ in (1,5) and payload.strip():chord_times.append(tick)
        assert sorted(notes)==r['notes'],path
        assert sorted(set(meters))==[tuple(x) for x in r['meters']],path
        assert division==r['ppq'],path
        assert all(t in chord_times for t,_ in r['chords']),path
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==r['sha256'],path
        recomputed=analyze(r)
        assert encoded(recomputed)==encoded(stored['analysis']),path
        # Independently derive adjacent-pair denominators after rap removal and >=1 beat gaps.
        excluded=rap_mask(r['notes'])
        pairs=sum(i not in excluded and i+1 not in excluded and 0<=b[0]-a[1]<r['ppq']
                  for i,(a,b) in enumerate(zip(r['notes'],r['notes'][1:])))
        assert pairs==sum(recomputed['melody'].get('interval',{}).values()),path
        checks.append({'id':r['id'],'notes':len(notes),'independent_note_events_equal':True,
                       'meters_equal':True,'source_hash_equal':True,'analysis_repeat_equal':True,
                       'interval_denominator_equal':True})
    integrity=db.execute('PRAGMA quick_check').fetchone()[0]
    db.close()
    report={'selection':'uniformly spaced successful file paths; not full-dataset parser certification',
            'independent_reader':'Composition read_smf/notes_of vs musigen.corpus_features.midi_features',
            'checks':checks,'sqlite_quick_check':integrity}
    dest=root/'validation';dest.mkdir(exist_ok=True)
    (dest/'crosscheck.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    print(json.dumps({'checked':len(checks),'sqlite':integrity}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--count',type=int,default=64)
    a=p.parse_args();main(a.root,a.count)
