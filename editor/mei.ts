import { ticks, type QueryEvent } from './model.ts';
const signatures: Record<string, number> = {
  'C major': 0,
  'G major': 1,
  'D major': 2,
  'F major': -1,
  'Bb major': -2,
  'Eb major': -3,
  'A minor': 0,
  'E minor': 1,
  'D minor': -1,
  'G minor': -2,
  'C minor': -3,
};
// MusicSearch's MEI writer uses written durations. Split imported rational values exactly
// at barlines and into engravable binary/dotted/3:2 values while retaining the parent ID.
const values = [1, 2, 4, 8, 16, 32, 64]
  .flatMap((dur) =>
    [0, 1].flatMap((dots) =>
      [false, true].map((triplet) => ({
        dur,
        dots,
        triplet,
        size: (96 / dur) * (dots ? 1.5 : 1) * (triplet ? 2 / 3 : 1),
      })),
    ),
  )
  .filter((v) => Number.isInteger(v.size))
  .sort((a, b) => b.size - a.size || Number(a.triplet) - Number(b.triplet));
export function toMEI(events: QueryEvent[], meter: string, key: string, clef: string) {
  const [count, unit] = meter.split('/').map(Number),
    bar = (96 * count) / unit,
    fifths = signatures[key] ?? 0;
  const pitches = events.flatMap((e) => (e.pitchMidi === null ? [] : [e.pitchMidi])).sort((a, b) => a - b);
  const shape = clef === 'auto' ? ((pitches[Math.floor(pitches.length / 2)] ?? 60) < 60 ? 'F' : 'G') : clef;
  let used = 0,
    measure = 1,
    body = '',
    layer = '',
    ties = '',
    group = '',
    previous = '',
    previousTie: string | undefined;
  const state = new Map<string, string>();
  function closeTuplet() {
    if (group) layer += '</tuplet>';
    group = '';
  }
  function closeBar() {
    closeTuplet();
    body +=
      '<measure n="' +
      measure +
      '"><staff n="1"><layer n="1">' +
      layer +
      '</layer></staff>' +
      ties +
      '</measure>';
    used = 0;
    measure++;
    layer = '';
    ties = '';
    state.clear();
  }
  let autoTripletEnd = -1,
    autoTriplet = '';
  for (const [index, e] of events.entries()) {
    // Portable clips store sounding lengths, so three equal triplet eighths
    // can arrive without a written tuplet group.
    if (
      index > autoTripletEnd &&
      !e.tupletGroup &&
      ticks(e.durationRatio) === 8 &&
      bar - used >= 24 &&
      [events[index + 1], events[index + 2]].every((n) => n && !n.tupletGroup && ticks(n.durationRatio) === 8)
    ) {
      autoTripletEnd = index + 2;
      autoTriplet = e.id;
    }
    let left = ticks(e.durationRatio),
      part = 0;
    while (left) {
      const budget = Math.min(left, bar - used);
      const v = values.find((value) => {
        if (value.size > budget) return false;
        if (e.tupletGroup) return value.triplet;
        // Even a plain dotted rhythm could otherwise be split into two
        // unusual tuplets by a longest-duration-first search.
        return budget % 3 !== 0 || !value.triplet;
      })!;
      const id = e.id + '-p' + part,
        nextGroup = v.triplet ? e.tupletGroup || (index <= autoTripletEnd ? autoTriplet : e.id) : '';
      if (nextGroup !== group) {
        closeTuplet();
        if (nextGroup) {
          layer += '<tuplet num="3" numbase="2">';
          group = nextGroup;
        }
      }
      const rhythm = ' xml:id="' + id + '" dur="' + v.dur + '"' + (v.dots ? ' dots="1"' : '');
      if (e.kind === 'rest') layer += '<rest' + rhythm + '/>';
      else {
        const [, letter, alter, oct] = e
          .spelling!.replaceAll('♯', '#')
          .replaceAll('♭', 'b')
          .match(/^([A-G])([#b]{0,2})(-?\d+)$/)!;
        const accidental = { '': 'n', '#': 's', '##': 'ss', b: 'f', bb: 'ff' }[alter]!;
        const signed = (fifths < 0 ? 'BEADGCF' : 'FCGDAEB').slice(0, Math.abs(fifths)).includes(letter);
        const prior = state.get(letter + oct) ?? (signed ? (fifths < 0 ? 'f' : 's') : 'n');
        layer +=
          '<note' +
          rhythm +
          ' pname="' +
          letter.toLowerCase() +
          '" oct="' +
          oct +
          '" accid.ges="' +
          accidental +
          '"' +
          (prior !== accidental ? ' accid="' + accidental + '"' : '') +
          '/>';
        state.set(letter + oct, accidental);
        if (part || (e.tieGroup && previousTie === e.tieGroup))
          ties += '<tie startid="#' + previous + '" endid="#' + id + '"/>';
      }
      previous = id;
      previousTie = e.tieGroup;
      part++;
      used += v.size;
      left -= v.size;
      if (used === bar) closeBar();
    }
  }
  if (used) closeBar();
  return (
    '<mei xmlns="http://www.music-encoding.org/ns/mei" meiversion="5.0"><meiHead><fileDesc><titleStmt><title/></titleStmt><pubStmt/></fileDesc></meiHead><music><body><mdiv><score><scoreDef meter.count="' +
    count +
    '" meter.unit="' +
    unit +
    '"><staffGrp><staffDef n="1" lines="5" clef.shape="' +
    shape +
    '" clef.line="' +
    (shape === 'F' ? 4 : 2) +
    '"><keySig sig="' +
    Math.abs(fifths) +
    (fifths < 0 ? 'f' : fifths > 0 ? 's' : '') +
    '"/></staffDef></staffGrp></scoreDef><section>' +
    body +
    '</section></score></mdiv></body></music></mei>'
  );
}
