import copy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from musigen.accompaniment_review import compare
from musigen.accompaniment_context import observe
from musigen.piece import build
from test_corpus_accomp import work


class AccompanimentReviewTests(unittest.TestCase):
    def test_rh_changes_cannot_be_published_as_accompaniment_only(self):
        d,s=work();a=build(d,s);b=copy.deepcopy(a)
        n=next(n for n in b.notes if n.hand=='rh');b.notes.remove(n);b.notes.append(replace(n,dur=n.dur/2))
        with patch('musigen.accompaniment_review.load',side_effect=[(a,{},observe(a,d)),(b,{},observe(b,d))]),self.assertRaisesRegex(ValueError,'주선율'):
            compare('before','after')

    def test_changed_lh_bars_and_exact_controls_are_preserved(self):
        d,s=work();a=build(d,s);b=copy.deepcopy(a)
        n=next(n for n in b.notes if n.hand=='lh');b.notes.remove(n);b.notes.append(replace(n,pitches=tuple((m+12,t) for m,t in n.pitches)))
        with tempfile.TemporaryDirectory() as tmp:
            dirs=[Path(tmp)/name for name in ('before','after')]
            for folder in dirs:folder.mkdir();(folder/'piano_solo.musicxml').write_text('synthetic test fixture')
            with patch('musigen.accompaniment_review.load',side_effect=[(a,{},observe(a,d)),(b,{},observe(b,d))]):r=compare(*dirs)
            self.assertEqual(r['changed_lh_bars'],[1]);self.assertEqual(r['status'],'awaiting_listener_feedback')
