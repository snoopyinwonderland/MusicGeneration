import React from 'react';
import { isBlack, pitchName } from './pitch';

const keys = Array.from({ length: 53 }, (_, i) => 36 + i);
const whiteKeys = keys.filter((key) => !isBlack(key));

type KeyboardProps = {
  onNote: (midi: number) => void;
  preferFlat: boolean;
  onPreferenceChange: (useFlats: boolean) => void;
};

export function Keyboard({ onNote, preferFlat, onPreferenceChange }: KeyboardProps) {
  return (
    <div className="keyboard" role="group" aria-label="C2부터 E6까지의 멜로디 건반">
      <div className="accidental-toggle" aria-label="검은 건반 임시표 선택">
        <button aria-pressed={!preferFlat} onClick={() => onPreferenceChange(false)}>
          ♯
        </button>
        <button aria-pressed={preferFlat} onClick={() => onPreferenceChange(true)}>
          ♭
        </button>
      </div>
      <div className="keyboard-keys">
        {whiteKeys.map((midi) => (
          <div key={midi} className="key-pair">
            <button
              className="white-key"
              aria-label={pitchName(midi, preferFlat)}
              onClick={() => onNote(midi)}
            >
              {midi % 12 === 0 ? pitchName(midi) : ''}
            </button>
            {midi < keys[keys.length - 1] && isBlack(midi + 1) && (
              <button
                className="black-key"
                aria-label={pitchName(midi + 1, preferFlat)}
                onClick={() => onNote(midi + 1)}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
