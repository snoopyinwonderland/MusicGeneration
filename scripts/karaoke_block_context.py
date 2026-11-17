"""Compare repeated-block weighting without changing the primary census."""
from bisect import bisect_left
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys
import zlib


def run(root):
    db=sqlite3.connect((root/'statistics.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    seen=set();all_intervals=Counter();unique_intervals=Counter();meters=Counter();keys=Counter();markers=Counter()
    totals=Counter()
    for payload, in db.execute("SELECT payload FROM files WHERE status='ok' ORDER BY path"):
        value=json.loads(zlib.decompress(payload));r=value['record'];a=value['analysis']
        if r['melody_fingerprint'] in seen:continue
        seen.add(r['melody_fingerprint'])
        totals['unique_melodies']+=1
        meters.update({f'{num}/{den}' for _,num,den in r['meters']})
        modes={minor for _,_,minor in r['keys']}
        keys['major_and_minor' if len(modes)>1 else 'major_only' if modes=={0} else 'minor_only' if modes=={1} else 'unknown']+=1
        markers.update({label for _,label in r['markers']})
        if r['unknown_labels']:totals['files_with_unparsed_chord_labels']+=1
        if not any(c for _,c in r['chords']):totals['files_without_any_parsed_chord']+=1
        if not r['keys']:totals['files_without_explicit_key']+=1
        if not r['meters']:totals['files_without_explicit_meter']+=1
        notes=r['notes'];onsets=[n[0] for n in notes];unique=set()
        for block in a['blocks']:
            if block['bars']!=2:continue
            start,end=block['start'],block['end']
            window=notes[bisect_left(onsets,start):bisect_left(onsets,end)]
            fingerprint=tuple((t-start,z-t,p-window[0][2]) for t,z,p in window)
            intervals=[b[2]-a[2] for a,b in zip(window,window[1:]) if 0<=b[0]-a[1]<r['ppq']]
            all_intervals.update(intervals);totals['all_two_bar_blocks']+=1
            if fingerprint in unique:continue
            unique.add(fingerprint);totals['unique_two_bar_blocks_within_song']+=1
            unique_intervals.update(intervals)
    db.close()
    result={'scope':'Same accepted non-overlapping two-bar windows, all occurrences vs once per relative pitch+timing shape within each melody. Other windows and cross-window intervals excluded.',
            'totals':dict(totals),'all_two_bar_intervals':dict(all_intervals),'unique_two_bar_intervals':dict(unique_intervals),
            'meter_document_support':dict(meters),'explicit_key_modes':dict(keys),'marker_document_support':dict(markers)}
    (root/'block-context.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'totals':dict(totals),'keys':dict(keys),'meters':dict(meters)}))


if __name__=='__main__':run(Path(sys.argv[1]))
