import React from 'react';
import { timeframeLabel } from '../utils/format';

interface MinutesPickerProps {
  value: number;
  onChange: (minutes: number) => void;
  /** Bar sizes the model was trained on. */
  options: number[];
}

export function MinutesPicker({ value, onChange, options }: MinutesPickerProps) {
  return (
    <div role="group" aria-label="Timeframe" className="flex rounded-lg bg-surface p-1 ring-1 ring-line">
      {options.map((m) =>
      <button
        key={m}
        type="button"
        aria-pressed={m === value}
        onClick={() => onChange(m)}
        className={`rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 ${
        m === value ? 'bg-raised text-ink shadow-sm' : 'text-muted hover:text-ink'}`
        }>

          {timeframeLabel(m)}
        </button>
      )}
    </div>);

}
