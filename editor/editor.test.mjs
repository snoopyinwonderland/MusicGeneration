import assert from 'node:assert/strict';
import test from 'node:test';
import { fromClip, makeEvent, normalizeTies, toClip } from './model.ts';
import { toMEI } from './mei.ts';

test('binary rhythms do not acquire unnecessary triplet brackets', () => {
  const mei = toMEI([makeEvent('G4', 2.75)], '4/4', 'C major', 'G');
  assert.doesNotMatch(mei, /<tuplet /);
});

const base = { format: 'musicanote-motif', version: 1, events: [] };
const note = (name, duration = 1) => makeEvent(name, duration);
const engrave = (events) => toMEI(events, '4/4', 'Eb major', 'auto');

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
