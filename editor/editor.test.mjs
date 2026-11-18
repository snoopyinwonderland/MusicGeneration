import assert from 'node:assert/strict';
import test from 'node:test';
import { fromClip, makeEvent, normalizeTies, toClip, workshopEvents } from './model.ts';
import { toMEI } from './mei.ts';

test('binary rhythms do not acquire unnecessary triplet brackets', () => {
  const mei = toMEI([makeEvent('G4', 2.75)], '4/4', 'C major', 'G');
  assert.doesNotMatch(mei, /<tuplet /);
});

const base = { format: 'musicanote-motif', version: 1, events: [] };
const note = (name, duration = 1) => makeEvent(name, duration);
const engrave = (events) => toMEI(events, '4/4', 'Eb major', 'auto');

test('a native query without spelling uses its MIDI pitch and preserves rests', () => {
  const notes = workshopEvents([
    { id: 'a', kind: 'note', pitchMidi: 61, durationRatio: 0.5 },
    { id: 'b', kind: 'rest', pitchMidi: null, durationRatio: 1, spelling: 'D4' },
  ]);
  assert.deepEqual(toClip(notes, base).events, [
    { duration: '1/2', pitches: ['C#4'] },
    { duration: '1', pitches: [] },
  ]);
});

test('the adapter rejects unsupported durations before rounding', () => {
  for (const duration of [1 / 16, 4 / 5, Infinity])
    assert.throws(() => toClip([note('C4', duration)], base), /지원/);
});

test('a native duplet restores its written duration and ratio', () => {
  const pair = ['C4', 'Eb4'].map((p) => ({
    ...note(p, 0.75),
    tupletGroup: 'duplet',
    writtenDuration: 0.5,
    actualNotes: 2,
    normalNotes: 3,
  }));
  const events = fromClip(toClip(pair, base));
  assert.deepEqual(
    events.map((e) => [e.durationRatio, e.writtenDuration, e.actualNotes, e.normalNotes]),
    [
      [0.75, 0.5, 2, 3],
      [0.75, 0.5, 2, 3],
    ],
  );
});

test('tied written notes round-trip through the sounding motif', () => {
  const pair = [note('Bb3'), note('Bb3')].map((e) => ({ ...e, tieGroup: 'legato' }));
  const clip = toClip(normalizeTies(pair), base);
  assert.deepEqual(clip.events, [{ duration: '2', pitches: ['Bb3'] }]);
  const restored = fromClip(clip);
  assert.equal(restored.length, 2);
  assert.ok(restored[0].tieGroup);
  assert.equal(restored[0].tieGroup, restored[1].tieGroup);
  assert.equal((engrave(restored).match(/<tie /g) || []).length, 1);
  const altered = { ...clip, events: [{ duration: '3/2', pitches: ['Bb3'] }] };
  assert.deepEqual(
    fromClip(altered).map((e) => e.durationRatio),
    [1.5],
  );
});

test('an inserted rest splits the tie and isolates future transpositions', () => {
  const notes = Array.from({ length: 4 }, () => ({ ...note('D4'), tieGroup: 'chain' }));
  notes.splice(2, 0, note(null));
  const split = normalizeTies(notes);
  assert.notEqual(split[0].tieGroup, split[3].tieGroup);
  assert.deepEqual(
    toClip(split, base).events.map((e) => e.duration),
    ['2', '1', '2'],
  );
});

test('three imported triplet eighths share one bracket across a rest', () => {
  const events = ['C4', null, 'Eb4'].map((p) => note(p, 1 / 3));
  const mei = engrave(events);
  assert.equal((mei.match(/<tuplet /g) || []).length, 1);
  assert.equal((mei.match(/dur="8"/g) || []).length, 3);
  assert.match(mei, /<rest /);
});

test('the two glyphs of a five-beat note address the same editable event', () => {
  const event = note('Eb4', 5);
  const mei = engrave([event]);
  assert.ok(mei.includes(event.id + '-p0'));
  assert.ok(mei.includes(event.id + '-p1'));
  assert.match(mei, /<measure n="2"/);
  assert.match(mei, /<tie /);
});
