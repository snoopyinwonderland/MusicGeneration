import copy
import unittest
from musigen.development_stats import aggregate

def sample(n=30,yes=21,scope='licensed'):
    return {'samples':[{'id':str(i),'genre':'pop','review':{'boundary_match':i<yes,'reason':'synthetic test evidence','type_match':True,'transformation_match':True},
       'use_scope':scope,'license_reference':'synthetic fixture','length_bars':4,'relations':[{'kind':'exact'}],'climax_position':.5} for i in range(n)]}

class AuditGateTest(unittest.TestCase):
    def test_below_threshold_stops_without_music_statistics(self):
        r=aggregate(sample(30,20))['genres']['pop']
        self.assertFalse(r['ranking_eligible']);self.assertNotIn('phrase_length_counts',r)
    def test_exact_threshold_with_complete_licensed_audit(self):
        r=aggregate(sample())['genres']['pop']
        self.assertTrue(r['ranking_eligible']);self.assertEqual(r['relation_denominator'],30)
    def test_incomplete_and_unreviewed_fail_closed(self):
        a=sample(29);self.assertFalse(aggregate(a)['genres']['pop']['ranking_eligible'])
        a=sample();a['samples'][0]['review']=None
        self.assertIsNone(aggregate(a)['genres']['pop']['boundary_rate'])
    def test_research_only_cannot_promote(self):
        self.assertFalse(aggregate(sample(scope='local_research_only'))['genres']['pop']['ranking_eligible'])
    def test_duplicate_or_unexplained_reviews_rejected(self):
        a=sample();a['samples'][1]['id']='0'
        with self.assertRaises(ValueError):aggregate(a)
        a=sample();a['samples'][0]['review']['reason']=''
        with self.assertRaises(ValueError):aggregate(a)
    def test_missing_classification_audit_cannot_promote(self):
        a=sample();a['samples'][0]['review']['type_match']=None
        self.assertFalse(aggregate(a)['genres']['pop']['ranking_eligible'])

if __name__=='__main__':unittest.main()
