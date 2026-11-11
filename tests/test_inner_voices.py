import copy
import unittest
from dataclasses import replace
from fractions import Fraction as F
from musigen.inner_voices import audit,fingerprint,pitch_name
from musigen.piece import build,Note
from test_corpus_accomp import work


def fixture():
 d,s=work();p=build(d,s)
 p.notes=[n for n in p.notes if n.hand=='rh']+[
  Note(F(0),F(4),((43,1),(59,5),(65,-1)),'lh',1,'written'),
  Note(F(4),F(3),((48,0),(60,0),(64,4)),'lh',1,'written')]
 from musigen.accomp import parse_chord
 p.analysis_chords=[(F(0),parse_chord('G7')),(F(4),parse_chord('C'))]
 event=lambda bar,pitch:dict(bar=bar,offset='0',hand='lh',voice=1,pitch=pitch)
 a=event(1,'F4');a['next']={'kind':'step_down','source_degree':7,'reason':'작성한 종지에서 7음을 아래로 연결'}
 b=event(2,'E4')
 plan={'format':'musicanote-inner-voices','version':1,'score_sha256':fingerprint(p),
  'voices':[{'id':'seventh','label':'위 내성','events':[a,b]}]}
 return p,plan


class InnerVoiceTests(unittest.TestCase):
 def test_explicit_seventh_resolution_matches_actual_notes_without_mutation(self):
  p,plan=fixture();saved=copy.deepcopy((p,plan));r=audit(p,plan)
  self.assertEqual((p,plan),saved);self.assertEqual(r['summary']['met'],1)
  self.assertEqual(r['summary']['assigned_pitch_events'],2);self.assertEqual(r['summary']['total_lh_pitch_events'],6)

 def test_octave_displacement_is_not_stepwise_resolution(self):
  p,plan=fixture();p.notes[-1]=replace(p.notes[-1],pitches=((48,0),(52,4),(60,0)))
  plan['score_sha256']=fingerprint(p);plan['voices'][0]['events'][1]['pitch']='E3'
  self.assertEqual(audit(p,plan)['summary']['outside_plan'],1)

 def test_rest_is_explicit_not_silently_joined(self):
  p,plan=fixture();p.notes[-1]=replace(p.notes[-1],onset=F(5),dur=F(2))
  plan['score_sha256']=fingerprint(p);plan['voices'][0]['events'][1]['offset']='1'
  self.assertEqual(audit(p,plan)['summary']['gaps'],1)
  plan['voices'][0]['events'][0]['next']['max_gap']='1'
  r=audit(p,plan);self.assertEqual(r['summary']['met'],1);self.assertEqual(r['summary']['interrupted_links'],1)

 def test_stale_score_wrong_pitch_role_and_ambiguous_anchor_are_rejected(self):
  for kind in ('stale','spelling','role','missing','ambiguous'):
   p,plan=fixture()
   if kind=='stale':plan['score_sha256']='old'
   elif kind=='spelling':plan['voices'][0]['events'][0]['pitch']='E#4'
   elif kind=='role':plan['voices'][0]['events'][0]['next']['source_degree']=3
   elif kind=='missing':plan['voices'][0]['events'][1]['offset']='1'
   else:p.notes.append(copy.deepcopy(p.notes[-1]));plan['score_sha256']=fingerprint(p)
   with self.subTest(kind=kind),self.assertRaises(ValueError):audit(p,plan)

 def test_pitch_order_does_not_infer_voices_or_allow_duplicate_assignment(self):
  p,plan=fixture();plan['voices'].append(copy.deepcopy(plan['voices'][0]));plan['voices'][1]['id']='other'
  with self.assertRaisesRegex(ValueError,'중복'):audit(p,plan)

 def test_hold_requires_same_spelling_and_octave(self):
  p,plan=fixture();plan['voices'][0]['events'][0]['next']={'kind':'hold','reason':'공통음 유지'}
  plan['voices'][0]['events'][0]['pitch']='G2';plan['voices'][0]['events'][1]['pitch']='C3'
  self.assertEqual(audit(p,plan)['summary']['outside_plan'],1)
  self.assertEqual(pitch_name(60,12),'B#3');self.assertEqual(pitch_name(59,-7),'Cb4')

 def test_negative_gaps_bad_limits_and_unknown_fields_rejected(self):
  for extra in ({'max_gap':'-1'},{'max_gap':True},{'kind':'within','max_semitones':True},{'unexpected':1}):
   p,plan=fixture();plan['voices'][0]['events'][0]['next'].update(extra)
   with self.assertRaises(ValueError):audit(p,plan)
