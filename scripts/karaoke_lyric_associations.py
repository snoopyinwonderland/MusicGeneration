"""Describe lyric-cue and music co-occurrence. Only aggregate results leave memory."""
import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
import re
import sqlite3
import zlib

from musigen.karaoke_statistics import chord_quality, dec, rap_mask, read_smf, track_name

# These are explicit lexical cues, not validated listener-emotion labels.
CUES = json.loads(Path(__file__).with_name('karaoke_lyric_cues.json').read_text('utf8'))
MATCH = {label: re.compile('|'.join(map(re.escape, words['ko'])) +
                           r'|\b(?:' + '|'.join(map(re.escape, words['en'])) + r')\b', re.I)
         for label, words in CUES.items()}
SYLLABLE_SPACE = re.compile(r'(?<=[가-힣])\s+(?=[가-힣])')


def cue_labels(text):
    # KY can pad every Hangul syllable with a space, even within a single word.
    normalized = SYLLABLE_SPACE.sub('',text)
    return [k for k,regex in MATCH.items() if regex.search(normalized)]


def lines(track):
    tokens = []
    for tick, kind, typ, payload in track:
        if kind != 'meta' or typ != 5:
            continue
        for part in re.split(r'([\r\n]+)', dec(payload)):
            if part.startswith(('\r', '\n')):
                if tokens:
                    yield tokens
                    tokens = []
            elif part:
                tokens.append((tick, part))
    if tokens:
        yield tokens


def describe(notes, ppq, chords, chord_ticks):
    pitches = [n[2] for n in notes]
    intervals = [b-a for a,b in zip(pitches,pitches[1:])]
    durations = [(b-a)/ppq for a,b,_ in notes]
    span = (notes[-1][1]-notes[0][0])/ppq
    values = {'note_count':len(notes),'range_st':max(pitches)-min(pitches), 'net_rise_st':pitches[-1]-pitches[0],
              'onsets_per_beat':len(notes)/span,'ending_beats':durations[-1],
              'leap_share':sum(abs(i)>=5 for i in intervals)/len(intervals),
              'repeat_share':intervals.count(0)/len(intervals)}
    rhythms = ['s' if d<=.5 else 'm' if d<=1 else 'l' for d in durations]
    contour = ['+' if i>0 else '-' if i<0 else '=' for i in intervals]
    shapes = [str(i) if abs(i)<=2 else ('+' if i>0 else '-')+('3:4' if abs(i)<=4 else '5+') for i in intervals]
    patterns = {}
    for name,seq,length in [('rhythm4',rhythms,4),('contour4',contour,3),('melody4',shapes,3)]:
        patterns[name] = Counter('/'.join(seq[i:i+length]) for i in range(len(seq)-length+1))
    attacks = [(y[0]-x[0])/ppq for x,y in zip(notes,notes[1:])]
    spacing = ['s' if t<=.5 else 'm' if t<=1 else 'l' for t in attacks]
    patterns['timed_shape'] = Counter(''.join(contour[i:i+3])+' '+''.join(spacing[i:i+3])
                                      for i in range(len(contour)-2))
    start = bisect_right(chord_ticks,notes[0][0])-1
    stop = bisect_right(chord_ticks,notes[-1][0])
    active = chords[max(0,start):stop]
    transitions = []
    harmony = Counter()
    for (_,a),(_,b) in zip(active,active[1:]):
        if a and b:
            transitions.append((b['root']-a['root'])%12)
            harmony[f'{chord_quality(a)} +{transitions[-1]} {chord_quality(b)}'] += 1
    patterns['harmony'] = harmony
    patterns['root_motion'] = Counter(map(str,transitions))
    if transitions:
        values['root_plus5_share'] = transitions.count(5)/len(transitions)
    if start>=0 and active and all(c for _,c in active):
        values['chord_changes_per_beat'] = (len(active)-1)/span
        values['minor_chord_onset_share'] = sum(
            chord_quality(chords[bisect_right(chord_ticks,n[0])-1][1]).startswith('minor') for n in notes)/len(notes)
    return values,patterns


def worker(args):
    database, bounds = args
    coverage = Counter()
    moments = defaultdict(Counter)
    patterns = defaultdict(Counter)
    con = sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)
    for path,status,payload in con.execute('SELECT path,status,payload FROM files WHERE rowid BETWEEN ? AND ?',bounds):
        coverage['files'] += 1
        if status!='ok':
            coverage['source_excluded'] += 1
            continue
        rec = json.loads(zlib.decompress(payload))['record']
        raw = Path(path)
        if sha256(raw.read_bytes()).hexdigest()!=rec['sha256']:
            raise ValueError(f'Source changed: {path}')
        track, = [t for t in read_smf(path)[2] if track_name(t).strip().upper()=='S1']
        notes = rec['notes']
        starts = {n[0]:i for i,n in enumerate(notes)}
        masked = rap_mask(notes)
        chord_ticks = [t for t,_ in rec['chords']]
        seen = set()
        song = defaultdict(Counter)
        by_length = defaultdict(Counter)
        flags = set()
        for tokens in lines(track):
            text = ''.join(s for _,s in tokens).strip().casefold()
            if not text:
                continue
            coverage['text_lines'] += 1
            flags.add('with_text')
            script = 'ko' if re.search('[가-힣]',text) else 'latin' if re.search('[a-z]',text) else 'other'
            coverage['text_'+script] += 1
            if script=='other':
                continue
            ticks = [t for t,s in tokens if s.strip()]
            if any(t not in starts for t in ticks):
                coverage['unaligned'] += 1
                continue
            a,b = starts[ticks[0]], starts[ticks[-1]]
            segment = notes[a:b+1]
            if len(segment)<4 or any(i in masked for i in range(a,b+1)):
                coverage['short_or_rap'] += 1
                continue
            if any(y[0]<x[1] or y[0]-x[1]>=2*rec['ppq'] for x,y in zip(segment,segment[1:])):
                coverage['overlap_or_long_gap'] += 1
                continue
            key = (text,tuple((s-segment[0][0],e-s,p-segment[0][2]) for s,e,p in segment),
                   tuple((t-segment[0][0] if t>segment[0][0] else 0,str(c)) for t,c in
                         rec['chords'][max(0,bisect_right(chord_ticks,segment[0][0])-1):bisect_right(chord_ticks,segment[-1][0])]))
            if key in seen:
                coverage['duplicate_lines'] += 1
                continue
            seen.add(key)
            labels = cue_labels(text)
            flags.add('analyzed')
            coverage['analyzed_lines'] += 1
            if labels:
                coverage['cue_lines'] += 1
                flags.add('with_cue')
            values,grams = describe(segment,rec['ppq'],rec['chords'],chord_ticks)
            for label in labels or ['unmarked']:
                group = script+'/'+label
                coverage[group+'/lines'] += 1
                for metric,value in values.items():
                    song[group,metric]['sum'] += value
                    song[group,metric]['n'] += 1
                    by_length[group,metric,len(segment)]['sum'] += value
                    by_length[group,metric,len(segment)]['n'] += 1
                for family,counts in grams.items():
                    patterns[group,family].update(counts)
        coverage.update('files_'+flag for flag in flags)
        matched = defaultdict(Counter)
        for (group,metric,length),row in by_length.items():
            if group.endswith('/unmarked'):
                continue
            ref = by_length.get((group.split('/')[0]+'/unmarked',metric,length))
            if ref:
                matched[group,metric]['sum'] += row['sum']-row['n']*ref['sum']/ref['n']
                matched[group,metric]['n'] += row['n']
        for key,row in matched.items():
            moments[key]['matched_sum'] += row['sum']/row['n']
            moments[key]['matched_files'] += 1
        for (group,metric),row in song.items():
            mean = row['sum']/row['n']
            entry = moments[group,metric]
            entry['files'] += 1
            entry['sum'] += mean
            ref = song.get((group.split('/')[0]+'/unmarked',metric))
            if ref and not group.endswith('/unmarked'):
                delta = mean-ref['sum']/ref['n']
                entry['pairs'] += 1
                entry['delta'] += delta
                entry['delta2'] += delta*delta
    con.close()
    return coverage,dict(moments),dict(patterns)


def run(database,out,workers):
    database = database.resolve()
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as con:
        last,total = con.execute('SELECT max(rowid),count(*) FROM files').fetchone()
    jobs = [(database,(a,a+499)) for a in range(1,last+1,500)]
    counts,metrics,patterns = Counter(),defaultdict(Counter),defaultdict(Counter)
    with ProcessPoolExecutor(workers) as pool:
        for i,(c,m,p) in enumerate(pool.map(worker,jobs),1):
            counts.update(c)
            for k,v in m.items():metrics[k].update(v)
            for k,v in p.items():patterns[k].update(v)
            if i%10==0:print(i,'/',len(jobs),flush=True)
    assert counts['files']==total
    rows = {}
    for (group,metric),v in sorted(metrics.items()):
        n=v['pairs']
        se=sqrt(max(0,v['delta2']-v['delta']**2/n)/(n-1)/n) if n>1 else None
        rows.setdefault(group,{})[metric]={'files':v['files'],'mean':v['sum']/v['files'],'pairs':n,
            'difference':v['delta']/n if n else None,'paired_se':se,
            'matched_files':v['matched_files'],
            'matched_difference':v['matched_sum']/v['matched_files'] if v['matched_files'] else None}
    hist={}
    for (group,family),v in sorted(patterns.items()):
        hist.setdefault(group,{})[family]={'total':v.total(),'counts':dict(v.most_common())}
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'coverage':counts,'metrics':rows,'patterns':hist},ensure_ascii=False),encoding='utf8')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('database',type=Path)
    parser.add_argument('out',type=Path)
    parser.add_argument('--workers',type=int,default=8)
    args=parser.parse_args()
    run(args.database,args.out,args.workers)
