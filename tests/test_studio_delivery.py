import copy
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from musigen.blueprint import dump,prepare,write_xml
from musigen.blueprint_solo import realize
from musigen.studio import save_request,write_studio
from musigen.studio_delivery import publish,catalog,verify_request,contained


def fixture(root,meter='4/4'):
    beats='4' if meter=='4/4' else '3'
    motif={'format':'musicanote-motif','version':1,'name':'시험용 선율','events':[
        {'duration':'1','pitches':['C5']},{'duration':'1','pitches':[]},
        {'duration':'1','pitches':['E5']}]+([{'duration':'1','pitches':[]}] if beats=='4' else [])}
    plan={'format':'musicanote-development','version':1,'design':{'title':'전달 시험',
        'basics':{'key':'C','mode':'major','meter':meter,'tempo':60 if meter=='6/8' else 90,'grade':6},
        'form':[{'label':'A','bars':[1,16],'function':'statement'}]},
        'score':{'blocks':[{'bars':str(i),'rh':{'motif':'input'}} for i in range(1,17)]},
        'harmony':[{'bar':i,'duration':beats,'symbol':'C'} for i in range(1,17)]}
    lead,score,details=prepare(motif,plan)
    for b in score['blocks']:b['lh']='[C3,G3,C4]/h '+('r/h' if beats=='4' else 'r/q')
    solo,frozen=realize(lead,plan,score)
    root.mkdir()
    for name,data in [('motif.json',motif),('development.json',plan),('solo_score.json',frozen)]:dump(root/name,data)
    for kind,piece in [('melody_harmony',lead),('piano_solo',solo)]:
        write_xml(piece,root/(kind+'.musicxml'))
        # Unit-test stand-in: publishing checks presence/header and hashes, not PDF musical content.
        (root/(kind+'.pdf')).write_bytes(b'%PDF-1.4\n%%EOF\n')
    request={'format':'musicanote-composition-request','version':1,'motif':motif,'preferences':{
        'prompt':'검수 시험 데이터 · 사용자 선택 아님','key':'C major','meter':meter,'tempo':90,'bars':16,
        'secondary':False,'augmented_sixth':False,'modulation':False,'outputs':['melody_harmony','piano_solo']}}
    return request,plan,lead,details


class StudioDeliveryTest(unittest.TestCase):
    def test_authored_playback_balance_survives_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data,_,_,_=fixture(root/'piece');req=save_request(root,data,origin='author_demo')
            path=root/'piece/solo_score.json';score=json.loads(path.read_text(encoding='utf-8'))
            score['playback_balance']=[{'bars':'1-4','rh':1,'lh':.8,'reduce_lh_chords':True}]
            dump(path,score)
            manifest=publish(root,req['id'],root/'piece')
            target=root/'requests'/req['id']/'results'/manifest['revision']
            html=(target/'piano_solo.html').read_text(encoding='utf-8')
            self.assertIn('"balance": [{"start": 0.0, "end": 16.0, "rh": 1, "lh": 0.8, "reduce_lh_chords": true}]',html)
            self.assertEqual((target/'piano_solo.musicxml').read_bytes(),(root/'piece/piano_solo.musicxml').read_bytes())

    def test_two_scores_roundtrip_immutable_revision_and_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data,_,_,_=fixture(root/'piece');req=save_request(root,data,origin='author_demo')
            first=publish(root,req['id'],root/'piece');row=catalog(root)[0]
            self.assertEqual(row['origin'],'author_demo');self.assertEqual(row['status'],'draft_ready')
            self.assertIsNone(first['listener_approval']);self.assertEqual(set(row['result']['outputs']),{'melody_harmony','piano_solo'})
            folder=root/'requests'/req['id'];before=(folder/'results/v001/delivery.json').read_bytes()
            self.assertEqual(publish(root,req['id'],root/'piece')['revision'],'v002')
            self.assertEqual(before,(folder/'results/v001/delivery.json').read_bytes())
            page=(folder/'results/v002/melody_harmony.html').read_text(encoding='utf-8')
            self.assertIn('"label": "멜로디 + 상세 왼손 화성"',page)
            self.assertIn('"version": "v002"',page)
            self.assertIn(data['preferences']['prompt'],page)
            write_studio(root);self.assertEqual(catalog(root)[0]['status'],'draft_ready')
            (folder/'results/v002/piano_solo.musicxml').write_text('changed',encoding='utf-8')
            row=catalog(root)[0];self.assertEqual(row['status'],'unavailable');self.assertNotIn('result',row)

    def test_request_mismatches_do_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data,_,_,_=fixture(root/'piece')
            changes=[lambda d:d['motif']['events'][0].update(pitches=['D5']),
                lambda d:d['preferences'].update(key='G major'),lambda d:d['preferences'].update(meter='3/4'),
                lambda d:d['preferences'].update(tempo=100),lambda d:d['preferences'].update(bars=24)]
            for change in changes:
                d=copy.deepcopy(data);change(d);req=save_request(root,d)
                with self.assertRaises(ValueError):publish(root,req['id'],root/'piece')
                self.assertFalse(list((root/'requests'/req['id']/'results').iterdir()))

    def test_missing_pdf_and_changed_actual_xml_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data,_,_,_=fixture(root/'piece');req=save_request(root,data)
            pdf=root/'piece/piano_solo.pdf';payload=pdf.read_bytes();pdf.unlink()
            with self.assertRaises(FileNotFoundError):publish(root,req['id'],root/'piece')
            pdf.write_bytes(payload);xml=root/'piece/piano_solo.musicxml';original=xml.read_bytes()
            for field in ('tempo','meter','note'):
                tree=ET.ElementTree(ET.fromstring(original))
                if field=='tempo':tree.find('.//sound[@tempo]').set('tempo','100')
                if field=='meter':tree.find('.//time/beats').text='3'
                if field=='note':tree.find('.//note/pitch/step').text='D'
                tree.write(xml,encoding='utf-8')
                with self.subTest(field=field),self.assertRaises(ValueError):publish(root,req['id'],root/'piece')

    def test_six_eight_uses_quarter_bpm_and_lead_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data,plan,lead,details=fixture(root/'piece','6/8')
            self.assertEqual(verify_request(data,data['motif'],plan,lead,details)['tempo'],90)
            data['preferences']['outputs']=['melody_harmony'];req=save_request(root,data)
            result=publish(root,req['id'],root/'piece');self.assertEqual(set(result['outputs']),{'melody_harmony'})
            self.assertNotIn('piano_solo.musicxml',result['files'])

    def test_forbidden_secondary_plain_or_explicit_and_modulation(self):
        with tempfile.TemporaryDirectory() as tmp:
            data,plan,lead,details=fixture(Path(tmp)/'piece')
            for chord in ({'symbol':'D7'},{'figure':'V7/V'}):
                p=copy.deepcopy(plan);p['harmony'][0].pop('symbol');p['harmony'][0].update(chord)
                l,_,d=prepare(data['motif'],p)
                with self.assertRaisesRegex(ValueError,'세컨더리'):verify_request(data,data['motif'],p,l,d)
            p=copy.deepcopy(plan);p['harmony'][0].pop('symbol');p['harmony'][0]['figure']='Ger65'
            l,_,d=prepare(data['motif'],p)
            with self.assertRaisesRegex(ValueError,'증6화음'):verify_request(data,data['motif'],p,l,d)
            details['key_plan'].append({'bar':9,'tonic':'G','mode':'major'})
            with self.assertRaisesRegex(ValueError,'전조'):verify_request(data,data['motif'],plan,lead,details)

    def test_unsafe_paths_lock_and_stale_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data,_,_,_=fixture(root/'piece');req=save_request(root,data);folder=root/'requests'/req['id']
            for value in ('../outside','request-x','request-'+('a'*32)+'/..'):
                with self.assertRaises(ValueError):publish(root,value,root/'piece')
            with self.assertRaises(ValueError):contained(root,'../outside')
            (folder/'.delivery.lock').touch()
            with self.assertRaisesRegex(ValueError,'진행 중'):publish(root,req['id'],root/'piece')
            (folder/'.delivery.lock').unlink();publish(root,req['id'],root/'piece')
            data['preferences']['prompt']='바뀐 요청';dump(folder/'request.json',data)
            self.assertEqual(catalog(root)[0]['status'],'unavailable')

    def test_failed_republication_keeps_previous_ready_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data,_,_,_=fixture(root/'piece');req=save_request(root,data);publish(root,req['id'],root/'piece')
            (root/'piece/motif.json').write_text('{}',encoding='utf-8')
            with self.assertRaises(ValueError):publish(root,req['id'],root/'piece')
            row=catalog(root)[0];self.assertEqual(row['status'],'draft_ready');self.assertEqual(row['result']['revision'],'v001')
