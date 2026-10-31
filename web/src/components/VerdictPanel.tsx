import React from 'react';
import { motion } from 'framer-motion';
import { ArrowDownRightIcon, ArrowUpRightIcon } from 'lucide-react';
import { timeframeLabel } from '../utils/format';
import type { ModelInfo, ModelSource, Prediction } from '../types/market';

interface VerdictPanelProps {
  prediction: Prediction;
  minutes: number;
  model: ModelInfo;
  modelSource: ModelSource;
  loading: boolean;
}

/** One plain-language line on how much to trust this call. */
function readout(probability: number, dir: string): string {
  if (probability < 55) return `Close to a coin flip — the model only barely leans ${dir}. Usually better to wait.`;
  if (probability < 65) return `Leans ${dir}, but not strongly. Treat it as a hint, not a signal.`;
  return `Clear lean ${dir}. Still use a stop loss — strong calls miss too.`;
}

export function VerdictPanel({ prediction, minutes, model, modelSource, loading }: VerdictPanelProps) {
  const isUp = prediction.direction === 'up';
  const upChance = isUp ? prediction.probability : 100 - prediction.probability;
  const Icon = isUp ? ArrowUpRightIcon : ArrowDownRightIcon;
  // 'local' only when the model call failed — then the indicators decide, and we say so
  const source = modelSource === 'remote' ? 'Your model' : 'Indicators only';

  return (
    <section aria-label="Prediction" aria-busy={loading} aria-live="polite">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[15px] font-semibold text-ink">Next {timeframeLabel(minutes)}</h2>
        <span className="rounded-full bg-accent/10 px-2.5 py-0.5 text-xs font-medium text-accent">{source}</span>
      </div>

      {loading ?
      <div className="mt-5 space-y-4" aria-hidden="true">
          <div className="h-14 w-40 animate-pulse rounded-xl bg-raised" />
          <div className="h-4 w-full animate-pulse rounded bg-raised" />
          <div className="h-2 w-full animate-pulse rounded-full bg-raised" />
        </div> :

      <motion.div
        key={`${prediction.candle.time}-${prediction.direction}-${prediction.probability}-${minutes}`}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}>

          <div className="mt-4 flex items-center justify-between gap-4">
            <p
            className={`flex items-center gap-2 rounded-2xl px-4 py-2 text-4xl font-bold tracking-tight ${
            isUp ? 'bg-up/10 text-up' : 'bg-down/10 text-down'}`
            }>
              <Icon className="h-8 w-8" strokeWidth={2.5} aria-hidden="true" />
              {isUp ? 'UP' : 'DOWN'}
            </p>
            <p className="text-right">
              <span className="block text-3xl font-semibold tabular-nums text-ink">{prediction.probability}%</span>
              <span className="text-[13px] text-muted">chance</span>
            </p>
          </div>

          <p className="mt-4 text-sm leading-relaxed text-ink/90">{readout(prediction.probability, isUp ? 'up' : 'down')}</p>

          <div className="mt-5">
            <div className="mb-1.5 flex justify-between text-[13px] font-medium tabular-nums">
              <span className="text-up">Up {upChance}%</span>
              <span className="text-down">Down {100 - upChance}%</span>
            </div>
            <div className="flex h-2 gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
              <div className="rounded-l-full bg-up" style={{ width: `${upChance}%` }} />
              <div className="flex-1 rounded-r-full bg-down" />
            </div>
          </div>
        </motion.div>
      }

      <div className="mt-5 border-t border-line pt-4 text-[13px] leading-relaxed text-muted">
        <p>
          <span className="font-medium text-ink">{model.name}</span>
        </p>
        <p>
          Right <span className="font-medium tabular-nums text-ink">{model.accuracy}%</span> of the time in walk-forward testing · {model.lookback}
        </p>
      </div>
    </section>);

}
