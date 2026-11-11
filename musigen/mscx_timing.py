"""Independent, bounded MuseScore 3 written-time reader (no ms3 dependency).

Not a performance reader: repeats are not unfolded and grace notes take no time.
Unknown time-bearing structures fail closed. Ties remain individual written notes.
"""
from collections import Counter
from fractions import Fraction as F
from xml.etree import ElementTree as ET

DURATIONS={name:F(4,den) for name,den in [('whole',1),('half',2),('quarter',4),('eighth',8),('16th',16),('32nd',32),('64th',64),('128th',128)]}
DURATIONS.update(breve=F(8),long=F(16))
GRACES={'acciaccatura','appoggiatura','grace4','grace16','grace32','grace8after','grace16after','grace32after'}
DECORATIONS={'KeySig','Dynamic','Tempo','StaffText','SystemText','Beam','Fermata','Spanner','Clef','BarLine'}
CHORD_DECORATIONS={'Lyrics','Articulation','StemDirection','Spanner','BeamMode','Arpeggio','offset','Stem','Hook'}


def raw_label(row):
    """ms3's separate alternative column reconstructs the complete source label."""
    return row['label']+('-'+row['alt_label'] if row.get('alt_label') else '')


def parse(xml):
    root=ET.fromstring(xml)
    if root.tag!='museScore' or not root.get('version','').startswith('3.'):
        raise ValueError('unsupported_musescore_version')
    score=root.find('Score')
    if score is None:raise ValueError('missing_score')
    if any(int(e.text or 0) for tag in ('transposeChromatic','transposeDiatonic') for e in score.findall('.//'+tag)):
        raise ValueError('transposing_instrument_not_supported')
    notes=[];harmonies=[];bars=[];staff_ids=set()
    for staff in score.findall('Staff'):
        sid=int(staff.get('id'));meter=None;start=F(0)
        if sid in staff_ids:raise ValueError('duplicate_staff')
        staff_ids.add(sid)
        for mc,measure in enumerate(staff.findall('Measure'),1):
            sigs={(int(t.findtext('sigN')),int(t.findtext('sigD'))) for t in measure.findall('./voice/TimeSig')}
            if len(sigs)>1:raise ValueError('conflicting_meter')
            if sigs:meter=next(iter(sigs))
            if meter is None or min(meter)<=0:raise ValueError('missing_or_invalid_meter')
            length=4*F(measure.get('len')) if measure.get('len') else 4*F(*meter)
            if length<=0:raise ValueError('invalid_measure_length')
            bars.append((mc,sid,start,length,f'{meter[0]}/{meter[1]}'))
            for voice_id,voice in enumerate(measure.findall('voice'),1):
                cursor=F(0);tuplets=[]
                for e in voice:
                    if e.tag=='TimeSig':
                        if cursor:raise ValueError('mid_measure_meter_not_supported')
                    elif e.tag in DECORATIONS:pass
                    elif e.tag=='Tuplet':
                        normal=int(e.findtext('normalNotes'));actual=int(e.findtext('actualNotes'))
                        if min(normal,actual)<=0:raise ValueError('invalid_tuplet')
                        tuplets.append(F(normal,actual))
                    elif e.tag=='endTuplet':
                        if not tuplets:raise ValueError('unmatched_tuplet_end')
                        tuplets.pop()
                    elif e.tag=='location':
                        if set(c.tag for c in e)!={'fractions'}:raise ValueError('unsupported_location')
                        cursor+=4*F(e.findtext('fractions'))
                    elif e.tag=='Harmony':
                        if e.findtext('harmonyType')=='1':harmonies.append((mc,sid,voice_id,cursor,e.findtext('name')))
                    elif e.tag in ('Chord','Rest'):
                        typ=e.findtext('durationType');dots=int(e.findtext('dots','0'))
                        if not 0<=dots<=3:raise ValueError('unsupported_dots')
                        grace=[c.tag for c in e if c.tag in GRACES]
                        if len(grace)>1:raise ValueError('multiple_grace_types')
                        if e.tag=='Chord':
                            unknown={c.tag for c in e}-CHORD_DECORATIONS-GRACES-{'durationType','dots','Note'}
                            if unknown:raise ValueError('unsupported_chord_fields:'+','.join(sorted(unknown)))
                        if typ=='measure':
                            if e.tag!='Rest' or tuplets or dots:raise ValueError('unsupported_measure_rest')
                            duration=4*F(e.findtext('duration'))
                            if duration!=length:raise ValueError('measure_rest_length_mismatch')
                        elif typ in DURATIONS:
                            duration=DURATIONS[typ]*sum((F(1,2**i) for i in range(dots+1)),F(0))
                            for factor in tuplets:duration*=factor
                        else:raise ValueError('unsupported_duration_type:'+str(typ))
                        if grace:duration=F(0)
                        if cursor<0 or cursor+duration>length:raise ValueError('note_or_rest_outside_measure')
                        if e.tag=='Chord':
                            if not e.findall('Note'):raise ValueError('empty_chord')
                            for n in e.findall('Note'):
                                midi=int(n.findtext('pitch'));tpc=int(n.findtext('tpc'))-14
                                if not 0<=midi<=127 or (7*tpc-midi)%12:raise ValueError('pitch_spelling_mismatch')
                                notes.append((mc,sid,voice_id,cursor,duration,midi,tpc,grace[0] if grace else ''))
                        cursor+=duration
                    else:raise ValueError('unsupported_voice_element:'+e.tag)
                    if not 0<=cursor<=length:raise ValueError('cursor_outside_measure')
                if tuplets:raise ValueError('unclosed_tuplet')
            start+=length
    if not bars or not notes:raise ValueError('empty_score')
    return {'bars':bars,'notes':notes,'harmonies':harmonies}


def differences(actual,expected):
    a,b=Counter(actual),Counter(expected)
    return {'xml_only':[list(map(str,x)) for x in (a-b).elements()],
            'table_only':[list(map(str,x)) for x in (b-a).elements()]}


def audit(xml,measures,notes,harmonies):
    parsed=parse(xml)
    staff_ids=sorted({b[1] for b in parsed['bars']})
    expected_bars=[(int(r['mc']),sid,F(r['quarterbeats']),4*F(r['act_dur']),r['timesig']) for sid in staff_ids for r in measures]
    expected_notes=[(int(r['mc']),int(r['staff']),int(r['voice']),4*F(r['mc_onset']),4*F(r['duration']),int(r['midi']),int(r['tpc']),r['gracenote']) for r in notes]
    expected_harmonies=[(int(r['mc']),int(r['staff']),int(r['voice']),4*F(r['mc_onset']),raw_label(r)) for r in harmonies]
    diffs={kind:differences(parsed[kind],expected) for kind,expected in [('bars',expected_bars),('notes',expected_notes),('harmonies',expected_harmonies)]}
    passed=not any(v for d in diffs.values() for v in d.values())
    return {'status':'validated' if passed else 'mismatch','counts':{k:len(v) for k,v in parsed.items()},
            'differences':diffs,'alternatives_preserved':sum(bool(r.get('alt_label')) for r in harmonies),
            'scope':'independent XML written note segments incl grace, pitch spelling, measure clock, full label onsets; no unfolding/tie merging/performance interpretation'}
