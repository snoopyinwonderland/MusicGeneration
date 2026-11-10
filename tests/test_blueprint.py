import copy
import json
import tempfile
import unittest
from pathlib import Path
from musigen.blueprint import prepare, run


def inputs():
    motif={'format':'musicanote-motif','version':1,'events':[
        {'duration':'1','pitches':[]},{'duration':'3','pitches':['E5']}]}
    plan={'format':'musicanote-development','version':1,
          'design':{'title':'교환 검증','basics':{'key':'C','mode':'major','meter':'4/4','tempo':90,'grade':6},
                    'form':[{'label':'A','bars':[1,2],'function':'statement'}]},
          'score':{'blocks':[{'bars':'1','rh':{'motif':'input'}},{'bars':'2','rh':'D5/h C5/h'}]},
          'harmony':[{'bar':1,'duration':'2','symbol':'C/E'},
                     {'bar':1,'offset':'2','duration':'2','symbol':'Am7'},
                     {'bar':2,'duration':'2','symbol':'G7/B'},
                     {'bar':2,'offset':'2','duration':'2','symbol':'C','cadence':'PAC'}]}
    return motif,plan


class BlueprintTest(unittest.TestCase):
    def test_exact_exchange_and_inversions(self):
        motif,plan=inputs()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'in';work.mkdir()
            for name,value in [('motif.json',motif),('development.json',plan)]:
                (work/name).write_text(json.dumps(value),encoding='utf-8')
            report=run(work,root/'out')
            self.assertTrue(report['roundtrip']['exact'])
            data=json.loads((root/'out/harmony.json').read_text(encoding='utf-8'))
            self.assertEqual(data['events'][0]['inversion'],1)
            self.assertEqual(data['events'][2]['bass'],'B')
            self.assertTrue(data['events'][1]['melody_relation'][0]['sustained_into_event'])
            self.assertEqual(data['events'][3]['cadence_status'],'composer_intent_not_verified')
            with self.assertRaisesRegex(ValueError,'덮어쓰지'):run(work,root/'out')

    def test_motif_cannot_silently_change(self):
        motif,plan=inputs();plan['score']['blocks'][0]['rh']='r/q F5/h.'
        with self.assertRaisesRegex(ValueError,'보존'):prepare(motif,plan)

    def test_gap_and_overlap(self):
        motif,plan=inputs()
        for offset in ('1','3'):
            p=copy.deepcopy(plan);p['harmony'][1]['offset']=offset
            with self.assertRaises(ValueError):prepare(motif,p)

    def test_voicing_cannot_omit_seventh_or_change_bass(self):
        motif,plan=inputs()
        for notes in (['G2','B2','D3'],['G2','B2','D3','F3']):
            p=copy.deepcopy(plan);p['harmony'][2]['voicing']=notes
            with self.assertRaisesRegex(ValueError,'전체 구성음'):prepare(motif,p)

    def test_extensions_survive_xml(self):
        from musigen.blueprint import write_xml,verify_roundtrip
        for symbol in ('Cadd9','Cmadd9','Cm6','C6','G7sus4'):
            motif,plan=inputs();plan['harmony'][0]['symbol']=symbol
            with self.subTest(symbol=symbol),tempfile.TemporaryDirectory() as tmp:
                piece,_,_=prepare(motif,plan)
                self.assertTrue(verify_roundtrip(piece,write_xml(piece,Path(tmp)/'x.musicxml'))['exact'])

    def test_added_tone_bass_is_not_classical_inversion(self):
        for symbol,wanted in [('Cadd9/E',1),('Cadd9/D',None),('C6/A',None),('Bdim7/Ab',3)]:
            motif,plan=inputs();plan['harmony'][0]['symbol']=symbol
            with self.subTest(symbol=symbol):
                _,_,details=prepare(motif,plan)
                self.assertEqual(details['events'][0]['inversion'],wanted)

    def test_repeated_harmony_events_survive_xml(self):
        motif,plan=inputs();plan['harmony']=[{'bar':i,'duration':'4','symbol':'C'} for i in (1,2)]
        from musigen.blueprint import write_xml,verify_roundtrip
        with tempfile.TemporaryDirectory() as tmp:
            piece,_,_=prepare(motif,plan)
            self.assertEqual(verify_roundtrip(piece,write_xml(piece,Path(tmp)/'x.musicxml'))['harmony_events'],2)
