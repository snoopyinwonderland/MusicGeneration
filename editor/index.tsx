import React from 'react';
import { createRoot } from 'react-dom/client';
import { MotifEditor } from './Editor';
import { fromClip, normalizeTies, pitchMidi, toClip, type Clip, type QueryEvent } from './model';

type Options = {
  onChange: (clip: Clip) => void;
  audition: (pitch: number) => void;
  error: (s: string) => void;
};
type Snapshot = { events: QueryEvent[]; clip: Clip };
export function mount(host: HTMLElement, options: Options) {
  const root = createRoot(host);
  const empty: Clip = {
    format: 'musicanote-motif',
    version: 1,
    name: '나의 모티프',
    source: { kind: 'user' },
    events: [],
  };
  let current: Snapshot = { events: [], clip: empty };
  const past: Snapshot[] = [],
    future: Snapshot[] = [];
  let meter = '4/4',
    key = 'C major',
    clef = 'auto';
  function remember() {
    past.push(current);
    if (past.length > 100) past.shift();
    future.length = 0;
  }
  function restore(from: Snapshot[], into: Snapshot[]) {
    if (!from.length) return;
    into.push(current);
    current = from.pop()!;
    draw();
    options.onChange(current.clip);
  }
  function change(edited: QueryEvent[]) {
    const events = normalizeTies(edited);
    const clip = toClip(events, current.clip);
    if (
      events.length > 4096 ||
      clip.events.some((r) => {
        const [n, d = '1'] = r.duration.split('/');
        return +n / +d > 256;
      })
    ) {
      options.error('모티프는 음·쉼 4096개까지, 붙인 음은 256박까지 지원합니다.');
      return;
    }
    remember();
    current = { events, clip };
    draw();
    options.onChange(clip);
  }
  function draw() {
    root.render(
      <MotifEditor
        value={current.events}
        onChange={change}
        meter={meter}
        tonality={key}
        clef={clef}
        setClef={(s) => {
          clef = s;
          draw();
        }}
        audition={options.audition}
        undo={() => restore(past, future)}
        redo={() => restore(future, past)}
        canUndo={!!past.length}
        canRedo={!!future.length}
      />,
    );
  }
  draw();
  return {
    replace(clip: Clip) {
      if (clip === current.clip || JSON.stringify(clip) === JSON.stringify(current.clip)) return;
      const events = fromClip(clip);
      remember();
      current = { clip, events };
      draw();
    },
    configure(newMeter: string, newKey: string) {
      meter = newMeter;
      key = newKey;
      draw();
    },
    performance(tempo: number) {
      let time = 0;
      return current.clip.events.flatMap((row) => {
        const [a, b = '1'] = row.duration.split('/'),
          beats = Number(a) / Number(b),
          start = time;
        time += (beats * 60) / tempo;
        if (!row.pitches.length) return [];
        return [{ pitch: pitchMidi(row.pitches[0]), start, end: time, bank: 'piano' }];
      });
    },
    destroy() {
      root.unmount();
    },
  };
}
