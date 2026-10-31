import React from 'react';
import { GaugeIcon, ListChecksIcon, NewspaperIcon, ScaleIcon } from 'lucide-react';
import { DirectionTag, Empty, ErrorNote, MODEL_LABELS, PageTitle, Panel, ResultTag, rightTone, tone } from '../components/Bits';
import { Scorecard } from '../components/ModelPanels';
import { Pagination, pageOf, usePageParam } from '../components/Pagination';
import { usePoll } from '../hooks/usePoll';
import { formatPct } from '../utils/format';
import { eventLabel, fetchScores, type Scores as ScoresData } from '../utils/site';
import { formatSession } from '../utils/trikal';

export function Scores() {
  const { data, error } = usePoll(fetchScores, 5 * 60_000);

  return (
    <div className="flex flex-col gap-6">
      <PageTitle icon={ScaleIcon} title="Scores">
        Chitragupta scores every call against what the market did, after each session closes. Only prices decide a score.
      </PageTitle>
      {error && <ErrorNote>{error}</ErrorNote>}

      {data && (
      data.total === 0 ?
      <Empty>
            Nothing scored yet. Chitragupta scores each call after its session closes (4 PM IST), every hour while the server
            runs.
          </Empty> :

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-8">
            <div className="flex min-w-0 flex-col gap-6">
              <RecentCalls data={data} />
            </div>
            <aside className="flex flex-col gap-4">
              <Scorecard rows={data.models} />
              <ByEvent data={data} />
              <Calibration data={data} />
            </aside>
          </div>)
      }
    </div>);

}

function RecentCalls({ data }: {data: ScoresData;}) {
  const [page, setPage] = usePageParam('page');
  const view = pageOf(data.recent, page);
  return (
    <Panel id="recent-title" icon={ListChecksIcon} title="Latest scored calls" aside={<p className="text-xs text-muted">{data.total.toLocaleString()} scored in all</p>}>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="text-xs text-muted">
            <tr className="border-b border-line">
              <th scope="col" className="py-2 pr-3 text-left font-medium">Session</th>
              <th scope="col" className="px-3 py-2 text-left font-medium">Model</th>
              <th scope="col" className="px-3 py-2 text-left font-medium">Stock</th>
              <th scope="col" className="px-3 py-2 text-left font-medium">Called</th>
              <th scope="col" className="px-3 py-2 text-left font-medium">Judged on</th>
              <th scope="col" className="py-2 pl-3 text-right font-medium">Result</th>
            </tr>
          </thead>
          <tbody>
            {view.rows.map((c, i) =>
            <tr key={`${c.model}-${c.symbol}-${c.session}-${i}`} className="border-b border-line/60 align-top last:border-0" title={c.title ?? undefined}>
                <td className="whitespace-nowrap py-2.5 pr-3 tabular-nums text-ink">{formatSession(c.session)}</td>
                <td className="whitespace-nowrap px-3 py-2.5 text-muted">{(MODEL_LABELS[c.model] ?? c.model).split(' · ')[0]}</td>
                <td className="whitespace-nowrap px-3 py-2.5 text-ink">{c.symbol}</td>
                <td className="whitespace-nowrap px-3 py-2.5">
                  {c.said === 0 ? <span className="text-muted">neutral</span> : <DirectionTag up={c.said > 0} />}
                  <span className="ml-1.5 text-xs tabular-nums text-muted">{c.said > 0 ? '+' : ''}{c.said.toFixed(2)}</span>
                </td>
                <td className={`whitespace-nowrap px-3 py-2.5 tabular-nums ${tone(c.outcome)}`}>{formatPct(c.outcome * 100)}</td>
                <td className="whitespace-nowrap py-2.5 pl-3 text-right"><ResultTag hit={c.hit} /></td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <Pagination page={view.page} pages={view.pages} total={data.recent.length} onPage={setPage} noun="latest calls" />
      <p className="mt-3 text-xs leading-relaxed text-muted">
        News calls (Narad, Drona) are judged on the stock's move beyond Nifty that session; Sanjay, Chanakya and Trikal on its
        plain move. Neutral news calls are recorded but not scored for direction. Hover a row to see the news headline.
      </p>
    </Panel>);

}

function ByEvent({ data }: {data: ScoresData;}) {
  return (
    <Panel id="event-title" icon={NewspaperIcon} title="News calls by kind">
      {data.events.length === 0 ?
      <p className="mt-3 text-sm text-muted">No news call scored yet.</p> :

      <table className="mt-3 w-full text-sm">
          <thead className="text-xs text-muted">
            <tr className="border-b border-line">
              <th scope="col" className="py-1.5 pr-2 text-left font-medium">Kind</th>
              <th scope="col" className="px-2 py-1.5 text-right font-medium">Calls</th>
              <th scope="col" className="py-1.5 pl-2 text-right font-medium">Right</th>
            </tr>
          </thead>
          <tbody>
            {data.events.map((e) =>
          <tr key={`${e.model}-${e.event}`} className="border-b border-line/60 last:border-0">
                <td className="py-2 pr-2 text-ink">
                  {eventLabel(e.event)} <span className="text-xs text-muted">· {e.model === 'drona' ? 'Drona' : 'Narad'}</span>
                </td>
                <td className="px-2 py-2 text-right tabular-nums text-muted">{e.calls}</td>
                <td className={`py-2 pl-2 text-right font-semibold tabular-nums ${rightTone(e.right_pct)}`}>
                  {e.right_pct === null ? '–' : `${e.right_pct}%`}
                </td>
              </tr>
          )}
          </tbody>
        </table>
      }
      <p className="mt-3 text-xs leading-relaxed text-muted">
        Once Narad is right on fewer than 52% of 40 or more calls of one kind, its notes of that kind go to Drona.
      </p>
    </Panel>);

}

function Calibration({ data }: {data: ScoresData;}) {
  return (
    <Panel id="calibration-title" icon={GaugeIcon} title="Is Narad's confidence honest?">
      {data.calibration.length === 0 ?
      <p className="mt-3 text-sm text-muted">No news call scored yet.</p> :

      <table className="mt-3 w-full text-sm">
          <thead className="text-xs text-muted">
            <tr className="border-b border-line">
              <th scope="col" className="py-1.5 pr-2 text-left font-medium">Narad's confidence</th>
              <th scope="col" className="px-2 py-1.5 text-right font-medium">Calls</th>
              <th scope="col" className="py-1.5 pl-2 text-right font-medium">Right</th>
            </tr>
          </thead>
          <tbody>
            {data.calibration.map((b) =>
          <tr key={b.band} className="border-b border-line/60 last:border-0">
                <td className="py-2 pr-2 text-ink">{b.band}</td>
                <td className="px-2 py-2 text-right tabular-nums text-muted">{b.calls}</td>
                <td className={`py-2 pl-2 text-right font-semibold tabular-nums ${rightTone(b.right_pct)}`}>
                  {b.right_pct === null ? '–' : `${b.right_pct}%`}
                </td>
              </tr>
          )}
          </tbody>
        </table>
      }
      <p className="mt-3 text-xs leading-relaxed text-muted">
        If higher confidence isn't right more often, Narad's own number can't be trusted. That's why its help requests also go
        by this record, not only by what it says about itself.
      </p>
    </Panel>);

}
