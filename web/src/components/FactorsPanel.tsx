import React from 'react';
import type { ModelSource, Prediction } from '../types/market';

interface FactorsPanelProps {
  prediction: Prediction;
  modelSource: ModelSource;
}

/** Each factor's contribution in probability points (roughly). */
const points = (impact: number, weight: number) => Math.round(impact * weight * 45);

export function FactorsPanel({ prediction, modelSource }: FactorsPanelProps) {
  const factors = [...prediction.factors].sort((a, b) => Math.abs(b.impact * b.weight) - Math.abs(a.impact * a.weight));

  return (
    <section aria-labelledby="factors-title">
      <h2 id="factors-title" className="text-[15px] font-semibold text-ink">What the indicators say</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-muted">
        {modelSource === 'remote' ?
        'Background only — the UP / DOWN call comes from your model, which weighs these and more.' :
        'These readings decide the call.'}
      </p>

      <ul className="mt-3 divide-y divide-line">
        {factors.map((f) => {
          const pts = points(f.impact, f.weight);
          const effect = pts > 0 ? 'Pushes up' : pts < 0 ? 'Pulls down' : 'Neutral';
          const tone = pts > 0 ? 'text-up' : pts < 0 ? 'text-down' : 'text-muted';
          const width = `${Math.min(50, Math.abs(f.impact) * 50)}%`;
          return (
            <li key={f.id} className="grid grid-cols-[minmax(0,1fr)_88px_92px] items-center gap-4 py-2.5 sm:grid-cols-[minmax(0,1fr)_140px_92px]">
              <span className="min-w-0">
                <span className="block text-sm font-medium text-ink">{f.label}</span>
                <span className="block truncate text-xs text-muted">{f.reading}</span>
              </span>
              <span className="relative h-1.5 rounded-full bg-raised" aria-hidden="true">
                <span className="absolute left-1/2 top-[-3px] h-3 w-px bg-muted/50" />
                <span
                  className={`absolute top-0 h-full rounded-full ${f.impact >= 0 ? 'bg-up' : 'bg-down'}`}
                  style={f.impact >= 0 ? { left: '50%', width } : { right: '50%', width }} />

              </span>
              <span className={`text-right text-[13px] font-medium ${tone}`}>{effect}</span>
            </li>);

        })}
      </ul>
    </section>);

}
