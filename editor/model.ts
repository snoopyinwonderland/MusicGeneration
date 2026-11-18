export type QueryEvent = {
  id: string;
  kind: 'note' | 'rest';
  pitchMidi: number | null;
  spelling?: string;
  durationRatio: number;
  writtenDuration?: number;
  tieGroup?: string;
  tupletGroup?: string;
  actualNotes?: number;
  normalNotes?: number;
};

export type Row = { duration: string; pitches: string[] };
export type Clip = { format: string; version: number; events: Row[]; [field: string]: unknown };

export const ticks = (quarters: number) => Math.round(quarters * 24);

export function fraction(length: number) {
  const gcd = (a: number, b: number): number => (b ? gcd(b, a % b) : a);
  const divisor = gcd(length, 24);
  return divisor === 24 ? String(length / 24) : [length / divisor, 24 / divisor].join('/');
}

export function pitchMidi(name: string) {
  const match = name.match(/^([A-G])(#{1,2}|b{1,2})?(-?\d+)$/);
  if (!match) throw Error('음이름을 확인하세요.');
  const [, letter, accidental = '', octave] = match;
  const natural: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  const midi =
    12 * (Number(octave) + 1) + natural[letter] + accidental.length * (accidental.includes('b') ? -1 : 1);
  if (midi < 0 || midi > 127) throw Error('MIDI 0–127 범위 밖의 음입니다.');
  return midi;
}

export function makeEvent(pitch: string | null, quarters: number): QueryEvent {
  const spelling = pitch?.replaceAll('♯', '#').replaceAll('♭', 'b');
  return {
    id: 'q-' + crypto.randomUUID(),
    kind: spelling ? 'note' : 'rest',
    pitchMidi: spelling ? pitchMidi(spelling) : null,
    spelling,
    durationRatio: quarters,
  };
}

// Inserting an event in a tie separates the two runs. Give each remaining
// contiguous run its own identity so that transposing one cannot move the other.
export function normalizeTies(events: QueryEvent[]) {
  const result = [...events];
  for (let start = 0; start < events.length; ) {
    const first = events[start];
    if (!first.tieGroup) {
      start++;
      continue;
    }
    let end = start + 1;
    while (
      first.kind === 'note' &&
      end < events.length &&
      events[end].tieGroup === first.tieGroup &&
      events[end].pitchMidi === first.pitchMidi
    )
      end++;
    const tieGroup = end - start > 1 ? first.id : undefined;
    for (let i = start; i < end; i++) result[i] = { ...events[i], tieGroup };
    start = end;
  }
  return result;
}

function rows(events: QueryEvent[], merge = true): Row[] {
  const result: Row[] = [];
  let length = 0;
  for (const [index, event] of events.entries()) {
    const previous = events[index - 1];
    const tied =
      merge &&
      event.tieGroup &&
      event.tieGroup === previous?.tieGroup &&
      event.pitchMidi === previous.pitchMidi;
    length = ticks(event.durationRatio) + (tied ? length : 0);
    if (tied) result[result.length - 1].duration = fraction(length);
    else
      result.push({
        duration: fraction(length),
        pitches: event.spelling ? [event.spelling.replaceAll('♯', '#').replaceAll('♭', 'b')] : [],
      });
  }
  return result;
}

export function toClip(events: QueryEvent[], base: Clip): Clip {
  const { editorNotation, ...metadata } = base;
  const clip = { ...metadata, events: rows(events) };
  if (!events.some((e) => e.tieGroup || e.tupletGroup)) return clip;
  const raw = rows(events, false);
  return {
    ...clip,
    editorNotation: events.map((event, i) => ({
      ...raw[i],
      tie: event.tieGroup,
      triplet: event.tupletGroup,
    })),
  };
}

function fromRow(row: Row) {
  const [n, d = '1'] = String(row.duration).split('/');
  const beats = Number(n) / Number(d);
  if (
    !(beats >= 1 / 12 && beats <= 256) ||
    Math.abs(beats * 24 - ticks(beats)) > 1e-7 ||
    row.pitches.length > 1
  )
    throw Error('지원하지 않는 모티프 음가 또는 화음입니다.');
  return makeEvent(row.pitches[0] || null, beats);
}

export function fromClip(clip: Clip): QueryEvent[] {
  // A rhythm variation may carry notation metadata from its unmodified parent.
  if (Array.isArray(clip.editorNotation) && clip.editorNotation.length <= 4096) {
    try {
      const detailed = normalizeTies(
        clip.editorNotation.map((row) => {
          const event = fromRow(row);
          if (typeof row.tie === 'string') event.tieGroup = row.tie;
          if (typeof row.triplet === 'string')
            Object.assign(event, {
              tupletGroup: row.triplet,
              writtenDuration: event.durationRatio * 1.5,
              actualNotes: 3,
              normalNotes: 2,
            });
          return event;
        }),
      );
      const merged = rows(detailed);
      if (
        merged.length === clip.events.length &&
        merged.every(
          (row, i) =>
            row.duration === clip.events[i].duration && row.pitches.join() === clip.events[i].pitches.join(),
        )
      )
        return detailed;
    } catch {
      /* Fall back to the portable events if the optional notation is invalid. */
    }
  }
  return clip.events.map(fromRow);
}
