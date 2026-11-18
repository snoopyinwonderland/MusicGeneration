import React from 'react';
import { createRoot } from 'react-dom/client';
import { MelodyQueryInput, type Meter, type Query } from '@musicanote/melody-query-input';
import '@musicanote/melody-query-input/style.css';
import { fromClip, workshopEvents, pitchMidi, toClip, type Clip } from './model';
import { toMEI } from './mei';

type Options = {
  onChange: (clip: Clip, meter: Meter) => void;
  audition: (pitch: number) => void;
  preview: () => void;
  error: (message: string) => void;
};
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

export function mount(host: HTMLElement, options: Options) {
  const root = createRoot(host);
  // In 0.1.0 the black button is nested in the white key's keyboard handler.
  function activateBlackKey(event: KeyboardEvent) {
    const key = event.target;
    if (
      key instanceof HTMLButtonElement &&
      key.matches('.keyboard .black-key') &&
      (event.key === 'Enter' || event.key === ' ')
    ) {
      event.preventDefault();
      event.stopPropagation();
      if (!event.repeat) key.click();
    }
  }
  host.addEventListener('keydown', activateBlackKey, true);
  const blank: Clip = {
    format: 'musicanote-motif',
    version: 1,
    name: '나의 모티프',
    events: [],
    source: { kind: 'user' },
  };
  let clip = blank;
  let query: Query = { version: 1, mode: 'melody_rhythm', meter: '4/4', startsOnDownbeat: true, events: [] };
  let key = 'C major',
    clef = 'auto',
    revision = 0,
    error = '';
  let previous: { clip: Clip; query: Query } | null = null;
  const origins = new WeakMap<Query['events'], Clip>();
  let displayed: Query['events'];

  function change(next: Query) {
    try {
      if (!['3/4', '4/4', '6/8'].includes(next.meter))
        throw Error('이 작업실에서 작곡할 수 있는 박자는 3/4, 4/4, 6/8입니다.');
      if (next.events === displayed) {
        const meterChanged = query.meter !== next.meter;
        query = { ...query, mode: next.mode, meter: next.meter };
        error = '';
        draw();
        if (meterChanged) options.onChange(clip, query.meter);
        return;
      }
      const events = workshopEvents(next.events);
      const oldIDs = new Set(query.events.map((e) => e.id));
      const origin = origins.get(next.events) ?? (events.some((e) => oldIDs.has(e.id)) ? clip : blank);
      const updated = toClip(events, origin);
      const addedNote = events.length === oldIDs.size + 1 && events.find((e) => !oldIDs.has(e.id));
      query = { ...next, events };
      clip = updated;
      error = '';
      draw();
      options.onChange(clip, query.meter);
      if (addedNote && addedNote.pitchMidi !== null) options.audition(addedNote.pitchMidi);
    } catch (reason) {
      error = reason instanceof Error ? reason.message : String(reason);
      draw();
      options.error(error);
    }
  }

  function draw() {
    // The packaged engraver also accepts score context on its controlled query.
    const [count, unit] = query.meter.split('/').map(Number);
    const bar = (count * 4) / unit;
    let elapsed = 0;
    const value = {
      ...query,
      keyFifths: signatures[key] ?? 0,
      clefShape: clef === 'auto' ? undefined : clef,
      events: query.events.map((e) => {
        const measure = Math.floor((elapsed + 1e-8) / bar) + 1;
        elapsed += e.durationRatio;
        return { ...e, measure };
      }),
    };
    displayed = value.events;
    origins.set(displayed, clip);
    root.render(
      <>
        <div className="motif-input-head">
          <h2>모티프 악보 입력기</h2>
          <label>
            음자리표{' '}
            <select
              value={clef}
              onChange={(e) => {
                clef = e.target.value;
                draw();
              }}
            >
              <option value="auto">음역에 맞게</option>
              <option value="G">높은음자리표</option>
              <option value="F">낮은음자리표</option>
            </select>
          </label>
          {previous && (
            <button
              onClick={() => {
                const restored = previous!;
                previous = { clip, query };
                clip = restored.clip;
                query = restored.query;
                revision++;
                error = '';
                draw();
                options.onChange(clip, query.meter);
              }}
            >
              이전 모티프와 전환
            </button>
          )}
        </div>
        {error && (
          <p className="motif-input-error" role="alert">
            {error}
          </p>
        )}
        <MelodyQueryInput key={revision} value={value} onChange={change} onPreview={options.preview} />
      </>,
    );
  }
  draw();
  return {
    replace(next: Clip) {
      if (next === clip || JSON.stringify(next) === JSON.stringify(clip)) return;
      const events = fromClip(next);
      previous = { clip, query };
      clip = next;
      query = { ...query, mode: 'melody_rhythm', events };
      revision++;
      error = '';
      draw();
    },
    configure(meter: Meter, tonality: string) {
      query = { ...query, meter };
      key = tonality;
      draw();
    },
    score() {
      return toMEI(query.events, query.meter, key, clef);
    },
    performance(tempo: number) {
      let time = 0;
      return clip.events.flatMap((row) => {
        const [a, b = '1'] = row.duration.split('/'),
          start = time;
        time += ((Number(a) / Number(b)) * 60) / tempo;
        return row.pitches.length
          ? [{ pitch: pitchMidi(row.pitches[0]), start, end: time, bank: 'piano' }]
          : [];
      });
    },
    destroy() {
      host.removeEventListener('keydown', activateBlackKey, true);
      root.unmount();
    },
  };
}
