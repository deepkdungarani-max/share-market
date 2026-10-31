import React from 'react';
import { AlertTriangleIcon } from 'lucide-react';
import { formatPct, formatPrice } from '../utils/format';
import type { Quote } from '../utils/marketData';
import type { Instrument } from '../types/market';

interface MarketWatchProps {
  instruments: Instrument[];
  quotes: Record<string, Quote> | null;
  error: string | null;
  onSelect: (symbol: string) => void;
}

export function MarketWatch({ instruments, quotes, error, onSelect }: MarketWatchProps) {
  return (
    <section aria-labelledby="market-watch" className="mt-14">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="market-watch" className="text-lg font-semibold text-ink">Market watch</h2>
        <p className="text-[13px] text-muted">Latest price · change vs previous close · click a card to see the prediction</p>
      </div>

      {error && !quotes &&
      <p className="mb-4 flex items-start gap-3 rounded-xl bg-down/10 px-4 py-3 text-sm text-ink/90" role="alert">
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0 text-down" aria-hidden="true" />
          Couldn't load live prices ({error}). Make sure start.bat is running — retrying every minute.
        </p>
      }

      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {instruments.map((inst) => {
          const q = quotes?.[inst.symbol];
          const positive = (q?.changePct ?? 0) >= 0;
          return (
            <li key={inst.symbol}>
              <button
                type="button"
                onClick={() => onSelect(inst.symbol)}
                className="group flex w-full flex-col gap-3 rounded-xl border border-line bg-surface p-4 text-left transition-colors duration-150 hover:border-accent/50 hover:bg-raised/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/60">

                <span className="flex items-start justify-between gap-3">
                  <span className="min-w-0">
                    <span className="block truncate text-[15px] font-semibold text-ink">{inst.symbol}</span>
                    <span className="block truncate text-[13px] text-muted">{inst.name}</span>
                  </span>
                  {q ?
                  <span
                    className={`shrink-0 rounded-md px-2 py-0.5 text-[13px] font-semibold tabular-nums ${
                    positive ? 'bg-up/10 text-up' : 'bg-down/10 text-down'}`
                    }>

                      {formatPct(q.changePct)}
                    </span> :

                  <span className="h-6 w-16 shrink-0 animate-pulse rounded-md bg-raised" aria-hidden="true" />
                  }
                </span>
                <span className="flex items-end justify-between gap-3">
                  {q ?
                  <>
                      <span className="text-lg font-semibold tabular-nums text-ink">{formatPrice(q.price, inst.decimals)}</span>
                      <Sparkline closes={q.closes} up={positive} />
                    </> :

                  <>
                      <span className="h-7 w-24 animate-pulse rounded-md bg-raised" aria-hidden="true" />
                      <span className="h-8 w-24 animate-pulse rounded-md bg-raised/60" aria-hidden="true" />
                    </>
                  }
                </span>
              </button>
            </li>);

        })}
      </ul>
    </section>);

}

function Sparkline({ closes, up }: {closes: number[];up: boolean;}) {
  const W = 96;
  const H = 32;
  if (closes.length < 2) return <svg width={W} height={H} aria-hidden="true" />;
  const max = Math.max(...closes);
  const min = Math.min(...closes);
  const range = max - min || 1;
  const pts = closes.map((v, i) => [i / (closes.length - 1) * W, H - (v - min) / range * (H - 4) - 2]);
  const line = pts.map(([px, py]) => `${px},${py}`).join(' ');
  const color = up ? 'rgb(var(--up))' : 'rgb(var(--down))';
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden="true" className="shrink-0">
      <polygon points={`0,${H} ${line} ${W},${H}`} fill={color} opacity={0.08} />
      <polyline points={line} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>);

}
