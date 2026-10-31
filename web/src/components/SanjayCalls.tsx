import React from 'react';
import { CandlestickChartIcon } from 'lucide-react';
import { usePoll } from '../hooks/usePoll';
import type { Market } from '../types/market';
import { fetchSanjay } from '../utils/site';
import { formatWhen } from '../utils/teacher';
import { formatSession } from '../utils/trikal';
import { CallTag, Empty, Panel } from './Bits';

/** Sanjay's daily call on every tracked stock or rupee pair for the next session; a click opens its chart. */
export function SanjayCalls({ market, onSelect }: {market: Market;onSelect: (symbol: string) => void;}) {
  const { data, error } = usePoll((signal) => fetchSanjay(market, signal), 5 * 60_000, [market]);
  const forex = market === 'forex';

  return (
    <Panel
      id="sanjay-title"
      icon={CandlestickChartIcon}
      title={data?.as_of ? `Sanjay's call for the session after ${formatSession(data.as_of)}` : "Sanjay's daily call"}
      aside={data?.made_at && <p className="text-xs text-muted">made {formatWhen(data.made_at)}</p>}
      className="mt-10">

      {error && <p className="mt-3 text-sm text-down">{error}</p>}
      {data && (
      data.calls.length === 0 ?
      <Empty>
          No call yet. Sanjay calls {forex ? "each morning once a pair's day is final (06:00 IST)" : 'after each 4 PM close'}, while the
          server runs.
        </Empty> :

      <>
            <div className="mt-2 grid gap-x-8 sm:grid-cols-2 lg:grid-cols-3">
              {data.calls.map((c) =>
          <button
            key={c.symbol}
            type="button"
            onClick={() => onSelect(c.symbol)}
            className="flex items-center justify-between gap-3 border-b border-line/60 py-2.5 text-left text-sm hover:bg-raised/40">

                  <span className="font-medium text-ink">{c.symbol}</span>
                  <CallTag p={c.prob_up} />
                </button>
          )}
            </div>
            <p className="mt-3 text-xs leading-relaxed text-muted">
              Chance of closing above {forex ? "the last day's close on the next day (a pair's day ends 03:30 IST)" : "today's close in the next session"}, from the daily chart model.
              {data.accuracy !== null &&
          <>
                  {' '}Tested on days it never saw: right {data.accuracy}% of the time
                  {data.confident_accuracy !== null && <>, {data.confident_accuracy}% on its confident calls</>}.
                </>
          }{' '}
              Trikal averages it with Chanakya's overnight call from 06:00 IST. Click a {forex ? 'pair' : 'stock'} to open its chart.
              {forex && <> The pairs' daily models show no edge yet: treat these calls as experiments.</>}
            </p>
          </>)
      }
    </Panel>);

}
