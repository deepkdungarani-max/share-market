import React from 'react';
import { GlobeIcon } from 'lucide-react';
import { CallTag, Empty, ErrorNote, PageTitle, Panel, tone, PairTag } from '../components/Bits';
import { usePoll } from '../hooks/usePoll';
import { formatPct } from '../utils/format';
import { fetchWorld } from '../utils/site';
import { formatWhen } from '../utils/teacher';
import { formatSession } from '../utils/trikal';

/** The overnight series Chanakya reads, in the order a trader would scan them. */
const CUES = [
{ key: 'sp500', label: 'S&P 500', note: 'US large caps, last US session' },
{ key: 'nasdaq', label: 'Nasdaq', note: 'US tech, moves Indian IT' },
{ key: 'brent', label: 'Brent crude', note: 'Cheaper oil usually helps India' },
{ key: 'usdinr', label: 'Dollar–rupee', note: 'Up means a weaker rupee' },
{ key: 'us10y', label: 'US 10-year yield', note: 'Change in the yield' },
{ key: 'gold', label: 'Gold', note: 'Safe-haven demand' },
{ key: 'dollar', label: 'Dollar index', note: 'Dollar against major currencies' },
{ key: 'indiavix', label: 'India VIX', note: 'Fear gauge, previous session' }];


export function World() {
  const { data, error } = usePoll(fetchWorld, 5 * 60_000);

  return (
    <div className="flex flex-col gap-6">
      <PageTitle icon={GlobeIcon} title="World">
        Chanakya reads the overnight moves of the world's markets before each Indian session and calls every tracked stock.
      </PageTitle>
      {error && <ErrorNote>{error}</ErrorNote>}

      {data && (
      data.calls.length === 0 ?
      <Empty>
            No call yet. Chanakya calls on weekdays from 06:00 IST, once the US session, the rupee's day and Brent have closed.
            Keep start.bat running.
          </Empty> :

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start lg:gap-8">
            <Panel
          id="cues-title"
          title={`What moved overnight, before the session after ${formatSession(data.as_of!)}`}
          aside={data.made_at && <p className="text-xs text-muted">read {formatWhen(data.made_at)}</p>}>

              <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                {CUES.map((c) => {
              const v = data.cues[`${c.key}_ret`];
              return (
                <div key={c.key} className="flex items-start justify-between gap-3 rounded-lg bg-raised/60 px-3 py-2.5">
                      <div className="min-w-0">
                        <dt className="text-sm font-medium text-ink">
                          {c.label} <span className="text-xs font-normal text-muted">{data.tickers[c.key]}</span>
                        </dt>
                        <p className="text-xs text-muted">{c.note}</p>
                      </div>
                      <dd className="text-right">
                        <span className={`text-[15px] font-semibold tabular-nums ${tone(v ?? null)}`}>
                          {v === undefined ? '–' : formatPct(v * 100)}
                        </span>
                        {c.key === 'indiavix' && data.cues.indiavix_level !== undefined &&
                    <span className="block text-xs tabular-nums text-muted">level {data.cues.indiavix_level.toFixed(1)}</span>
                    }
                      </dd>
                    </div>);

            })}
              </dl>
              <p className="mt-3 text-xs leading-relaxed text-muted">
                Only moves dated before the session count: the US closes at 01:30–02:30 IST and the rupee's day at 05:30 IST.
                On every session from 2017 to 2026, judged by models that never saw them, Chanakya was right 53.5% of the time
                (55.3% on its confident calls); the chart alone (Sanjay) managed 51.2%.
              </p>
            </Panel>

            <Panel id="world-calls-title" title="Chanakya's call">
              <table className="mt-3 w-full text-sm">
                <thead className="text-xs text-muted">
                  <tr className="border-b border-line">
                    <th scope="col" className="py-2 pr-3 text-left font-medium">Stock</th>
                    <th scope="col" className="py-2 pl-3 text-right font-medium">Call</th>
                  </tr>
                </thead>
                <tbody>
                  {data.calls.map((c) =>
              <tr key={c.symbol} className="border-b border-line/60 last:border-0">
                      <td className="py-2.5 pr-3 font-medium text-ink">{c.symbol}<PairTag market={c.market} /></td>
                      <td className="py-2.5 pl-3 text-right"><CallTag p={c.prob_up} /></td>
                    </tr>
              )}
                </tbody>
              </table>
              {data.trained_on &&
          <p className="mt-3 text-xs text-muted">Trained this morning on {data.trained_on.toLocaleString()} past stock-sessions.</p>
          }
            </Panel>
          </div>)
      }
    </div>);

}
