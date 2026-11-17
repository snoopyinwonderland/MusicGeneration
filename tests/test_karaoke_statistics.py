import unittest
import json
from pathlib import Path
import tempfile
import zlib
from musigen.karaoke_statistics import aggregate, analyze, ambiguous_vocal_overlap, bar_grid, chord_quality, connect, degree, rap_mask, split_runs


def record(notes, chords=(), keys=((0,0,0),), meters=((0,4,4),)):
    return dict(notes=notes, ppq=120, chords=list(chords), keys=list(keys), meters=list(meters),
                markers=[], screen_line_ends=[], unknown_labels={})


class KaraokeStatisticsTests(unittest.TestCase):
    def test_rap_removal_does_not_bridge_intervals(self):
        notes=[(0,60,60)]+[(60+i*60,120+i*60,69) for i in range(8)]+[(540,600,72)]
        self.assertEqual(rap_mask(notes),set(range(1,9)))
        a=analyze(record(notes))
        self.assertEqual(a['metrics']['attacks'],2)
        self.assertEqual(a['melody'].get('interval',{}),{})
        self.assertEqual(a['melody']['raw_interval']['0'],7)

    def test_gap_and_overlap_break_patterns(self):
        notes=[(0,60,60),(180,300,62),(240,360,64),(360,480,65)]
        self.assertEqual([len(x) for x in split_runs(notes,set(),120)],[1,1,2])
        self.assertEqual(analyze(record(notes))['melody']['interval'],{'1':1})

    def test_retrigger_same_pitch_is_not_a_reliable_duration(self):
        self.assertTrue(ambiguous_vocal_overlap([(0,65,60),(60,120,60)]))
        self.assertFalse(ambiguous_vocal_overlap([(0,60,60),(60,120,60)]))
        with self.assertRaisesRegex(ValueError,'same-pitch'):
            analyze(record([(0,65,60),(60,120,60)]))

    def test_missing_meter_is_not_assumed(self):
        self.assertEqual(bar_grid([],960,120),[])
        self.assertEqual(bar_grid([(120,3,4),(840,4,4)],1320,120),
                         [(120,480,'3/4',0),(480,840,'3/4',0),(840,1320,'4/4',1)])

    def test_unknown_chord_breaks_alignment_and_progression(self):
        c=dict(root=0,bass=0,ivs=[0,4,7]); g=dict(root=7,bass=7,ivs=[0,4,7,10])
        notes=[(i*120,(i+1)*120,p) for i,p in enumerate([60,62,64,65,67,69,71,72])]
        a=analyze(record(notes,[(0,c),(240,None),(480,g)]))['harmony']
        self.assertEqual(a['melody_alignment']['unlabelled_attack'],2)
        self.assertEqual(a.get('degree_transition',{}),{})

    def test_long_notes_are_not_split_into_multiple_attacks(self):
        a=analyze(record([(0,240,60),(240,300,62),(300,360,64),(360,480,60)]))
        self.assertEqual(a['metrics']['attacks'],4)
        self.assertEqual(a['melody']['interval_pattern_4'],{'2,2,-4':1})
        self.assertEqual(a['melody']['duration_quarters']['2'],1)

    def test_chord_quality_and_no_guessed_key(self):
        c=dict(root=2,bass=2,ivs=[0,3,6,10])
        self.assertEqual(chord_quality(c),'half_dim7')
        self.assertEqual(degree(c,(0,0)),'major:2:half_dim7')
        self.assertIsNone(degree(c,None))

    def test_rhythm_and_pitch_repetition_are_separate(self):
        # Four bars: the second two-bar block is an exact transposition.
        notes=[(i*120,(i+1)*120,60+i%3) for i in range(8)]
        notes += [(a+960,b+960,p+2) for a,b,p in notes.copy()]
        a=analyze(record(notes))['melody']
        self.assertEqual(a['block_2_adjacent_relation']['transposed'],1)
        self.assertEqual(a['block_2_repetition']['joint_unique'],1)

    def test_file_duplicates_and_pattern_support_have_distinct_denominators(self):
        r=record([(i*120,(i+1)*120,60+i%3) for i in range(8)])
        r.update(id='a',melody_fingerprint='same',combined_fingerprint='same')
        analysis=analyze(r)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);db=connect(out/'statistics.sqlite3')
            for ident in ('a','b'):
                rr={**r,'id':ident}
                payload=zlib.compress(json.dumps({'record':rr,'analysis':analysis}).encode())
                db.execute('INSERT INTO files VALUES(?,?,?,?,?)',(ident,'ok',ident,payload,None))
            db.commit();result=aggregate(db,out)
            self.assertEqual(result['deduplication']['melody_unique_files'],1)
            self.assertEqual(result['deduplication']['melody_duplicates'],1)
            self.assertEqual(db.execute("SELECT occurrences,documents FROM patterns WHERE family='melody.interval_pattern_4' AND pattern='1,1,-2'").fetchone(),(2,1))
            db.close()


if __name__=='__main__':
    unittest.main()
