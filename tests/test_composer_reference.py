import copy
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from musigen.composer_reference import index_rows,build


def row(bar=0):
    return {'song':'mozart-a','bar':bar,'composer':'Mozart','corpus':'mozart-sonatas','work_group':'a','split':'train',
            'license':'CC-BY-NC-SA-4.0','meter':'4/4','bar_len':'4','key':'C','library_assessment':{'eligible':True},
            'melody':[{'on':'0','dur':'1','midi':60},{'on':'1','dur':'1','midi':62}],
            'phrase':{'id':'a','pos':bar,'len':4},'chords':[]}


class ComposerReferenceTest(unittest.TestCase):
    def test_composer_train_and_eligibility_are_hard_filters(self):
        good=row();evaluation={**row(1),'split':'evaluation'}
        other={**row(2),'composer':'Beethoven','corpus':'beethoven-sonatas'}
        excluded={**row(3),'library_assessment':{'eligible':False}}
        self.assertEqual([r['bar'] for r in index_rows([good,evaluation,other,excluded],'mozart')],[0])

    def test_neighbors_do_not_bridge_missing_bars(self):
        rows=index_rows([row(0),row(1),row(3)],'mozart')
        self.assertEqual(rows[0]['next'],rows[1]['id'])
        self.assertIsNone(rows[1]['next']);self.assertIsNone(rows[2]['previous'])

    def test_meter_mismatch_returns_empty_and_motif_not_changed(self):
        motif={'format':'musicanote-motif','version':1,'events':[{'duration':'1','pitches':['Eb4']}]}
        before=copy.deepcopy(motif)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bars.gz'
            with gzip.open(p,'wt',encoding='utf-8') as f:f.write(json.dumps(row())+'\n')
            _,report=build('mozart',motif,'3/4',p)
            self.assertEqual(report['references'],[])
            self.assertEqual(report['matching_meter_bars'],0)
        self.assertEqual(motif,before)
