import copy, tempfile, unittest
from pathlib import Path
from fractions import Fraction as F
from test_notation_expression import work
from musicomp.theory import Key
from musigen.motif import apply
from musigen.notation import parse, length, NotationError
from musigen.piece import build, ScoreError
from musigen.versions import bar_signature
from musigen.checks import check
class ThemeTest(unittest.TestCase):
    def test_sequence_equals_expanded(self):
        d,s=work(); expanded=copy.deepcopy(s)
        i=next(i for i,b in enumerate(s["blocks"]) if b["bars"]=="9-11")
        expanded["blocks"][i:i+1]=[{"bars":str(b),"key":"F major","rh":{"motif":"a","ops":[f"at:{p}"]},
            "lh":{"pattern":"broken","chords":ch},**({"dyn":"mp"} if b==9 else {})}
            for b,p,ch in [(9,"C5","F"),(10,"D5","Gm7"),(11,"E5","C7")]]
        self.assertEqual(bar_signature(build(d,s)),bar_signature(build(d,expanded)))
    def test_seq_list_semitones_and_errors(self):
        d,s=work(); item=next(b for b in s["blocks"] if b["bars"]=="9-11")["rh"]
        item["seq"]={"times":3,"step":[0,1,3],"semi":True}
        p=build(d,s); starts=[p.in_bars(b,b,"rh")[0] for b in (9,10,11)]
        self.assertEqual([n.pitches[0][0] for n in starts],[72,73,75])
        self.assertIn("|seq:2",starts[-1].src)
        for seq in ({"times":0},{"times":3,"step":[0,1]},{"times":True},{"times":3,"semi":"yes"}):
            item["seq"]=seq
            with self.assertRaises(ScoreError): build(d,s)
    def test_delay_extend_tail(self):
        ev=parse("(C4/e D4/e E4/h)")
        delayed=apply(ev,"delay:e",Key(0,False))
        self.assertTrue(delayed[0].rest)
        self.assertEqual(length(delayed),3)
        self.assertEqual(length(apply(ev,"extend:q",Key(0,False))),4)
        tail=apply(ev,"tail:F4,G4",Key(0,False))
        self.assertEqual([e.pitches[0] for e in tail],[60,65,67])
        self.assertEqual([e.dur for e in ev],[e.dur for e in tail])
        with self.assertRaises(NotationError): apply(ev,"delay:h",Key(0,False))
    def test_extended_block_rejected(self):
        d,s=work(); s["blocks"][0]["rh"]["ops"]=["extend:q"]
        with self.assertRaises(ScoreError): build(d,s)
    def test_similarity_transposition_and_inversion(self):
        d,s=work(); p=build(d,s); r=check(p,d)["recognition"]
        one=next(x for x in r["occurrences"] if x["motif"]=="a" and x["bar"]==9)
        self.assertEqual(one["score"],1)
        inv=next(x for x in r["occurrences"] if "|invert" in x["how"])
        self.assertTrue(inv["inverted"]); self.assertEqual(inv["score"],1)
        self.assertTrue(all(sum(v["histogram"].values())==v["windows"] for v in r["distributions"].values()))
    def test_hidden_and_partial(self):
        d,s=work(); s["blocks"][0]["rh"]="A4/q D5/q. E5/e"
        r=check(build(d,s),d)["recognition"]
        self.assertTrue(any(x["bar"]==1 and x["motif"]=="a" for x in r["hidden"]))
    def test_winter_left_hand(self):
        d,s=work("winter_morning"); p=build(d,s)
        r=check(p,d)
        self.assertEqual(r["errors"],[])
        self.assertTrue(any(x["hand"]=="lh" and x["bar"]==9 for x in r["recognition"]["occurrences"]))
if __name__=="__main__": unittest.main()
