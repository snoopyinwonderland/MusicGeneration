import copy, json, tempfile, unittest
from pathlib import Path
from fractions import Fraction as F
from xml.etree import ElementTree as ET
import musigen
from musicomp.theory import Key
from musigen.design import validate, DesignError, seconds
from musigen.notation import parse, NotationError
from musigen.motif import apply
from musigen.piece import build, ScoreError
from musigen.piano_io import write_musicxml
from musigen.versions import bar_signature
from musigen.expression import playback
ROOT=Path(__file__).resolve().parents[1]
def work(name="after_rain"):
    p=ROOT/"examples/pieces"/name
    return [json.loads((p/n).read_text(encoding="utf-8")) for n in ("design.json","score.json")]
class ExpressionTest(unittest.TestCase):
    def test_legacy_bytes(self):
        d,s=work()
        with tempfile.TemporaryDirectory() as tmp:
            p=write_musicxml(build(d,s),Path(tmp)/"p.xml",subtitle="v001")
            self.assertEqual(p.read_bytes(),(ROOT/"tests/data/after_rain_v001.musicxml").read_bytes())
    def test_pickup(self):
        d,s=work("winter_morning"); p=build(d,s)
        self.assertEqual(p.bar_of(F(0)),0)
        self.assertEqual(p.bar_of(F(1,2)),1)
        self.assertIn("0",bar_signature(p)["rh"])
        self.assertAlmostEqual(seconds(d),72.5*60/66)
        with tempfile.TemporaryDirectory() as tmp:
            root=ET.parse(write_musicxml(p,Path(tmp)/"p.xml"))
            bars=root.findall(".//part/measure")
        self.assertEqual(bars[0].attrib.get("number"),"0")
        self.assertEqual(bars[0].attrib.get("implicit"),"yes")
        self.assertEqual(bars[-1].attrib.get("number"),"24")
    def test_pickup_rest_and_copy_rejection(self):
        d,s=work("winter_morning"); s["blocks"].pop(0)
        self.assertEqual(build(d,s).in_bars(0,0),[])
        s["blocks"][0]["copy"]="0"
        with self.assertRaises(ScoreError): build(d,s)
    def test_pickup_invalid(self):
        d,s=work()
        for x in (-1,3,"x","1/0"):
            d["basics"]["pickup"]=x
            with self.assertRaises(DesignError): validate(d)
    def test_articulation(self):
        self.assertEqual([e.art for e in parse("D5/q' F5/q> G5/q_")],["staccato","accent","tenuto"])
        for text in ("F5/h~>","C4/q'>","C4/q~ C4/q>","r/q'"):
            with self.assertRaises(NotationError): parse(text)
    def test_slur_validation(self):
        self.assertEqual([e.slur for e in parse("(C4/q D4/q E4/q)")],["start",None,"stop"])
        for t in ("(C4/q D4/q","C4/q)","(C4/q (D4/q))"):
            with self.assertRaises(NotationError): parse(t)
    def test_slur_transforms(self):
        ev=parse("(C4/q D4/q E4/q F4/q)")
        for op in ("retro","frag:1:3","frag:0:2","frag:2:"):
            out=apply(ev,op,Key(0,False))
            self.assertEqual((out[0].slur,out[-1].slur),("start","stop"))
        self.assertEqual(apply(ev,"frag:1:2",Key(0,False))[0].slur,"both")
    def test_tie_slur_merge(self):
        d,s=work(); s["blocks"][0]["rh"]="(D5/q~ D5/h)"
        n=build(d,s).notes[0]
        self.assertEqual((n.dur,n.slur),(3,"both"))
    def test_pedal_counts_and_hairpin(self):
        d,s=work(); s["expression"]=[{"bars":"1-2","pedal":"half"},{"bars":"1-8","hairpin":"cresc"}]
        p=build(d,s); self.assertEqual(p.expression[0]["changes"],[F(3)])
        with tempfile.TemporaryDirectory() as tmp:
            root=ET.parse(write_musicxml(p,Path(tmp)/"p.xml"))
        self.assertEqual([x.get("type") for x in root.findall(".//pedal")],["start","change","stop"])
        self.assertEqual([x.get("type") for x in root.findall(".//wedge")],["crescendo","stop"])
        s["expression"]=[{"bars":"1-24","hairpin":"cresc"}]
        self.assertEqual(build(d,s).expression[0]["end"],24) # mp at bar 9
    def test_expression_errors(self):
        d,s=work()
        for rows in ([{"bars":"25","pedal":"bar"}],
                     [{"bars":"1-2","pedal":"bar"},{"bars":"2","pedal":"held"}],
                     [{"bars":"1","hairpin":"bad"}]):
            s["expression"]=rows
            with self.assertRaises(ScoreError): build(d,s)
    def test_playback_quarters(self):
        d,s=work("winter_morning"); pf=playback(build(d,s))
        self.assertEqual(pf["bars"][1]["start"],.5)
        self.assertEqual(pf["articulations"][0]["art"],"tenuto")
        self.assertTrue(pf["expression"])
if __name__=="__main__": unittest.main()
