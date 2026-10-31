import React from 'react';
import { ArrowDownRightIcon, ArrowRightIcon, ArrowUpRightIcon, CheckIcon, MinusIcon, XIcon } from 'lucide-react';
import { formatCandleTime, formatPct, timeframeLabel } from '../utils/format';
import type { Direction, HistoryEntry } from '../types/market';

/** Each call the model made on this chart, against what the candle did: its close, how far it went up and down
 *  on the way, and whether the call was right. A candle whose close didn't change isn't scored. */
export function HistoryPanel({ history, minutes, decimals }: {history: HistoryEntry[];minutes: number;decimals: number;}) {
  const scored = history.filter((h) => h.hit !== null);
  const hits = scored.filter((h) => h.hit).length;
  const rate = scored.length ? Math.round(hits / scored.length * 100) : 0;
  const price = (v: number) => `₹${v.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;

  return (
    <section aria-labelledby="history-title">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="history-title" className="text-[15px] font-semibold text-ink">Past calls</h2>
        {history.length > 0 &&
        <p className="text-[13px] text-muted">
            <span className="font-semibold tabular-nums text-ink">
              {hits} of {scored.length}
            </span>{' '}
            right · <span className={rate >= 55 ? 'text-up' : rate >= 45 ? 'text-ink' : 'text-down'}>{rate}%</span>
          </p>
        }
      </div>

      {history.length === 0 ?
      <p className="mt-6 rounded-lg bg-raised/50 px-4 py-6 text-center text-sm leading-relaxed text-muted">
          No scored calls yet. Each prediction is saved and appears here as right or wrong once its {timeframeLabel(minutes)} candle closes.
        </p> :

      <div className="mt-3 overflow-x-auto">
      <table className="w-full min-w-[560px] text-sm">
          <thead className="text-xs text-muted">
            <tr className="border-b border-line">
              <th scope="col" className="py-2 pr-3 text-left font-medium">Candle</th>
              <th scope="col" className="px-3 py-2 text-left font-medium">Called</th>
              <th scope="col" className="px-3 py-2 text-left font-medium">Actual</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Close</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Highest · lowest</th>
              <th scope="col" className="py-2 pl-3 text-right font-medium">Result</th>
            </tr>
          </thead>
          <tbody>
            {history.map((h) =>
          <tr key={h.start} className="border-b border-line/60 last:border-0">
                <td className="whitespace-nowrap py-2.5 pr-3 tabular-nums text-ink">{formatCandleTime(h.start, minutes)}</td>
                <td className="whitespace-nowrap px-3 py-2.5">
                  <DirectionTag direction={h.predicted} />
                  <span className="ml-1.5 text-xs tabular-nums text-muted">{h.probability}%</span>
                </td>
                <td className="whitespace-nowrap px-3 py-2.5">
                  <DirectionTag direction={h.actual} />
                  <span className="ml-1.5 text-xs tabular-nums text-muted">{formatPct(h.movePct)}</span>
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums">
                  <span className="text-ink">{price(h.close)}</span>
                  <span className="block text-xs text-muted">from {price(h.prevClose)}</span>
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-right text-xs tabular-nums">
                  <span className="block text-up">↑ {price(h.high)} ({formatPct(h.highPct)})</span>
                  <span className="block text-down">↓ {price(h.low)} ({formatPct(h.lowPct)})</span>
                </td>
                <td className="whitespace-nowrap py-2.5 pl-3 text-right">
                  {h.hit === null ?
              <span className="inline-flex items-center gap-1 rounded-full bg-raised px-2 py-0.5 text-xs font-medium text-muted">
                      <MinusIcon className="h-3.5 w-3.5" aria-hidden="true" /> No move
                    </span> :
              h.hit ?
              <span className="inline-flex items-center gap-1 rounded-full bg-up/10 px-2 py-0.5 text-xs font-medium text-up">
                      <CheckIcon className="h-3.5 w-3.5" aria-hidden="true" /> Right
                    </span> :

              <span className="inline-flex items-center gap-1 rounded-full bg-down/10 px-2 py-0.5 text-xs font-medium text-down">
                      <XIcon className="h-3.5 w-3.5" aria-hidden="true" /> Wrong
                    </span>
              }
                </td>
              </tr>
          )}
          </tbody>
        </table>
      </div>
      }
      {history.length > 0 &&
      <p className="mt-2 text-xs leading-relaxed text-muted">
          Actual is the close against the close before it. Highest · lowest is how far the price went up and down during
          the candle, from that same close. A candle that closed unchanged is shown as no move and not counted.
        </p>
      }
    </section>);

}

function DirectionTag({ direction }: {direction: Direction | 'flat';}) {
  if (direction === 'flat') {
    return (
      <span className="inline-flex items-center gap-0.5 font-semibold text-muted">
        <ArrowRightIcon className="h-4 w-4" aria-hidden="true" />
        Flat
      </span>);

  }
  const up = direction === 'up';
  const Icon = up ? ArrowUpRightIcon : ArrowDownRightIcon;
  return (
    <span className={`inline-flex items-center gap-0.5 font-semibold ${up ? 'text-up' : 'text-down'}`}>
      <Icon className="h-4 w-4" aria-hidden="true" />
      {up ? 'Up' : 'Down'}
    </span>);

}
