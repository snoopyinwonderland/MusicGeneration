import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Keyboard } from './Keyboard';
import { pitchName } from './pitch';
import { insertAfterSelection, stepSelectedDurations, transposeSelectedEvents } from './queryEdit';
import { makeEvent, ticks, fraction, type QueryEvent } from './model';
import { toMEI } from './mei';

type Toolkit = {
  setOptions(o: object): void;
  loadData(s: string): boolean;
  getPageCount(): number;
  renderToSVG(n: number): string;
  destroy(): void;
};
declare const verovio: { toolkit: new () => Toolkit };
type Props = {
  value: QueryEvent[];
  onChange: (events: QueryEvent[]) => void;
  meter: string;
  tonality: string;
  clef: string;
  setClef: (s: string) => void;
  audition: (pitch: number) => void;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
};
const durations = [0.125, 0.25, 0.375, 0.5, 0.75, 1, 1.5, 2, 3, 4, 6];
const labels = ['32분', '16분', '점16분', '8분', '점8분', '4분', '점4분', '2분', '점2분', '온음', '점온음'];
export function MotifEditor({
  value,
  onChange,
  meter,
  tonality,
  clef,
  setClef,
  audition,
  undo,
  redo,
  canUndo,
  canRedo,
}: Props) {
  const [flat, setFlat] = useState(false),
    [duration, setDuration] = useState(1),
    [ids, select] = useState<string[]>([]);
  const host = useRef<HTMLDivElement>(null),
    tool = useRef<Toolkit | null>(null);
  const [error, setError] = useState(''),
    [retry, setRetry] = useState(0);
  const [pageWidth, setPageWidth] = useState(2000);
  useLayoutEffect(() => {
    const element = host.current!;
    const resize = () => setPageWidth(Math.max(480, Math.round(element.clientWidth * 1.7)));
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const drag = useRef<{ id: string; y: number; extend: boolean } | null>(null);
  const selected = value.filter((e) => ids.includes(e.id)),
    active = selected.map((e) => e.id);
  useEffect(
    () => () => {
      tool.current?.destroy();
      tool.current = null;
    },
    [],
  );
  useLayoutEffect(() => {
    const el = host.current!;
    if (!value.length) {
      el.replaceChildren();
      setError('');
      return;
    }
    try {
      const tk = (tool.current ??= new verovio.toolkit());
      tk.setOptions({
        pageWidth,
        pageHeight: 2500,
        scale: 45,
        svgViewBox: true,
        breaks: 'auto',
        adjustPageHeight: true,
        header: 'none',
        footer: 'none',
      });
      if (!tk.loadData(toMEI(value, meter, tonality, clef))) throw Error('입력 악보를 그리지 못했습니다.');
      el.innerHTML = Array.from({ length: tk.getPageCount() }, (_, i) => tk.renderToSVG(i + 1)).join('');
      for (const glyph of el.querySelectorAll<SVGGElement>('g.note,g.rest')) {
        const box = glyph.getBBox(),
          r = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        for (const [k, v] of Object.entries({
          x: box.x - 16,
          y: box.y - 12,
          width: box.width + 32,
          height: box.height + 24,
          fill: 'transparent',
          stroke: 'none',
          opacity: 0,
          'pointer-events': 'all',
        }))
          r.setAttribute(k, String(v));
        glyph.prepend(r);
        glyph.dataset.event = glyph.id.replace(/-p\d+$/, '');
      }
      setError('');
    } catch (err) {
      el.replaceChildren();
      setError(String(err));
    }
  }, [value, meter, tonality, clef, retry, pageWidth]);
  useLayoutEffect(() => {
    host.current
      ?.querySelectorAll<SVGGElement>('[data-event]')
      .forEach((g) => g.classList.toggle('chosen', ids.includes(g.dataset.event!)));
  }, [value, meter, tonality, clef, ids, retry, pageWidth]);
  function choose(id: string, multi = false) {
    select(multi ? (active.includes(id) ? active.filter((v) => v !== id) : [...active, id]) : [id]);
  }
  function insert(pitch: number | null) {
    const event = makeEvent(pitch === null ? null : pitchName(pitch, flat), duration);
    onChange(insertAfterSelection(value, active, event));
    select([event.id]);
    if (pitch !== null) audition(pitch);
  }
  function changeLength(d: number, targets: string[]) {
    onChange(
      value.map((e) =>
        targets.includes(e.id)
          ? {
              ...e,
              writtenDuration: e.tupletGroup ? d : undefined,
              durationRatio: e.tupletGroup ? (d * 2) / 3 : d,
            }
          : e,
      ),
    );
  }
  function transpose(step: number, targets = active) {
    if (targets.length) onChange(transposeSelectedEvents(value, targets, step, flat));
  }
  const contiguous =
    selected.length > 1 &&
    value.indexOf(selected.at(-1)!) - value.indexOf(selected[0]) + 1 === selected.length;
  const commonTie = selected[0]?.tieGroup && selected.every((e) => e.tieGroup === selected[0].tieGroup);
  const commonTriplet =
    selected[0]?.tupletGroup && selected.every((e) => e.tupletGroup === selected[0].tupletGroup);
  function tie() {
    const group = 'tie-' + crypto.randomUUID();
    const oldGroups = new Set(selected.map((e) => e.tieGroup).filter(Boolean));
    onChange(
      value.map((e) =>
        active.includes(e.id)
          ? { ...e, tieGroup: commonTie ? undefined : group }
          : oldGroups.has(e.tieGroup)
            ? { ...e, tieGroup: undefined }
            : e,
      ),
    );
  }
  function triplet() {
    const group = 'triplet-' + crypto.randomUUID();
    onChange(
      value.map((e) => {
        if (!active.includes(e.id)) return e;
        const written = e.writtenDuration ?? e.durationRatio;
        return {
          ...e,
          tupletGroup: commonTriplet ? undefined : group,
          writtenDuration: commonTriplet ? undefined : written,
          durationRatio: commonTriplet ? written : (written * 2) / 3,
          actualNotes: commonTriplet ? undefined : 3,
          normalNotes: commonTriplet ? undefined : 2,
        };
      }),
    );
  }
  function remove() {
    const targets = active.length ? active : [value.at(-1)?.id];
    onChange(value.filter((e) => !targets.includes(e.id)));
    select([]);
  }
  return (
    <section
      className="event-editor"
      aria-label="모티프 악보 입력기"
      onKeyDown={(e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
          e.preventDefault();
          e.shiftKey ? redo() : undo();
        }
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
          e.preventDefault();
          redo();
        }
      }}
    >
      <div className="editor-head">
        <h2>모티프 악보 입력기</h2>
        <div>
          <button disabled={!canUndo} onClick={undo}>
            실행 취소
          </button>
          <button disabled={!canRedo} onClick={redo}>
            다시 실행
          </button>
          <button onClick={remove} disabled={!value.length}>
            삭제
          </button>
        </div>
      </div>
      <div className="editor-settings">
        <span>
          {tonality.replace(' major', '장조').replace(' minor', '단조')} · {meter}
        </span>
        <label>
          건반 입력 음가{' '}
          <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
            {durations.map((d, i) => (
              <option key={d} value={d}>
                {labels[i]}
              </option>
            ))}
            <option value={1 / 3}>8분 셋잇단</option>
          </select>
        </label>
        <label>
          음자리표{' '}
          <select value={clef} onChange={(e) => setClef(e.target.value)}>
            <option value="auto">음역에 맞게</option>
            <option value="G">높은음자리표</option>
            <option value="F">낮은음자리표</option>
          </select>
        </label>
        <button onClick={() => transpose(1)} disabled={!selected.some((e) => e.kind === 'note')}>
          반음 ↑
        </button>
        <button onClick={() => transpose(-1)} disabled={!selected.some((e) => e.kind === 'note')}>
          반음 ↓
        </button>
      </div>
      <div className="event-strip" aria-label="음표별 음가">
        {value.map((e, i) => (
          <div key={e.id} className="duration-cell" style={{ flexGrow: Math.min(4, e.durationRatio) }}>
            <button
              aria-pressed={active.includes(e.id)}
              onClick={(ev) => choose(e.id, ev.shiftKey || ev.ctrlKey || ev.metaKey)}
            >
              {i + 1} · {e.spelling || '쉼'} <small>{fraction(ticks(e.durationRatio))}박</small>
            </button>
            <div>
              {([-1, 1] as const).map((dir) => (
                <button
                  key={dir}
                  aria-label={i + 1 + '번째 음가 ' + (dir < 0 ? '줄이기' : '늘리기')}
                  onClick={() => {
                    onChange(stepSelectedDurations(value, active, e.id, durations, dir));
                    if (!active.includes(e.id)) select([e.id]);
                  }}
                >
                  {dir < 0 ? '−' : '+'}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      {!value.length && <p className="staff-placeholder">건반을 눌러 모티프를 시작하세요.</p>}
      <div
        className="editor-score"
        aria-label="편집 악보"
        ref={host}
        onPointerDown={(ev) => {
          const id = (ev.target as Element).closest<SVGGElement>('[data-event]')?.dataset.event;
          if (id) {
            ev.preventDefault();
            drag.current = { id, y: ev.clientY, extend: ev.shiftKey || ev.ctrlKey || ev.metaKey };
            ev.currentTarget.setPointerCapture(ev.pointerId);
          }
        }}
        onPointerUp={(ev) => {
          const start = drag.current;
          drag.current = null;
          if (!start) return;
          const distance = Math.round((start.y - ev.clientY) / 6);
          if (distance && value.find((e) => e.id === start.id)?.kind === 'note') {
            const targets = active.includes(start.id) ? active : [start.id];
            select(targets);
            transpose(distance, targets);
          } else choose(start.id, start.extend);
        }}
        onPointerCancel={() => {
          drag.current = null;
        }}
      />
      {error && (
        <p role="alert">
          {error} <button onClick={() => setRetry((n) => n + 1)}>다시 그리기</button>
        </p>
      )}
      <Keyboard onNote={insert} preferFlat={flat} onPreferenceChange={setFlat} />
      <div className="editor-values">
        <strong>음가</strong>
        {durations.map((d, i) => (
          <button
            key={d}
            aria-pressed={duration === d}
            onClick={() => {
              setDuration(d);
              if (active.length) changeLength(d, active);
            }}
          >
            {labels[i]}
          </button>
        ))}
        <button onClick={() => insert(null)}>쉼표 입력</button>
        <button
          disabled={
            !contiguous || selected.some((e) => e.pitchMidi === null || e.pitchMidi !== selected[0].pitchMidi)
          }
          onClick={tie}
        >
          {commonTie ? '붙임줄 풀기' : '붙임줄'}
        </button>
        <button
          disabled={
            !contiguous ||
            (!commonTriplet &&
              (selected.length !== 3 ||
                selected.some(
                  (e) => e.tupletGroup || ticks(e.durationRatio) % 3 !== 0 || e.durationRatio < 0.125,
                )))
          }
          onClick={triplet}
        >
          {commonTriplet ? '셋잇단 풀기' : '셋잇단음표'}
        </button>
        <button onClick={() => select([])} disabled={!active.length}>
          선택 해제
        </button>
      </div>
      <p>
        음을 누르면 선택하고, 위아래로 끌면 음높이를 바꿉니다. Shift를 누른 채 클릭하면 여러 음을 선택합니다.
      </p>
    </section>
  );
}
