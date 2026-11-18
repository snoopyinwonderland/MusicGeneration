"""Aggregate song-local, touching two-bar windows of equal length, read-only."""
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path


def state(attacks, first, last):
    direction = 'up' if last-first > 2 else 'down' if first-last > 2 else 'level'
    density = 'sparse' if attacks <= 6 else 'medium' if attacks <= 11 else 'dense'
    return direction + '/' + density


def aggregate(database):
    db = sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True)
    counts = defaultdict(Counter)
    songs = set()
    previous = None
    windows = 0
    for song, start, end, features in db.execute(
            'SELECT song_id,start,end,features FROM blocks WHERE bars=2 ORDER BY song_id,start'):
        window = json.loads(features)
        label = state(window['attacks'], window['first'], window['last'])
        if previous:
            ident, boundary, length, prior, last = previous
            if song == ident and start == boundary and end-start == length:
                entry = max(-7, min(7, window['first']-last))
                counts[prior][f'{label}:{entry}'] += 1
                songs.add(song)
        previous = song, end, end-start, label, window['last']
        windows += 1
    relations = dict(db.execute("SELECT pattern,occurrences FROM patterns WHERE family='melody.block_2_adjacent_relation'"))
    db.close()
    return dict(windows=windows, songs=len(songs), pairs=sum(sum(c.values()) for c in counts.values()),
                transitions=counts, census_relations=relations)


if __name__ == '__main__':
    result = aggregate(sys.argv[1])
    Path(sys.argv[2]).write_text(json.dumps(result, sort_keys=True, indent=2)+'\n', encoding='utf8')
    print({k:v for k,v in result.items() if k!='transitions'})
