import React from 'react';
import { CandleChart } from './CandleChart';
import { CandleCountdown } from './CandleCountdown';
import { useElementSize } from '../hooks/useElementSize';
import { formatPct, formatPrice, timeframeLabel } from '../utils/format';
import type { Candle, HistoryEntry, Instrument, Prediction } from '../types/market';

interface ChartPanelProps {
  instrument: Instrument;
  candles: Candle[];
  forming: Candle | null;
  prediction: Prediction;
  history: HistoryEntry[];
  barMinutes: number;
  price: number;
  change: {pct: number;label: string;};
  closesAt: number | null;
  loading: boolean;
}

export function ChartPanel({
  instrument,
  candles,
  forming,
  prediction,
  history,
  barMinutes,
  price,
  change,
  closesAt,
  loading
}: ChartPanelProps) {
  const [ref, size] = useElementSize<HTMLDivElement>();
  const positive = change.pct >= 0;

  return (
    <div aria-label={`${instrument.symbol} chart`} className="flex h-full min-w-0 flex-col">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-3xl font-semibold tracking-tight tabular-nums text-ink">{formatPrice(price, instrument.decimals)}</span>
            <span
              className={`rounded-md px-2 py-0.5 text-sm font-semibold tabular-nums ${positive ? 'bg-up/10 text-up' : 'bg-down/10 text-down'}`}>
              {formatPct(change.pct)}
            </span>
            <LiveBadge live={!!forming} />
          </div>
          <p className="mt-1 text-[13px] text-muted">
            {timeframeLabel(barMinutes)} candles · change over {change.label}
          </p>
        </div>
        {closesAt && <CandleCountdown closesAt={closesAt} />}
      </div>

      <div ref={ref} className={`relative mt-4 min-h-[300px] flex-1 transition-opacity duration-200 ${loading ? 'opacity-30' : 'opacity-100'}`}>
        {size.width > 0 && size.height > 0 &&
        <CandleChart
          width={size.width}
          height={size.height}
          candles={candles}
          forming={forming}
          prediction={prediction}
          history={history}
          decimals={instrument.decimals}
          minutes={barMinutes} />

        }
      </div>

      <ul className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs text-muted">
        <li className="flex items-center gap-2">
          <span className="h-3.5 w-2.5 rounded-[3px] border border-dashed border-accent" aria-hidden="true" />
          Predicted next candle
        </li>
        <li className="flex items-center gap-2">
          <span className="w-4 border-t border-dashed border-down" aria-hidden="true" />
          Stop loss
        </li>
        <li className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-up" aria-hidden="true" />
          Past call right
        </li>
        <li className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full border-[1.5px] border-down" aria-hidden="true" />
          Past call wrong
        </li>
        <li className="ml-auto hidden lg:block">Hover a candle for details</li>
      </ul>
    </div>);

}

function LiveBadge({ live }: {live: boolean;}) {
  return (
    <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${live ? 'bg-up/10 text-up' : 'bg-raised text-muted'}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${live ? 'animate-pulse bg-up' : 'bg-muted'}`} aria-hidden="true" />
      {live ? 'Live' : 'Last session'}
    </span>);

}
