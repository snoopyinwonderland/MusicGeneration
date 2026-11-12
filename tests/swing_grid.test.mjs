import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../musigen/listen_template.html', import.meta.url), 'utf8');
const start = source.indexOf('function sharedSwingGrid(');
const end = source.indexOf('// Quarter positions', start);
const grid = vm.runInNewContext(source.slice(start, end) + '\nsharedSwingGrid');

test('the release and the next attack use the same swung offbeat', () => {
  const timing = grid([
    {qstamp: 0, on: ['right']},
    {qstamp: 0.5, off: ['right'], on: ['left']},
    {qstamp: 1, off: ['left']},
  ], q => 600 * q);
  assert.equal(timing.releases.get('right'), 0.5);
  assert.equal(timing.shift(timing.releases.get('right')), 100);
  assert.equal(timing.shift(0.5), 100);
  assert.equal(timing.shift(1), 0);
});

test('a sixteenth-note or triplet event keeps its beat straight across hands', () => {
  const timing = grid([
    {qstamp: 0.25, off: ['sixteenth']},
    {qstamp: 0.5, on: ['comp']},
    {qstamp: 1.5, on: ['anotherComp']},
    {qstamp: 2 + 1 / 3, on: ['triplet']},
    {qstamp: 2.5, on: ['beatThreeComp']},
  ], q => q < 2 ? 480 * q : 960 + 600 * (q - 2));
  assert.equal(timing.shift(0.5), 0);
  assert.equal(timing.shift(1.5), 80);
  assert.equal(timing.shift(2.5), 0);
});
