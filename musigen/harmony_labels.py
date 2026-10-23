"""Classical labels from the authored chords, local key and sounding bass at each chord onset.

This is a display analysis, not a new chord-recognition engine. Added tones and
suspensions stay explicit; they must not be mistaken for figured-bass inversions.
"""
import re
from music21 import chord as m21chord, key as m21key, pitch, roman
from musicomp.theory import tpc_name
from musigen.piano_io import piano_part

SUP=str.maketrans('0123456789','⁰¹²³⁴⁵⁶⁷⁸⁹')
STACK={'64':'⁶₄','65':'⁶₅','43':'⁴₃','42':'⁴₂'}


def display(figure):
    parts=figure.split('/')
    def one(text):
        text=text.replace('o','°').replace('#','♯').replace('b','♭')
        return re.sub(r'\d+',lambda m:STACK.get(m[0],m[0].translate(SUP)),text)
    return '/'.join(map(one,parts))


def label(ch, key, bass_tpc=None, secondary=False):
    key_obj=m21key.Key(tpc_name(key.tonic_tpc).replace('b','-'),'minor' if key.minor else 'major')
    bass_tpc=ch.bass_tpc if bass_tpc is None else bass_tpc
    # These are chord extensions/suspensions, not the classical first inversion '6'.
    extra={'6':'add6','m6':'add6','add9':'add9','madd9':'add9',
           'sus2':'sus2','sus4':'sus4','7sus4':'7sus4'}.get(ch.quality)
    tones=list(ch.tones)
    if extra:
        offsets=[0, -3 if ch.quality.startswith('m') else 4, 1]
        tones=[(((ch.root_tpc+x)*7)%12,ch.root_tpc+x) for x in offsets]
    names=[tpc_name(tpc).replace('b','-')+'4' for _,tpc in tones]
    bass_name=tpc_name(bass_tpc).replace('b','-')
    if bass_tpc in [t for _,t in tones]:
        names.append(bass_name+'3')
        bass_note=None
    else:
        # A pedal/non-chord bass is not silently converted to an inversion.
        names.append(tpc_name(ch.root_tpc).replace('b','-')+'3')
        bass_note=f'저음 {tpc_name(bass_tpc)}: 화음 밖 음 또는 첨가음'
    obj=m21chord.Chord(names)
    obj.root(pitch.Pitch(tpc_name(ch.root_tpc).replace('b','-')+'4'))
    scale_pcs={p.pitchClass for p in key_obj.pitches}
    chromatic=any(pc not in scale_pcs for pc,_ in ch.tones)
    # A diatonic I->IV is not automatically V/IV; require chromatic evidence.
    result=roman.romanNumeralFromChord(obj,key_obj,preferSecondaryDominants=secondary and chromatic)
    # music21 can spell a minor-key dominant as V75#3. Since chord quality
    # is supplied, use conventional case + quality + inversion figures instead.
    root_pitch=pitch.Pitch(tpc_name(ch.root_tpc).replace('b','-')+'4')
    degree,accidental=key_obj.getScaleDegreeAndAccidentalFromPitch(root_pitch)
    accidental_text='' if accidental is None else accidental.modifier.replace('-', 'b')
    quality=ch.quality
    if key.minor and degree==7 and accidental_text=='#' and quality in ('dim','dim7','m7b5'):
        accidental_text=''  # Conventional minor-key leading-tone diminished chord.
    numeral=['I','II','III','IV','V','VI','VII'][degree-1]
    if quality in ('m','m7','m6','madd9','dim','dim7','m7b5'):
        numeral=numeral.lower()
    quality_sign='o' if quality in ('dim','dim7') else 'ø' if quality=='m7b5' else '+' if quality=='aug' else ''
    inversion=obj.inversion()
    seventh=quality in ('7','maj7','m7','m7b5','dim7')
    figures={0:'7',1:'65',2:'43',3:'42'} if seventh else {0:'',1:'6',2:'64'}
    figure=accidental_text+numeral+quality_sign+figures[inversion]
    if result.secondaryRomanNumeral is not None:
        primary=result.romanNumeral
        figure=primary+quality_sign+figures[inversion]+'/'+result.secondaryRomanNumeral.figure
    shown=display(figure)+(f'({extra})' if extra else '')
    if bass_note:shown+=f' / {tpc_name(bass_tpc)}'
    return {'figure':figure,'engine_figure':result.figure,'display':shown,'key':f'{tpc_name(key.tonic_tpc)} '+('단조' if key.minor else '장조'),
            'bass':tpc_name(bass_tpc),'note':bass_note,'extension':extra}


def analyze(piece):
    symbols=piece.analysis_chords or piece.chords
    rows=[]
    for harmony in piano_part(piece).harmonies:
        on=harmony.onset
        index=next(i for i,(t,_) in enumerate(symbols) if t==on)
        ch=symbols[index][1]
        key=piece.bar_keys.get(piece.bar_of(on),piece.key)
        next_ch=symbols[index+1][1] if index+1<len(symbols) else None
        resolves=bool(next_ch and (next_ch.tones[0][0]-ch.tones[0][0])%12==5)
        sounding=[pair for n in piece.notes if n.onset<=on<n.onset+n.dur for pair in n.pitches]
        bass_tpc=min(sounding)[1] if sounding else ch.bass_tpc
        result=label(ch,key,bass_tpc,secondary=resolves)
        result.update(q=float(on),bar=piece.bar_of(on),symbol=ch.symbol,
                      basis='기보 화음·국소 조성·화음 시작 시 실제 최저음')
        rows.append(result)
    return rows
