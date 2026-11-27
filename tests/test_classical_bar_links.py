from unittest import TestCase
from scripts.classical_bar_links import comparisons, describe, features, validate_works


class BarLinksTest(TestCase):
    def test_missing_bar_does_not_create_false_pair(self):
        bars=[describe('4/4',[(0,60+i)],[(0,48)]) for i in range(12)]
        bars[5]=None
        pairs=list(comparisons(bars))
        self.assertEqual(len(pairs),9)
        for a,b,other in pairs:
            self.assertEqual(b[1][0]-a[1][0],1)
            self.assertGreater(abs(other[1][0]-a[1][0]),2)

    def test_joint_motion_uses_outer_attacks(self):
        a=describe('3/4',[(0,68),(2,70),(2,65)],[(0,55),(2,52)])
        b=describe('3/4',[(0,71),(1,73)],[(0,50),(0,55)])
        self.assertIn('hands:1,-2',features(a,b))
        self.assertIn('direction:2,1,2',features(a,b))
        self.assertEqual(validate_works({'only':[(a,b,b)]})['no_meter'],1)

