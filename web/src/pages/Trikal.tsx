import React, { useState } from 'react';
import { EyeIcon } from 'lucide-react';
import { LessonDialog } from '../components/LessonDialog';
import { CallTag, Chance, DirectionTag, Empty, ErrorNote, PageTitle, Panel, ResultTag, callPct, signed, tone, PairTag } from '../components/Bits';
import { PipelinePanel, Scorecard } from '../components/ModelPanels';
import { Pagination, pageOf, usePageParam } from '../components/Pagination';
import { usePoll } from '../hooks/usePoll';
import { formatPct } from '../utils/format';
import { formatWhen } from '../utils/teacher';
import { fetchTrikal, formatSession, type PastCall, type TrikalCall, type TrikalView } from '../utils/trikal';

export function Trikal() {
  const { data: view, error } = usePoll(fetchTrikal, 60_000);
  const [lessonId, setLessonId] = useState<number | null>(null);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-8">
      <div className="flex min-w-0 flex-col gap-6">
        <PageTitle icon={EyeIcon} title="Trikal">
          Next-session call for every tracked stock and rupee pair. Drona's call comes first: the teacher weighs the chart, the
          overnight world, the news and Sanjay's and Chanakya's calls with everything it has learned. Without it, Sanjay's and
          Chanakya's calls are averaged.
        </PageTitle>
        {error && <ErrorNote>{error}</ErrorNote>}
        {view && <CallsSection view={view} onOpenLesson={setLessonId} />}
        {view && <PastSection past={view.past} />}
      </div>

      <aside className="flex flex-col gap-4 lg:sticky lg:top-8 lg:self-start">
        {view && <Scorecard rows={view.scorecard} />}
        {view && <PipelinePanel pipeline={view.pipeline} />}
      </aside>
      {lessonId !== null && <LessonDialog id={lessonId} onOpen={setLessonId} onClose={() => setLessonId(null)} />}
    </div>);

}

function CallsSection({ view, onOpenLesson }: {view: TrikalView;onOpenLesson: (id: number) => void;}) {
  const market = view.calls.find((c) => c.market_news !== null)?.market_news ?? null;
  return (
    <Panel
      id="calls-title"
      title={view.as_of ? `Call for the session after ${formatSession(view.as_of)}` : 'Next call'}
      aside={view.made_at &&
      <p className="text-xs text-muted">made {formatWhen(view.made_at)} · refreshed with news until 09:15, then frozen</p>
      }>

      {view.calls.length === 0 ?
      <Empty>
          No call yet. Trikal calls on weekdays from 06:00 IST, once Sanjay (after the previous close) and Chanakya (after the
          overnight markets close) have called. Keep start.bat running.
        </Empty> :

      <>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[600px] text-sm">
              <thead className="text-xs text-muted">
                <tr className="border-b border-line">
                  <th scope="col" className="py-2 pr-3 text-left font-medium">Symbol</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Now</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Trikal</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">If up / down</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">Drona</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">Sanjay</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">Chanakya</th>
                  <th scope="col" className="py-2 pl-3 text-right font-medium">News</th>
                </tr>
              </thead>
              <tbody>
                {view.calls.map((c) => <CallRow key={c.symbol} call={c} onOpenLesson={onOpenLesson} />)}
              </tbody>
            </table>
          </div>
          {view.drona &&
        <p className={`mt-3 rounded-lg px-3 py-2 text-[13px] ${view.drona.first ? 'bg-accent/10 text-ink' : 'bg-amber-400/10 text-amber-400'}`}>
              {view.drona.why}
            </p>
        }
          <p className="mt-3 text-xs leading-relaxed text-muted">
            Every call is for the whole session: will it close above or below the close it was made on. Now is the price
            right now (refreshed every 2 minutes while this page is open), with its change since that close. If up / down
            is where that close goes on a typical day's move (the median of the symbol's last 60 days; hover for the
            size): the models call only the direction, never how far, so treat these as a typical day's reach, not a
            target. Sanjay and Chanakya columns show their chance of closing up. On 2022–2026 days the models never saw, Trikal's
            confident calls were right 58.9% of the time; the others are close to a coin flip. For the INR pairs neither
            model has shown an edge yet (Sanjay 49%, Chanakya 47% on 2025–2026): treat those calls as experiments.
            {market !== null && <> Market-wide news today averages {signed(market)}.</>}{' '}
            {view.news_weight > 0 ?
          <>News counts: a stock's average news sentiment of +1 adds {Math.round(view.news_weight * 100)} points to its chance
                up (−1 takes them off), a weight Trikal proved on its own scored calls.</> :
          <>News is shown, not yet weighed: it gets weight once Trikal's scored calls show it helps.</>}
          </p>
        </>
      }
    </Panel>);

}

/** ₹ with 2 decimals for a share, 4 for a rupee pair (₹ per unit of the other currency). */
function money(value: number, market: string): string {
  const digits = market === 'forex' ? 4 : 2;
  return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

function CallRow({ call, onOpenLesson }: {call: TrikalCall;onOpenLesson: (id: number) => void;}) {
  const [open, setOpen] = useState(false);
  const d = call.drona_call;
  return (
    <>
    <tr className={open ? '' : 'border-b border-line/60 last:border-0'}>
      <td className="whitespace-nowrap py-2.5 pr-3 font-medium text-ink">{call.symbol}<PairTag market={call.market} /></td>
      <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums">
        {call.price == null ? '–' :
        <>
            <span className="text-ink">{money(call.price, call.market)}</span>
            {call.last_close != null &&
          <span className={`block text-xs ${tone(call.price - call.last_close)}`} title={`since the close of ${formatSession(call.as_of)}`}>
                {formatPct((call.price / call.last_close - 1) * 100)}
              </span>
          }
          </>
        }
      </td>
      <td className="whitespace-nowrap px-3 py-2.5">
        <CallTag p={call.prob_up} />
        {call.drona_first && <span className="mt-1 block text-[11px] font-medium text-accent">Drona first</span>}
      </td>
      <td
        className="whitespace-nowrap px-3 py-2.5 text-right text-xs tabular-nums"
        title={call.typical_move == null ? undefined : `±${(call.typical_move * 100).toFixed(2)}% on a typical day`}>

        {call.up_to == null || call.down_to == null ? '–' :
        <>
            <span className="block text-up">↑ {money(call.up_to, call.market)}</span>
            <span className="block text-down">↓ {money(call.down_to, call.market)}</span>
          </>
        }
      </td>
      <td className="whitespace-nowrap px-2 py-2.5 text-right">
        {d ?
        <button
          type="button"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          className="inline-flex flex-col items-end rounded-md px-1.5 py-0.5 hover:bg-raised">

            <Chance p={d.prob_up} />
            <span className="text-[11px] text-accent">{open ? 'Hide' : 'Why'}</span>
          </button> :
        <span className="text-xs text-muted" title="Drona calls each weekday from 06:00 IST">–</span>}
      </td>
      <td className="whitespace-nowrap px-2 py-2.5 text-right"><Chance p={call.sanjay} /></td>
      <td className="whitespace-nowrap px-2 py-2.5 text-right"><Chance p={call.chanakya} /></td>
      <td className="whitespace-nowrap py-2.5 pl-3 text-right text-xs text-muted">
        {call.news_n ?
        <>
            {call.news_n} {call.news_n === 1 ? 'note' : 'notes'}
            <span className={`block ${tone(call.news_mean)}`}>{call.news_mean === null ? '–' : signed(call.news_mean)}</span>
          </> :
        '–'}
      </td>
    </tr>
    {open && d &&
      <tr className="border-b border-line/60 last:border-0">
        <td colSpan={8} className="pb-4 pt-1">
          <div className="rounded-lg bg-raised/50 p-3 text-[13px] leading-relaxed">
            <p className="text-muted">
              Drona: <span className="font-semibold text-ink">{callPct(d.prob_up)}% {d.prob_up >= 0.5 ? 'up' : 'down'}</span>
              {d.confidence && <> · {d.confidence} confidence</>} · written by {d.writer} · {formatWhen(d.made_at)}
            </p>
            {d.reasons.length > 0 &&
            <>
                <h4 className="mt-2 font-medium text-ink">Why</h4>
                <ul className="mt-1 list-disc pl-5 text-ink/90">{d.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              </>
            }
            {d.risks.length > 0 &&
            <>
                <h4 className="mt-2 font-medium text-ink">What would prove it wrong</h4>
                <ul className="mt-1 list-disc pl-5 text-ink/90">{d.risks.map((r) => <li key={r}>{r}</li>)}</ul>
              </>
            }
            {d.lessons.length > 0 &&
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <span className="text-muted">Lessons it used:</span>
                {d.lessons.map((l) =>
              <button
                key={l.id}
                type="button"
                onClick={() => onOpenLesson(l.id)}
                className="rounded-md border border-line px-2 py-0.5 text-xs text-ink hover:border-accent hover:text-accent">

                    {l.title}
                  </button>
              )}
              </div>
            }
          </div>
        </td>
      </tr>
      }
    </>);

}

function PastSection({ past }: {past: PastCall[];}) {
  const [page, setPage] = usePageParam('past');
  const view = pageOf(past, page);
  const scored = past.filter((p) => p.hit !== null);
  const hits = scored.filter((p) => p.hit === 1).length;
  return (
    <Panel
      id="past-title"
      title="Trikal's past calls"
      aside={scored.length > 0 &&
      <p className="text-[13px] text-muted">
            <span className="font-semibold tabular-nums text-ink">{hits} of {scored.length}</span> right
          </p>
      }>

      {past.length === 0 ?
      <Empty>Each call appears here as right or wrong once Chitragupta scores it, after its session closes (4 PM IST).</Empty> :

      <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[460px] text-sm">
            <thead className="text-xs text-muted">
              <tr className="border-b border-line">
                <th scope="col" className="py-2 pr-3 text-left font-medium">Session</th>
                <th scope="col" className="px-3 py-2 text-left font-medium">Stock</th>
                <th scope="col" className="px-3 py-2 text-left font-medium">Called</th>
                <th scope="col" className="px-3 py-2 text-left font-medium">Actual</th>
                <th scope="col" className="py-2 pl-3 text-right font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {view.rows.map((p) =>
            <tr key={`${p.session}-${p.symbol}`} className="border-b border-line/60 last:border-0">
                  <td className="whitespace-nowrap py-2.5 pr-3 tabular-nums text-ink">{formatSession(p.session)}</td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-ink">{p.symbol}</td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <DirectionTag up={p.prob_up >= 0.5} />
                    <span className="ml-1.5 text-xs tabular-nums text-muted">{callPct(p.prob_up)}%</span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <DirectionTag up={p.move > 0} />
                    <span className="ml-1.5 text-xs tabular-nums text-muted">{formatPct(p.move * 100)}</span>
                  </td>
                  <td className="whitespace-nowrap py-2.5 pl-3 text-right"><ResultTag hit={p.hit} /></td>
                </tr>
            )}
            </tbody>
          </table>
          <Pagination page={view.page} pages={view.pages} total={past.length} onPage={setPage} noun="scored calls" />
        </div>
      }
    </Panel>);

}
