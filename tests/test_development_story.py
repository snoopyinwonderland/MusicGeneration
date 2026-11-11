import copy
from dataclasses import replace
from fractions import Fraction as F
import unittest
from musigen.development_story import verify_uses
from musigen.piece import build
from test_corpus_accomp import work


class DevelopmentStoryTests(unittest.TestCase):
 def fixture(self):
  d,s=work();motif={'format':'musicanote-motif','version':1,'events':[{'duration':'1','pitches':['C5']},{'duration':'1','pitches':[]}]}
  s={'motifs':{'input':motif},'blocks':[{'bars':'1','rh':{'motif':'input','ops':['aug:2']}},
    {'bars':'2','rh':[{'motif':'input'},'r/h']},{'bars':'3-4','rh':'r/w r/w'}]}
  return build(d,s),motif
 def test_augmentation_and_original_include_rest_and_exact_spelling(self):
  p,m=self.fixture();uses=[{'id':'aug','bar':1,'kind':'transform','ops':['aug:2'],'label':'두 배 확대'}, {'id':'return','bar':2,'kind':'exact','label':'원형'}]
  saved=copy.deepcopy((p,m,uses));r=verify_uses(p,m,uses)
  self.assertEqual((p,m,uses),saved);self.assertEqual(r[0]['duration'],'4');self.assertEqual(r[1]['duration'],'2')
 def test_false_transformation_and_missing_rest_are_rejected(self):
  for change in ('pitch','duration','rest'):
   p,m=self.fixture();ns=list(p.notes)
   if change=='pitch':ns[0]=replace(ns[0],pitches=((74,2),))
   elif change=='duration':ns[0]=replace(ns[0],dur=F(3))
   else:ns.append(replace(ns[0],onset=F(3),dur=F(1)))
   p.notes=sorted(ns,key=lambda n:n.onset)
   with self.subTest(change=change),self.assertRaises(ValueError):verify_uses(p,m,[{'id':'aug','bar':1,'kind':'transform','ops':['aug:2'],'label':'확대'}])
 def test_rhythm_does_not_claim_same_pitch(self):
  p,m=self.fixture();p.notes[1]=replace(p.notes[1],pitches=((74,2),))
  self.assertEqual(verify_uses(p,m,[{'id':'rhythm','bar':2,'kind':'rhythm','label':'같은 리듬'}])[0]['status'],'verified_actual_notes')
 def test_invalid_and_out_of_bounds_claims_rejected(self):
  p,m=self.fixture()
  for u in [{'bar':5},{'kind':'unknown'},{'ops':['aug:2']},{'offset':True},{'bar':4,'kind':'transform','ops':['aug:4']}]:
   claim={'id':'bad','bar':2,'kind':'exact','label':'확인',**u}
   with self.subTest(u=u),self.assertRaises(ValueError):verify_uses(p,m,[claim])
 def test_fragment_sequence_checks_realized_diatonic_spelling(self):
  d,s=work();_,m=self.fixture()
  s={'motifs':{'input':m},'blocks':[{'bars':'1','rh':{'motif':'input','ops':['frag:0:1'],'seq':{'times':4,'step':1}}},{'bars':'2-4','rh':'r/w r/w r/w'}]}
  p=build(d,s);u={'id':'seq','bar':1,'kind':'transform','label':'조각 반복','ops':['frag:0:1'],'sequence':{'times':4,'step':1}}
  self.assertEqual(verify_uses(p,m,[u])[0]['attacks'],4)
