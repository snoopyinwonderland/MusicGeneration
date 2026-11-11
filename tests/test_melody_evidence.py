import gzip,json,tempfile,unittest
from pathlib import Path
from fractions import Fraction as F
from musigen.melody_evidence import xml_lines,kern_lines,line,fingerprint,features,selection


class MelodyEvidenceTest(unittest.TestCase):
    def test_relative_identity_keeps_time_and_rests(self):
        a=[(F(i),F(1,2),60+i%3) for i in range(9)]
        self.assertEqual(fingerprint(a),fingerprint([(t+4,d,p+5) for t,d,p in a]))
        b=a.copy();b[4]=(F(9,2),F(1,4),61)
        self.assertNotEqual(fingerprint(a),fingerprint(b))
        self.assertIsNone(line('x','unknown_voice','test',a+[(F(0),F(1,2),70)]))
        f=features(a);self.assertEqual(f['interval_pairs'],8);self.assertEqual(f['rest_gaps'],8)

    def test_xml_ties_and_role_are_not_top_voice_guess(self):
        notes=''.join(f'<note><pitch><step>C</step><octave>5</octave></pitch><duration>2</duration><voice>1</voice>{tie}</note>' for tie in ['<tie type="start"/>','<tie type="stop"/>']+['']*8)
        xml=f'<score-partwise><part-list><score-part id="P1"><part-name>Piano, S1</part-name></score-part></part-list><part id="P1"><measure number="1"><attributes><divisions>2</divisions></attributes>{notes}</measure></part></score-partwise>'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.xml';p.write_text(xml,encoding='utf-8');meta,lines=xml_lines(p,'kysing-xml')
            self.assertEqual(len(lines),1);self.assertEqual(lines[0]['role'],'documented_melody');self.assertEqual(lines[0]['features']['attacks'],9)
            self.assertEqual(lines[0]['features']['duration_counts']['2'],1)
            p.write_text(xml.replace('<duration>2</duration>','<duration>2</duration><chord/>',1),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'orphan chord'):xml_lines(p,'unknown')

    def test_kern_single_line_and_unsupported_spines(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.krn';p.write_text('**kern\n'+('\n'.join(['8c','8d','4e','4r','4g','8a','8g','4f','4e','4d']))+'\n*-\n',encoding='utf-8')
            _,lines=kern_lines(p,'essen');self.assertEqual(lines[0]['features']['attacks'],9)
            self.assertEqual(lines[0]['role'],'single_line_score')
            p.write_text('**kern\t**kern\n4c\t4e\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'multiple'):kern_lines(p,'unknown')

    def test_inventory_exclusions_have_reasons(self):
        for source,path in [('kysing-xml','x.xml'),('pdmx-search-xml','x.xml'),('aihub-gugak','x.mid')]:
            self.assertIsNotNone(selection({'source':source,'path':path}))
        self.assertIsNone(selection({'source':'kysing-midi','path':'x.mid'}))
        self.assertIsNotNone(selection({'source':'anything','path':'song.mp3'}))

    def test_explicit_inventory_extension_is_idempotent(self):
        from musigen.melody_inventory import extend
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'midi';source.mkdir();(source/'1.mid').write_bytes(b'MThd')
            (root/'inventory.json').write_text('{"sources":[]}',encoding='utf-8')
            self.assertEqual(extend(root,source),{'roots':1,'files':1})
            self.assertEqual(extend(root,source),{'roots':1,'files':1})
            with gzip.open(root/'files.jsonl.gz','rt',encoding='utf-8') as f:self.assertEqual(len(f.readlines()),1)

    def test_documented_role_wins_cross_database_duplicate(self):
        from musigen.melody_evidence import connect
        from musigen.melody_annotated import put
        from musigen.melody_profile import run
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);paths=[]
            events=[(F(i),F(1),60+i) for i in range(8)]
            for role in ['unknown_voice','documented_melody']:
                path=root/(role+'.db');paths.append(path);db=connect(path)
                put(db,'test',role,{},line('1',role,'test',events));db.commit();db.close()
            target=root/'report.json';run(paths,target);data=json.loads(target.read_text())
            self.assertEqual(data['unique_lines_across_databases'],1)
            self.assertEqual(list(data['groups']),['documented_melody / documented_melody'])

    def test_worker_skips_only_previously_read_identical_bytes(self):
        import musigen.melody_evidence as evidence
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'a.krn';path.write_text('**kern\n'+('4c\n4d\n'*4)+'*-\n')
            first=evidence.inspect_file((str(path),'test'))
            try:
                evidence.initialize_worker({first['sha256']})
                duplicate=evidence.inspect_file((str(path),'test'))
                self.assertEqual(duplicate['status'],'duplicate_bytes')
                self.assertEqual(duplicate['lines'],[])
                path.write_text('**kern\n'+('4c\n4e\n'*4)+'*-\n')
                changed=evidence.inspect_file((str(path),'test'))
                self.assertEqual(changed['status'],'read')
                self.assertNotEqual(first['sha256'],changed['sha256'])
            finally:evidence.KNOWN_HASHES=None
