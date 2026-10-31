import React, { useEffect, useState } from 'react';
import {
  ArrowLeftIcon,
  FileTextIcon,
  CircleCheckIcon,
  CircleIcon,
  CircleXIcon,
  FlaskConicalIcon,
  LoaderCircleIcon,
  PauseIcon,
  PlayIcon,
  SearchIcon } from
'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { CallTag, Empty, ErrorNote, PageTitle, Panel, ResultTag, rightTone, tone } from '../components/Bits';
import { Pagination, pageOf, usePageParam } from '../components/Pagination';
import { DatePicker, daysAgo } from '../components/DatePicker';
import { usePoll } from '../hooks/usePoll';
import {
  FEATURE_LABELS,
  fetchBacktest,
  fetchBacktestCompanies,
  fetchBacktestCompany,
  fetchBacktestDay,
  fullDay,
  monthLabel,
  movePct,
  pauseBacktest,
  resumeBacktest,
  rupees,
  setBacktestAuto,
  startBacktest,
  type AutoStep,
  type BacktestCall,
  type BacktestDay,
  type BacktestView,
  type CompanySort,
  type DayShow,
  type DaySort,
  type HistorySpan,
  type Metrics,
  type Progress,
  type Report,
  type ReportDay,
  type ReportGroup,
  type ReportMiss,
  type Retrain,
  type Run,
  type RunStatus,
  type StageStatus } from
'../utils/backtest';

/** The one-year backtest: trained on every NSE session before a cutoff, it calls every company's next session,
 *  every day after it. The latest run's steps and data, every run, the results, then every day's and every
 *  company's calls, 20 a page. */
export function Backtest() {
  const [params] = useSearchParams();
  const runId = Number(params.get('run')) || null;
  const [version, setVersion] = useState(0);
  const { data, error } = usePoll((signal) => fetchBacktest(runId, signal), 5_000, [runId, version]);

  return (
    <div className="flex flex-col gap-5">
      <PageTitle icon={FlaskConicalIcon} title="Backtest">
        A year the model never saw. It learns from every NSE session before the cutoff, back to 1994, then calls every
        company's next session, every day after it, and each call is checked against what really happened.
      </PageTitle>
      {error && <ErrorNote>{error}</ErrorNote>}
      {data && <RunPanel data={data} onChanged={() => setVersion((v) => v + 1)} />}
      {data && data.runs.length > 0 && <History data={data} />}
      {data?.run &&
      <>
          <Results run={data.run} />
          {data.run.report && <ReportPanel run={data.run} report={data.run.report} />}
          <Browse run={data.run} days={data.days} />
        </>
      }
    </div>);

}

const pct = (v: number | null | undefined, digits = 1) => v == null ? '–' : `${v.toFixed(digits)}%`;
const signedPct = (v: number | null | undefined, digits = 2) => v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(digits)}%`;
const auc = (v: number | null | undefined) => v == null ? '–' : v.toFixed(3);
const price = (v: number | null) => v == null ? '–' : v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (n: number | null | undefined) => n == null ? '–' : n.toLocaleString();
/** Bytes as "3.7 GB" or "78 MB". */
const size = (b: number | null | undefined) => b == null ? '–' : b >= 1e9 ? `${(b / 1e9).toFixed(1)} GB` : `${Math.max(1, Math.round(b / 1e6))} MB`;
const clock = (iso: string) => new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
const when = (iso: string) => new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

/** "45 s", "6 min 24 s", "25 min", "1 h 5 min" */
function duration(seconds: number | null | undefined): string {
  if (seconds == null) return '–';
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 10 && s % 60) return `${m} min ${s % 60} s`;
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

/** The latest run: what it is doing, its steps with their times, the time left, how much data it moved, and the
 *  Run / Pause / Continue buttons. */
function RunPanel({ data, onChanged }: {data: BacktestView;onChanged: () => void;}) {
  const suggested = data.next_cutoff && data.next_cutoff <= daysAgo(30) ? data.next_cutoff : '';
  const [cutoff, setCutoff] = useState(suggested);
  const [picked, setPicked] = useState(false);
  useEffect(() => {
    if (!picked) setCutoff(suggested);
  }, [suggested, picked]);
  const [retrain, setRetrain] = useState<Retrain>('once');
  const [history, setHistory] = useState<HistorySpan>('all');
  const [busy, setBusy] = useState(false);
  const latest = data.runs[0];
  const running = data.running && latest?.status === 'running';
  const progress = data.progress;
  const paused = running && !!progress?.paused_since;
  const typical = data.runs.find((r) => r.status === 'done' && (r.retrain ?? 'once') === retrain && (r.history ?? 'all') === history)?.seconds;

  const act = async (what: 'run' | 'pause' | 'resume') => {
    setBusy(true);
    try {
      if (what === 'run') {
        const r = await startBacktest(cutoff || null, retrain, history);
        toast.success(r.started ? `Backtest started${typical ? `: about ${duration(typical)}` : ''}` : 'A backtest is already running');
      } else if (what === 'pause') {
        const r = await pauseBacktest();
        if (r.done) toast.success('Paused: it keeps its place until you continue');else
        toast.error('Nothing to pause');
      } else {
        const r = await resumeBacktest();
        if (r.done) toast.success('Continuing from where it stopped');else
        toast.error('Nothing was paused');
      }
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'The backend did not answer');
    } finally {
      setBusy(false);
    }
  };
  const button = 'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold disabled:opacity-50';

  return (
    <Panel
      id="backtest-run"
      title={!latest ? 'No run yet' : running ? `Run #${latest.id} ${paused ? 'is paused' : 'is running'}` : `Last run: #${latest.id}`}
      aside={
      <div className="flex flex-wrap items-center gap-2">
          {running ?
        <button
          type="button"
          onClick={() => act(paused ? 'resume' : 'pause')}
          disabled={busy}
          className={`${button} ${paused ? 'bg-accent text-canvas hover:opacity-90' : 'border border-line text-ink hover:bg-raised'}`}>

              {paused ? <PlayIcon className="h-3.5 w-3.5" aria-hidden="true" /> : <PauseIcon className="h-3.5 w-3.5" aria-hidden="true" />}
              {paused ? 'Continue' : 'Pause'}
            </button> :

        <>
              <span className="text-xs text-muted">Cutoff</span>
              <DatePicker
            value={cutoff}
            onChange={(v) => {setPicked(true);setCutoff(v);}}
            min="1998-01-01"
            max={daysAgo(30)}
            placeholder="A year back (default)"
            describedBy="cutoff-hint"
            presets={[1, 2, 3, 5].map((y) => ({ label: `${y} ${y === 1 ? 'year' : 'years'} back`, value: daysAgo(0, y) }))} />
              <Select<Retrain>
            label="Retrain"
            value={retrain}
            onChange={setRetrain}
            options={[['once', 'Once'], ['quarter', 'Every quarter'], ['month', 'Every month']]} />
              <Select<HistorySpan>
            label="Learn from"
            value={history}
            onChange={setHistory}
            options={[['all', 'All since 1994'], ['10y', 'Last 10 years'], ['5y', 'Last 5 years']]} />
              <button type="button" onClick={() => act('run')} disabled={busy} className={`${button} bg-accent text-canvas hover:opacity-90`}>
                <PlayIcon className="h-3.5 w-3.5" aria-hidden="true" />
                {latest ? 'Run again' : 'Run'}
              </button>
            </>
        }
        </div>
      }>

      {latest &&
      <p className="mt-1 text-sm text-muted">
          Cutoff {latest.cutoff ? fullDay(latest.cutoff) : 'a year before the last session'} · started {when(latest.started_at)} ·{' '}
          {running ? `working ${duration(latest.seconds)} so far` : latest.seconds != null ? `worked ${duration(latest.seconds)}` : 'time not known'}
        </p>
      }
      <AutoRunControls data={data} retrain={retrain} history={history} onChanged={onChanged} />
      {running && progress?.seconds_left != null && (
      paused ?
      <p className="mt-2 text-sm font-semibold text-amber-400">
            Paused since {clock(progress.paused_since!)} · about {duration(progress.seconds_left)} of work left once you continue
            <span className="block text-xs font-normal text-muted">
              While paused it keeps its place and its memory, and the laptop stays awake. Continue picks up from the same spot.
            </span>
          </p> :

      <p className="mt-2 text-sm font-semibold text-ink">
            About {duration(progress.seconds_left)} left · finishes around{' '}
            {new Date(Date.now() + progress.seconds_left * 1000).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
            <span className="block text-xs font-normal text-muted">Each step still to come is timed by what it took in the last finished run.</span>
          </p>)
      }
      {latest?.status === 'failed' && <p className="mt-2 text-sm text-down">It failed: {latest.step}</p>}
      {latest?.status === 'stopped' &&
      <p className="mt-2 text-sm text-amber-400">
          It stopped before it finished (its process was closed) during: {latest.step}. Its calls weren't saved, so run it again.
        </p>
      }
      {progress && <Stages progress={progress} running={running} />}
      <DataFacts data={data} />
      {!running &&
      <p id="cutoff-hint" className="mt-3 text-xs text-muted">
          Leave the cutoff empty for a year before the last session. A run copies market.db to the laptop's SSD, builds
          the features for every company since 1994, trains, then calls every session after the cutoff
          {typical ? `: about ${duration(typical)}` : ''}. Retrain every quarter or month to train a fresh model on
          everything before each stretch of the year, the way the live model keeps learning: each extra model adds
          about 4 min. Learn from the last 10 or 5 years to train only on recent markets, and compare it with all
          history on the same cutoff.
        </p>
      }
    </Panel>);

}

const STAGE_LOOK: Record<StageStatus, [typeof CircleIcon, string]> = {
  done: [CircleCheckIcon, 'text-up'],
  running: [LoaderCircleIcon, 'animate-spin text-accent'],
  paused: [PauseIcon, 'text-amber-400'],
  stopped: [CircleXIcon, 'text-amber-400'],
  waiting: [CircleIcon, 'text-muted/60']
};

/** The run's steps in order: done with the time each took, the one working now, and those still to come. */
function Stages({ progress, running }: {progress: Progress;running: boolean;}) {
  return (
    <ol className="mt-4 flex flex-col gap-2.5" aria-label="Steps of the run">
      {progress.stages.map((s, i) => {
        const [Icon, look] = STAGE_LOOK[s.status];
        const time =
        s.status === 'done' ? duration(s.seconds) :
        s.status === 'running' ? `${duration(s.seconds)} so far · usually ${duration(s.usually)}` :
        s.status === 'paused' ? `paused after ${duration(s.seconds)}` :
        s.status === 'stopped' ? 'stopped here' :
        running ? `about ${duration(s.usually)}` : 'not reached';
        return (
          <li key={s.key} className="grid grid-cols-[16px_minmax(0,1fr)] gap-x-2.5 text-sm sm:grid-cols-[16px_minmax(0,1fr)_auto]">
            <Icon className={`mt-0.5 h-4 w-4 ${look}`} aria-hidden="true" />
            <div className="min-w-0">
              <p className={s.status === 'waiting' ? 'text-muted' : 'text-ink'}>
                {i + 1}. {s.label}<span className="sr-only"> ({s.status})</span>
              </p>
              {s.detail && <p className="text-xs text-muted">{s.detail}</p>}
            </div>
            <p className={`col-start-2 text-xs tabular-nums sm:col-start-auto sm:text-right ${s.status === 'running' ? 'text-accent' : 'text-muted'}`}>{time}</p>
          </li>);

      })}
    </ol>);

}

/** How much data the latest run read, copied, trained on, made and saved. */
function DataFacts({ data }: {data: BacktestView;}) {
  const f = data.progress?.facts ?? {};
  const files = data.files;
  const load = data.progress?.stages.find((s) => s.key === 'load');
  const copying = load?.status === 'running' && files.snapshot != null;
  const saved = data.run && data.run.id === data.runs[0]?.id ? data.run.saved : undefined;
  const items: [string, string, string][] = [
  ['Read from E:', size(files.market_db), 'market.db on the USB disk: the NSE bhavcopy since 1994 and the Yahoo bars'],
  ['Copied to the SSD', copying ? `${size(files.snapshot)} of ${size(files.market_db)}` : load?.status === 'done' ? size(files.market_db) : '–',
  copying ? 'copying now, in one sweep of the disk' : 'a temporary copy, deleted once the rows are read'],
  ['Loaded', f.rows ? `${num(f.rows)} rows` : '–', f.companies ? `${num(f.companies)} companies, one row per company per session` : 'one row per company per session'],
  ['Trained on', f.train_rows ? `${num(f.train_rows)} rows` : f.fit_rows ? `${num(f.fit_rows)} rows` : '–',
  f.rounds ? `${f.rounds} rounds${f.models && f.models > 1 ? ` × ${f.models} models, retrained through the year` : ''}, picked on ${num(f.check_rows)} rows of the year before the cutoff` : 'every session before the cutoff'],
  ['Calls made', f.calls ? num(f.calls) : '–', 'every company that traded, every session of the test year'],
  ['Saved in backtest.db', size(files.backtest_db), saved ? `${num(saved.predictions)} calls, ${saved.days} days and ${num(saved.companies)} companies` : 'on E:, read by this page']];

  return (
    <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {items.map(([label, value, note]) =>
      <div key={label} className="rounded-lg bg-raised/50 p-3">
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</dt>
          <dd className="mt-1 text-lg font-semibold tabular-nums text-ink">{value}</dd>
          <dd className="mt-0.5 text-xs text-muted">{note}</dd>
        </div>
      )}
    </dl>);

}

const STATUS_LOOK: Record<RunStatus, [string, string]> = {
  done: ['Done', 'bg-up/10 text-up'],
  running: ['Running', 'bg-accent/15 text-accent'],
  failed: ['Failed', 'bg-down/10 text-down'],
  stopped: ['Stopped', 'bg-amber-400/10 text-amber-400']
};

/** Every run, newest first; a finished one can be shown below. */
function History({ data }: {data: BacktestView;}) {
  const [, setParams] = useSearchParams();
  const latestDone = data.runs.find((r) => r.status === 'done');

  return (
    <Panel id="backtest-history" title="Every run">
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm tabular-nums">
          <thead className="text-xs text-muted">
            <tr className="border-b border-line">
              <th scope="col" className="py-2 pr-3 text-left font-medium">Run</th>
              <th scope="col" className="px-3 py-2 text-left font-medium">Started</th>
              <th scope="col" className="px-3 py-2 text-left font-medium">Cutoff</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Worked</th>
              <th scope="col" className="px-3 py-2 text-left font-medium">Status</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Right</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">AUC</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Calls</th>
              <th scope="col" className="py-2 pl-3"><span className="sr-only">Show</span></th>
            </tr>
          </thead>
          <tbody>
            {data.runs.map((r) => {
              const [label, look] = STATUS_LOOK[r.status];
              return (
                <tr key={r.id} className="border-b border-line/60 last:border-0">
                  <td className="py-2.5 pr-3 font-medium text-ink">#{r.id}</td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-muted">{when(r.started_at)}</td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-muted">
                    {r.cutoff ? fullDay(r.cutoff) : '–'}
                    {r.retrain && r.retrain !== 'once' &&
                    <span className="block text-xs">retrained every {r.retrain} · {r.models} models</span>
                    }
                    {r.history && r.history !== 'all' &&
                    <span className="block text-xs">learned the last {r.history === '10y' ? 10 : 5} years</span>
                    }
                  </td>
                  <td className="px-3 py-2.5 text-right text-muted">{duration(r.seconds)}</td>
                  <td className="px-3 py-2.5">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${look}`}>{label}</span>
                    {(r.status === 'stopped' || r.status === 'failed') && r.step &&
                    <span className="mt-1 block max-w-[260px] text-xs text-muted">{r.status === 'stopped' ? `during: ${r.step}` : r.step}</span>
                    }
                  </td>
                  <td className={`px-3 py-2.5 text-right ${rightTone(r.right_pct)}`}>{pct(r.right_pct, 2)}</td>
                  <td className="px-3 py-2.5 text-right text-muted">{auc(r.auc)}</td>
                  <td className="px-3 py-2.5 text-right text-muted">{num(r.calls)}</td>
                  <td className="py-2.5 pl-3 text-right">
                    {r.status === 'done' && (
                    data.run?.id === r.id ?
                    <span className="text-xs text-muted">Shown below</span> :

                    <button
                      type="button"
                      onClick={() => setParams(r.id === latestDone?.id ? {} : { run: String(r.id) })}
                      className="text-xs font-medium text-accent hover:underline">

                          Show
                        </button>)
                    }
                  </td>
                </tr>);

            })}
          </tbody>
        </table>
      </div>
    </Panel>);

}

/** In plain words: is there an edge, and where. */
function verdict(m: Metrics): string {
  const usual = m.train_up_pct >= 50 ? 'up' : 'down';
  const beat = m.right_pct - m.always_pct;
  const head = `Right on ${m.right_pct}% of calls, against ${m.always_pct}% for always calling "${usual}" (stocks closed up ${m.up_pct}% of the time): ${Math.abs(beat).toFixed(1)} points ${beat >= 0 ? 'better' : 'worse'}.`;
  if ((m.auc ?? 0.5) < 0.505) return `${head} Its ranking is no better than chance, so it has no real skill on this year.`;
  const l = m.liquid;
  const lAuc = l.auc ?? 0.5;
  if (lAuc < 0.505) {
    return `${head} The edge sits in small, thinly traded stocks: on stocks that trade ₹5 crore or more a day it is no better than chance, and in thin stocks the gap between buying and selling prices eats a one-day edge.`;
  }
  const always = l.up_pct == null ? null : Math.max(l.up_pct, 100 - l.up_pct);
  const direction = always == null || l.right_pct == null ? '' :
  ` On stocks that trade ₹5 crore or more a day its up/down calls were right ${l.right_pct}%, against ${always.toFixed(2)}% for always calling the usual way, so on direction alone the edge there is small.`;
  const p = m.picks;
  let picks = '';
  if (p && p.top_avg_pct != null && p.liquid_avg_pct != null && p.bottom_avg_pct != null) {
    picks = ` Its top ${p.top} buyable picks each day moved ${signedPct(p.top_avg_pct, 3)} the next day against ${signedPct(p.liquid_avg_pct, 3)} for all of them`;
    if (p.top_year_after_cost_pct != null) picks += `, which the taxes and charges of trading every day ${p.top_year_after_cost_pct < 0 ? 'more than eat' : "don't fully eat"}`;
    picks += '.';
    if (p.bottom_avg_pct < p.liquid_avg_pct - 0.1) {
      picks += ` Its bottom ${p.top} fell ${signedPct(p.bottom_avg_pct, 3)} a day, so it is better at saying what to avoid than what to buy.`;
    }
  }
  return `${head}${direction} It ranks those stocks a little better than chance (AUC ${auc(lAuc)}).${picks}`;
}

function Card({ label, value, valueTone = 'text-ink', children }: {label: string;value: string;valueTone?: string;children: React.ReactNode;}) {
  return (
    <div className="rounded-lg bg-raised/50 p-3">
      <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</dt>
      <dd className={`mt-1 text-xl font-semibold tabular-nums ${valueTone}`}>{value}</dd>
      <dd className="mt-1 text-xs leading-relaxed text-muted">{children}</dd>
    </div>);

}

function Results({ run }: {run: Run;}) {
  const m = run.metrics;
  const p = m.picks;
  const usual = m.train_up_pct >= 50 ? 'up' : 'down';

  return (
    <>
      <Panel
        id="backtest-results"
        title={`One year from ${fullDay(run.cutoff)}: ${m.calls.toLocaleString()} calls on ${m.companies.toLocaleString()} companies over ${m.sessions} sessions`}>

        <p className="mt-2 text-sm leading-relaxed text-ink/90">{verdict(m)}</p>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Card label="Right" value={pct(m.right_pct, 2)} valueTone={rightTone(m.right_pct)}>
            A coin toss gets 50%; always calling "{usual}" got {pct(m.always_pct, 2)}. Stocks closed up {pct(m.up_pct)} of the time.
          </Card>
          <Card label="Ranking skill (AUC)" value={auc(m.auc)}>
            0.500 is a coin toss. Day by day it averaged {auc(m.daily_auc)}. For one-day stock moves, 0.52 or more is a usable edge.
          </Card>
          <Card label="Confident calls" value={pct(m.confident.right_pct, 2)} valueTone={rightTone(m.confident.right_pct)}>
            {m.confident.calls.toLocaleString()} calls at 55% or more either way ({pct((100 * m.confident.calls) / m.calls)} of all).
          </Card>
          <Card label="Stocks trading ₹5 crore+ a day" value={pct(m.liquid.right_pct, 2)} valueTone={rightTone(m.liquid.right_pct)}>
            {m.liquid.calls.toLocaleString()} calls
            {m.liquid.up_pct != null && <> · always calling the usual way got {pct(Math.max(m.liquid.up_pct, 100 - m.liquid.up_pct), 2)}</>}
            {' '}· AUC {auc(m.liquid.auc)} · confident ones right {pct(m.liquid.confident_right_pct)} of {m.liquid.confident_calls.toLocaleString()}.
          </Card>
          {p &&
          <Card label={`Its top ${p.top} buyable picks each day`} value={signedPct(p.top_avg_pct, 3)} valueTone={tone(p.top_avg_pct)}>
              Average next-day move, against {signedPct(p.liquid_avg_pct, 3)} for all stocks trading ₹5 crore+ and {signedPct(p.bottom_avg_pct, 3)} for its bottom {p.top}. Ahead of them on {pct(p.top_beat_days_pct)} of days.
              {p.skipped_locked_pct != null &&
            <> {pct(p.skipped_locked_pct, 0)} of its raw top {p.top} were skipped: they closed locked at the upper price band, where nobody sells, so they couldn't be bought.</>
            }
            </Card>
          }
          {p &&
          <Card
            label="Buying the top picks every day for the year"
            value={p.top_year_after_cost_pct != null ? signedPct(p.top_year_after_cost_pct, 1) : signedPct(p.top_year_pct, 1)}
            valueTone={tone(p.top_year_after_cost_pct ?? p.top_year_pct)}>

              {p.top_year_after_cost_pct != null ?
            <>After about {pct(p.cost_pct, 2)} of taxes and charges a day (STT, stamp duty, exchange, GST, DP). Before them: {signedPct(p.top_year_pct, 1)}.</> :
            <>Before taxes and charges.</>}
              {' '}All stocks trading ₹5 crore+: {signedPct(p.liquid_year_pct, 1)}. Its bottom {p.top}: {signedPct(p.bottom_year_pct, 1)}.
            </Card>
          }
        </dl>
        <p className="mt-4 text-xs leading-relaxed text-muted">
          Learned from {m.train_rows.toLocaleString()} company-sessions, {fullDay(m.train_from)} up to the cutoff, in which
          stocks closed up {pct(m.train_up_pct)} of the time. {m.rounds} training rounds, picked on the year before the cutoff
          (AUC {auc(m.val_auc)} there).
          {m.models && m.models > 1 && <> Retrained every {m.retrain}: {m.models} models, each learning every session before its stretch of the year.</>}
          {' '}{m.flat.toLocaleString()} more calls aren't scored because the next close didn't move.
          The run took {m.minutes} min.
          {m.excluded && <> {m.excluded.symbols.toLocaleString()} ETFs and fund units ({m.excluded.calls.toLocaleString()} calls) are left out of the scores: they aren't companies.</>}
        </p>
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        {!run.report &&
        <Panel id="backtest-months" title="Month by month">
            <SmallTable
            head={['Month', 'Calls', 'Right', 'AUC']}
            rows={m.months.map((r) => [
            monthLabel(r.month),
            r.calls.toLocaleString(),
            <span key="r" className={rightTone(r.right_pct)}>{pct(r.right_pct)}</span>,
            auc(r.auc)]
            )} />

          </Panel>
        }
        <Panel id="backtest-bands" title="When it said up with…, it went up">
          <SmallTable
            head={['It said', 'Calls', 'Closed up']}
            rows={m.bands.map((b, i) => [
            i === 0 ? `Under ${Math.round(b.to * 100)}% up` :
            i === m.bands.length - 1 ? `${Math.round(b.from * 100)}% or more up` :
            `${Math.round(b.from * 100)}–${Math.round(b.to * 100)}% up`,
            b.calls.toLocaleString(),
            pct(b.up_pct)]
            )} />

          <p className="mt-2 text-xs text-muted">If the calls mean something, the right column climbs from top to bottom.</p>
        </Panel>
        <Panel id="backtest-turnover" title="By how much a stock trades a day">
          <SmallTable
            head={['Average turnover', 'Calls', 'Right', 'Best fixed call', 'AUC']}
            rows={m.by_turnover.map((t) => [
            t.label,
            t.calls.toLocaleString(),
            <span key="r" className={rightTone(t.right_pct)}>{pct(t.right_pct)}</span>,
            t.up_pct == null ? '–' : pct(Math.max(t.up_pct, 100 - t.up_pct)),
            auc(t.auc)]
            )} />

          <p className="mt-2 text-xs text-muted">
            Best fixed call: always calling the direction that came more often in that group. Right only beats it by a
            little in busy stocks; the AUC shows the ranking still works there.
          </p>
        </Panel>
        <Panel id="backtest-features" title="What it leaned on">
          <ul className="mt-3 grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2">
            {Object.entries(m.features).slice(0, 12).map(([f, share]) =>
            <li key={f} className="flex justify-between gap-3">
                <span className="text-ink/90">{FEATURE_LABELS[f] ?? f}</span>
                <span className="tabular-nums text-muted">{share.toFixed(1)}%</span>
              </li>
            )}
          </ul>
          <p className="mt-2 text-xs text-muted">Share of everything the model learned that came from each input.</p>
        </Panel>
      </div>
    </>);

}

/** The run's report: against the run before, why calls failed or worked, why it didn't do better, what to try
 *  next, the data checks, and the tables those sentences come from. */
function ReportPanel({ run, report: r }: {run: Run;report: Report;}) {
  if (r.error) {
    return (
      <Panel id="backtest-report" icon={FileTextIcon} title={`Report on run #${run.id}`}>
        <p className="mt-2 text-sm text-down">The report couldn't be written: {r.error}</p>
      </Panel>);

  }
  const monthAuc = Object.fromEntries(run.metrics.months.map((x) => [x.month, x.auc]));
  const group = (g: ReportGroup, extra: React.ReactNode[] = []) => [
  g.label,
  ...extra,
  g.calls.toLocaleString(),
  <span key="r" className={rightTone(g.right_pct)}>{pct(g.right_pct)}</span>,
  pct(g.said_up_pct),
  pct(g.went_up_pct)];

  const dayRows = (days: ReportDay[]) => days.map((d) => [
  fullDay(d.date),
  <span key="r" className={rightTone(d.right_pct)}>{pct(d.right_pct)}</span>,
  pct(d.said_up_pct, 0),
  pct(d.went_up_pct, 0),
  <span key="m" className={tone(d.market_pct)}>{signedPct(d.market_pct)}</span>,
  <span key="w" className="block min-w-[220px] whitespace-normal text-left text-xs">{d.why}</span>]
  );
  const missRows = (misses: ReportMiss[]) => misses.map((x) => [
  <span key="d" className="whitespace-nowrap">{fullDay(x.date)}</span>,
  <span key="s" className="block text-left">
      <span className="font-medium text-ink">{x.symbol}</span>
      {x.name && <span className="block max-w-[200px] truncate text-xs text-muted">{x.name}</span>}
    </span>,
  <CallTag key="c" p={x.prob_up} showConfident={false} />,
  <span key="n" className={tone(x.next_ret)}>{movePct(x.next_ret)}</span>,
  x.day_ret == null ? '–' : movePct(x.day_ret)]
  );

  return (
    <Panel
      id="backtest-report"
      icon={FileTextIcon}
      title={`Report on run #${run.id}`}
      aside={<span className="text-xs text-muted">written {when(r.generated_at)}</span>}>

      <p className="mt-2 text-[15px] font-semibold leading-relaxed text-ink">{r.headline}</p>

      <h3 className="mt-5 text-sm font-semibold text-ink">Against the run before</h3>
      {r.compare ?
      <>
          <SmallTable
          head={['', `Run #${r.compare.run}`, `Run #${run.id}`, 'Change']}
          rows={r.compare.rows.map((row) => {
            const f = (v: number | null) => v == null ? '–' : row.unit === '%' ? pct(v, 2) : row.label.startsWith('AUC') ? v.toFixed(3) : v.toLocaleString();
            const change = row.now == null || row.before == null ? '–' :
            row.label.startsWith('AUC') ? `${row.now - row.before >= 0 ? '+' : ''}${(row.now - row.before).toFixed(3)}` :
            row.unit === '%' ? `${row.now - row.before >= 0 ? '+' : ''}${(row.now - row.before).toFixed(2)} pts` :
            `${row.now - row.before >= 0 ? '+' : ''}${(row.now - row.before).toLocaleString()}`;
            return [row.label, f(row.before), f(row.now), change];
          })} />

          <Findings items={r.compare.notes} />
        </> :

      <p className="mt-1 text-sm text-muted">No earlier finished run to compare with yet. The next run will be compared with this one.</p>
      }

      <div className="mt-5 grid gap-x-8 gap-y-5 lg:grid-cols-2">
        <Findings title="Why calls failed" look="text-down" items={r.failed} />
        <Findings title="Why calls worked" look="text-up" items={r.worked} />
        <Findings title="Why it didn't do better" look="text-amber-400" items={r.limits} />
        <Findings title="What to try next" look="text-accent" items={r.next} />
      </div>
      {r.checks.length > 0 && <div className="mt-5"><Findings title="Data checks" items={r.checks} /></div>}

      <h3 className="mt-6 text-sm font-semibold text-ink">By what the typical stock did the next day</h3>
      <SmallTable
        head={['', 'Sessions', 'Calls', 'Right', 'Said up', 'Rose']}
        rows={r.market_moves.map((g) => group({ ...g, label: g.label.replace('The typical stock ', '').replace(' the next day', '') }, [String(g.sessions ?? '–')]))} />

      <h3 className="mt-6 text-sm font-semibold text-ink">By what the stock itself did on the day of the call</h3>
      <SmallTable
        head={['', 'Calls', 'Right', 'Said up', 'Rose', 'Next day, average']}
        rows={r.own_moves.map((g) => [...group(g), <span key="n" className={tone(g.next_move_pct ?? null)}>{signedPct(g.next_move_pct)}</span>])} />

      <h3 className="mt-6 text-sm font-semibold text-ink">Month by month</h3>
      <SmallTable
        head={['Month', 'Calls', 'Right', 'Said up', 'Rose', 'Read the market right', 'AUC']}
        rows={r.months.map((g) => [...group({ ...g, label: monthLabel(g.label) }), pct(g.market_call_pct), auc(monthAuc[g.label])])} />
      <p className="mt-2 text-xs text-muted">Read the market right: the share of its sessions where most of its calls went the way most stocks went.</p>

      <div className="mt-6 grid gap-x-8 gap-y-6 xl:grid-cols-2">
        <div>
          <h3 className="text-sm font-semibold text-down">Its worst days</h3>
          <SmallTable head={['Called at the close of', 'Right', 'Said up', 'Rose', 'Typical stock', 'Why']} rows={dayRows(r.worst_days)} />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-up">Its best days</h3>
          <SmallTable head={['Called at the close of', 'Right', 'Said up', 'Rose', 'Typical stock', 'Why']} rows={dayRows(r.best_days)} />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-ink">Sure it would rise, and it fell hardest</h3>
          <SmallTable head={['Called at the close of', 'Company', 'Call', 'Next day', 'That day']} rows={missRows(r.misses.said_up)} />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-ink">Sure it would fall, and it rose hardest</h3>
          <SmallTable head={['Called at the close of', 'Company', 'Call', 'Next day', 'That day']} rows={missRows(r.misses.said_down)} />
        </div>
      </div>
      <p className="mt-2 text-xs text-muted">The misses are among stocks trading ₹5 crore+ a day, leaving out splits and bonuses the bhavcopy didn't adjust.</p>
    </Panel>);

}

function Findings({ title, look = 'text-ink', items }: {title?: string;look?: string;items: string[];}) {
  if (items.length === 0) return null;
  return (
    <section>
      {title && <h3 className={`text-sm font-semibold ${look}`}>{title}</h3>}
      <ul className="mt-2 flex flex-col gap-2 text-sm leading-relaxed text-ink/90">
        {items.map((item) =>
        <li key={item} className="flex gap-2">
            <span className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-current ${look}`} aria-hidden="true" />
            <span>{item}</span>
          </li>
        )}
      </ul>
    </section>);

}

function SmallTable({ head, rows }: {head: string[];rows: React.ReactNode[][];}) {
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full text-sm tabular-nums">
        <thead className="text-xs text-muted">
          <tr className="border-b border-line">
            {head.map((h, i) =>
            <th key={h} scope="col" className={`py-2 font-medium ${i === 0 ? 'pr-3 text-left' : 'pl-3 text-right'}`}>{h}</th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, r) =>
          <tr key={r} className="border-b border-line/60 last:border-0">
              {cells.map((c, i) =>
            <td key={i} className={`py-2 ${i === 0 ? 'pr-3 text-ink' : 'pl-3 text-right text-muted'}`}>{c}</td>
            )}
            </tr>
          )}
        </tbody>
      </table>
    </div>);

}

/** Every session's calls or every company's year, with a day or a company opening its own list. */
function Browse({ run, days }: {run: Run;days: BacktestDay[];}) {
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'companies' ? 'companies' : 'days';
  const day = params.get('day');
  const symbol = params.get('symbol');
  const go = (changes: Record<string, string | null>) =>
  setParams((prev) => {
    const p = new URLSearchParams(prev);
    for (const [k, v] of Object.entries(changes)) if (v) p.set(k, v);else p.delete(k);
    return p;
  });

  if (day) {
    return (
      <DayCalls
        run={run}
        day={days.find((d) => d.date === day) ?? null}
        date={day}
        onBack={() => go({ day: null, dpage: null })}
        onCompany={(s) => go({ day: null, dpage: null, tab: 'companies', symbol: s, page: null })} />);


  }
  if (symbol) return <CompanyCalls run={run} symbol={symbol} onBack={() => go({ symbol: null, dpage: null })} />;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex w-fit rounded-lg border border-line bg-surface p-1" role="tablist" aria-label="List">
        {([['days', 'Every day'], ['companies', 'Every company']] as const).map(([key, label]) =>
        <button
          key={key}
          type="button"
          role="tab"
          aria-selected={tab === key}
          onClick={() => go({ tab: key === 'days' ? null : key, page: null })}
          className={`rounded-md px-4 py-1.5 text-sm font-medium ${tab === key ? 'bg-raised text-ink' : 'text-muted hover:text-ink'}`}>

            {label}
          </button>
        )}
      </div>
      {tab === 'days' ?
      <DayList days={days} onDay={(d) => go({ day: d, dpage: null })} /> :
      <CompanyList run={run} onCompany={(s) => go({ symbol: s, dpage: null })} />}
    </div>);

}

function DayList({ days, onDay }: {days: BacktestDay[];onDay: (date: string) => void;}) {
  const [page, setPage] = usePageParam('page');
  const rows = pageOf(days, page);

  return (
    <Panel id="backtest-days" title="Every session, newest first">
      <p className="mt-1 text-xs text-muted">Each call is made at a session's close for the next session. Open a day to see every company's call.</p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm tabular-nums">
          <thead className="text-xs text-muted">
            <tr className="border-b border-line">
              <th scope="col" className="py-2 pr-3 text-left font-medium">Called at the close of</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Companies</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Right</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Closed up next day</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Its top 10</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">All ₹5 cr+ stocks</th>
              <th scope="col" className="py-2 pl-3 text-right font-medium">AUC</th>
            </tr>
          </thead>
          <tbody>
            {rows.rows.map((d) => {
              const right = d.scored ? (100 * d.hits) / d.scored : null;
              return (
                <tr key={d.date} onClick={() => onDay(d.date)} className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-raised/40">
                  <td className="whitespace-nowrap py-2.5 pr-3">
                    <button type="button" className="font-medium text-ink hover:text-accent">{fullDay(d.date)}</button>
                  </td>
                  <td className="px-3 py-2.5 text-right text-ink">{d.calls.toLocaleString()}</td>
                  <td className={`px-3 py-2.5 text-right ${rightTone(right)}`}>{pct(right)}</td>
                  <td className="px-3 py-2.5 text-right text-muted">{d.scored ? pct((100 * d.ups) / d.scored, 0) : '–'}</td>
                  <td className={`px-3 py-2.5 text-right ${tone(d.top_ret)}`}>{d.top_ret == null ? '–' : movePct(d.top_ret)}</td>
                  <td className={`px-3 py-2.5 text-right ${tone(d.liquid_ret)}`}>{d.liquid_ret == null ? '–' : movePct(d.liquid_ret)}</td>
                  <td className="py-2.5 pl-3 text-right text-muted">{auc(d.auc)}</td>
                </tr>);

            })}
          </tbody>
        </table>
      </div>
      <Pagination page={rows.page} pages={rows.pages} total={days.length} onPage={setPage} noun="sessions" />
    </Panel>);

}

/** A search box that settles 300 ms after typing, and sends the page back to 1 when it does. */
function useSearch(onSettle: () => void): [string, string, (q: string) => void] {
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  useEffect(() => {
    if (q === query) return undefined;
    const id = setTimeout(() => {
      setQuery(q);
      onSettle();
    }, 300);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);
  return [q, query, setQ];
}

function SearchBox({ value, onChange }: {value: string;onChange: (q: string) => void;}) {
  return (
    <label className="flex items-center gap-2 rounded-lg border border-line bg-canvas px-2.5 py-1.5 text-sm">
      <SearchIcon className="h-4 w-4 text-muted" aria-hidden="true" />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Search symbol or company"
        aria-label="Search symbol or company"
        className="w-44 bg-transparent text-ink placeholder:text-muted focus:outline-none" />

    </label>);

}

const RETRAIN_WORDS: Record<Retrain, string> = { once: 'trained once', quarter: 'retrained every quarter', month: 'retrained every month' };
const HISTORY_WORDS: Record<HistorySpan, string> = { all: 'all history since 1994', '10y': 'the last 10 years', '5y': 'the last 5 years' };
const STEP_WORDS: Record<AutoStep, string> = { session: 'the next session', week: 'a week later', month: 'a month later' };

/** Auto run: each next backtest starts by itself, its cutoff a step after the last run's. */
function AutoRunControls({ data, retrain, history, onChanged }: {data: BacktestView;retrain: Retrain;history: HistorySpan;onChanged: () => void;}) {
  const auto = data.auto;
  const on = !!auto?.on;
  const [step, setStep] = useState<AutoStep>(auto?.step ?? 'session');
  const [runs, setRuns] = useState('10');
  const [busy, setBusy] = useState(false);

  const toggle = async () => {
    setBusy(true);
    try {
      await setBacktestAuto({ on: !on, step, runs: Number(runs), retrain, history });
      toast.success(on ? 'Auto run is off' : 'Auto run is on: each next run starts by itself');
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'The backend did not answer');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg bg-raised/50 p-3">
      <span className="text-xs font-semibold text-ink">Auto run</span>
      {!on &&
      <>
          <Select<AutoStep>
          label="Next cutoff"
          value={step}
          onChange={setStep}
          options={[['session', 'Next session'], ['week', 'A week later'], ['month', 'A month later']]} />
          <Select<string> label="Runs" value={runs} onChange={setRuns} options={[['5', '5'], ['10', '10'], ['20', '20'], ['50', '50']]} />
        </>
      }
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        className={`inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-semibold disabled:opacity-50 ${on ? 'border border-line text-ink hover:bg-raised' : 'bg-accent text-canvas hover:opacity-90'}`}>
        {on ? 'Turn off' : 'Turn on'}
      </button>
      <span className="text-xs text-muted">
        {on ?
        `On: next cutoff ${auto.next ? fullDay(auto.next) : 'after the current run'}, ${STEP_WORDS[auto.step ?? 'session']} each time · ${auto.left} runs left · ${RETRAIN_WORDS[auto.retrain ?? 'once']}, learning ${HISTORY_WORDS[auto.history ?? 'all']}${auto.note ? ` · ${auto.note}` : ''}` :
        auto?.note ?? "Off. When on, each run starts by itself with the next cutoff after the last run's, using the Retrain and Learn from choices above."}
      </span>
    </div>);
}

function Select<T extends string>({ label, value, options, onChange }: {label: string;value: T;options: [T, string][];onChange: (v: T) => void;}) {
  return (
    <label className="flex items-center gap-2 text-xs text-muted">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink focus:border-accent focus:outline-none">

        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>);

}

function BackButton({ onClick, children }: {onClick: () => void;children: React.ReactNode;}) {
  return (
    <button type="button" onClick={onClick} className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink hover:bg-raised">
      <ArrowLeftIcon className="h-3.5 w-3.5" aria-hidden="true" /> {children}
    </button>);

}

const SHOW: [DayShow, string][] = [['all', 'All'], ['right', 'Right'], ['wrong', 'Wrong'], ['confident', 'Confident'], ['liquid', '₹5 cr+ a day']];
const DAY_SORT: [DaySort, string][] = [['confidence', 'Most confident'], ['move', 'Biggest move up'], ['turnover', 'Most traded'], ['symbol', 'Symbol']];

function DayCalls({ run, day, date, onBack, onCompany }: {run: Run;day: BacktestDay | null;date: string;onBack: () => void;onCompany: (symbol: string) => void;}) {
  const [page, setPage] = usePageParam('dpage');
  const [q, query, setQ] = useSearch(() => setPage(1));
  const [show, setShow] = useState<DayShow>('all');
  const [sort, setSort] = useState<DaySort>('confidence');
  const { data, error } = usePoll((signal) => fetchBacktestDay(run.id, date, page, query, show, sort, signal), 300_000, [run.id, date, page, query, show, sort]);

  return (
    <Panel id="backtest-day" title={`Calls at the close of ${fullDay(date)}`} aside={<BackButton onClick={onBack}>Every day</BackButton>}>
      {day &&
      <p className="mt-1 text-sm text-muted">
          {day.calls.toLocaleString()} companies · right {pct(day.scored ? (100 * day.hits) / day.scored : null)} of the {day.scored.toLocaleString()} that moved ·{' '}
          {day.ups.toLocaleString()} closed up next day
          {day.top_ret != null && <> · its top 10 {movePct(day.top_ret)} against {day.liquid_ret == null ? '–' : movePct(day.liquid_ret)} for all ₹5 cr+ stocks</>}
        </p>
      }
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <SearchBox value={q} onChange={setQ} />
        <Select label="Show" value={show} options={SHOW} onChange={(v) => {setShow(v);setPage(1);}} />
        <Select label="Sort" value={sort} options={DAY_SORT} onChange={(v) => {setSort(v);setPage(1);}} />
      </div>
      {error && <p className="mt-3 text-sm text-down">{error}</p>}
      {data && (
      data.rows.length === 0 ?
      <Empty>No call matches.</Empty> :

      <>
            <CallTable calls={data.rows} onCompany={onCompany} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} noun="calls" />
          </>)
      }
    </Panel>);

}

/** Calls as rows: a day's list shows the company, a company's list shows the day. */
function CallTable({ calls, onCompany }: {calls: BacktestCall[];onCompany?: (symbol: string) => void;}) {
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full min-w-[760px] text-sm tabular-nums">
        <thead className="text-xs text-muted">
          <tr className="border-b border-line">
            <th scope="col" className="py-2 pr-3 text-left font-medium">{onCompany ? 'Company' : 'Called at the close of'}</th>
            <th scope="col" className="px-3 py-2 text-left font-medium">Call</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">Close</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">Next close</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">Move</th>
            <th scope="col" className="px-3 py-2 text-left font-medium">Result</th>
            <th scope="col" className="py-2 pl-3 text-right font-medium">Turnover a day</th>
          </tr>
        </thead>
        <tbody>
          {calls.map((c) =>
          <tr key={c.symbol ?? c.date} className="border-b border-line/60 last:border-0">
              <td className="py-2.5 pr-3">
                {onCompany && c.symbol ?
              <>
                    <button type="button" onClick={() => onCompany(c.symbol!)} className="text-left font-medium text-ink hover:text-accent">{c.symbol}</button>
                    {c.name && <span className="block max-w-[240px] truncate text-xs text-muted">{c.name}</span>}
                  </> :

              <span className="whitespace-nowrap text-ink">{c.date && fullDay(c.date)}</span>
              }
              </td>
              <td className="px-3 py-2.5">
                <CallTag p={c.prob_up} />
                {c.locked === 1 &&
              <span className="mt-1 block text-[11px] text-amber-400" title="Closed at its high after a 2%+ rise: locked at the upper price band, nobody selling">
                    Upper circuit: couldn't be bought
                  </span>
              }
                {c.locked === -1 &&
              <span className="mt-1 block text-[11px] text-amber-400" title="Closed at its low after a 2%+ fall: locked at the lower price band, nobody buying">
                    Lower circuit: couldn't be sold
                  </span>
              }
              </td>
              <td className="px-3 py-2.5 text-right text-muted">{price(c.close)}</td>
              <td className="px-3 py-2.5 text-right text-ink">{price(c.next_close)}</td>
              <td className={`px-3 py-2.5 text-right font-medium ${tone(c.next_ret)}`}>{movePct(c.next_ret)}</td>
              <td className="px-3 py-2.5">{c.hit === null ? <span className="text-xs text-muted">No move</span> : <ResultTag hit={c.hit} />}</td>
              <td className="py-2.5 pl-3 text-right text-muted">{rupees(c.avg_value)}</td>
            </tr>
          )}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-muted">Move counts splits and bonuses, so it can differ from the two closes on those days.</p>
    </div>);

}

const COMPANY_SORT: [CompanySort, string][] = [['right', 'Most often right'], ['worst', 'Most often wrong'], ['turnover', 'Most traded'], ['symbol', 'Symbol']];

function CompanyList({ run, onCompany }: {run: Run;onCompany: (symbol: string) => void;}) {
  const [page, setPage] = usePageParam('page');
  const [q, query, setQ] = useSearch(() => setPage(1));
  const [sort, setSort] = useState<CompanySort>('right');
  const { data, error } = usePoll((signal) => fetchBacktestCompanies(run.id, page, query, sort, signal), 300_000, [run.id, page, query, sort]);

  return (
    <Panel
      id="backtest-companies"
      title="Every company's year"
      aside={
      <div className="flex flex-wrap items-center gap-3">
          <SearchBox value={q} onChange={setQ} />
          <Select label="Sort" value={sort} options={COMPANY_SORT} onChange={(v) => {setSort(v);setPage(1);}} />
        </div>
      }>

      <p className="mt-1 text-xs text-muted">Companies with at least 50 scored calls come first when sorting by right or wrong.</p>
      {error && <p className="mt-3 text-sm text-down">{error}</p>}
      {data && (
      data.rows.length === 0 ?
      <Empty>No company matches.</Empty> :

      <>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[680px] text-sm tabular-nums">
                <thead className="text-xs text-muted">
                  <tr className="border-b border-line">
                    <th scope="col" className="py-2 pr-3 text-left font-medium">Company</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Calls</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Right</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Said up</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Closed up</th>
                    <th scope="col" className="py-2 pl-3 text-right font-medium">Turnover a day</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((c) => {
                const right = c.scored ? (100 * c.hits) / c.scored : null;
                return (
                  <tr key={c.symbol} onClick={() => onCompany(c.symbol)} className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-raised/40">
                        <td className="py-2.5 pr-3">
                          <button type="button" className="text-left font-medium text-ink hover:text-accent">{c.symbol}</button>
                          {c.name && <span className="block max-w-[260px] truncate text-xs text-muted">{c.name}</span>}
                        </td>
                        <td className="px-3 py-2.5 text-right text-ink">{c.calls.toLocaleString()}</td>
                        <td className={`px-3 py-2.5 text-right ${rightTone(right)}`}>{pct(right)}</td>
                        <td className="px-3 py-2.5 text-right text-muted">{pct((100 * c.said_up) / c.calls, 0)}</td>
                        <td className="px-3 py-2.5 text-right text-muted">{c.scored ? pct((100 * c.ups) / c.scored, 0) : '–'}</td>
                        <td className="py-2.5 pl-3 text-right text-muted">{rupees(c.avg_value)}</td>
                      </tr>);

              })}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} noun="companies" />
          </>)
      }
    </Panel>);

}

function CompanyCalls({ run, symbol, onBack }: {run: Run;symbol: string;onBack: () => void;}) {
  const [page, setPage] = usePageParam('dpage');
  const { data, error } = usePoll((signal) => fetchBacktestCompany(run.id, symbol, signal), 300_000, [run.id, symbol]);
  const rows = pageOf(data?.calls ?? [], page);
  const c = data?.company;

  return (
    <Panel id="backtest-company" title={`${symbol}${c?.name ? ` · ${c.name}` : ''}: every call`} aside={<BackButton onClick={onBack}>Every company</BackButton>}>
      {c &&
      <p className="mt-1 text-sm text-muted">
          Right <span className={rightTone(c.scored ? (100 * c.hits) / c.scored : null)}>{pct(c.scored ? (100 * c.hits) / c.scored : null)}</span> of the{' '}
          {c.scored.toLocaleString()} calls whose next close moved · said up {pct((100 * c.said_up) / c.calls, 0)} of the time, closed up{' '}
          {c.scored ? pct((100 * c.ups) / c.scored, 0) : '–'} · usually trades {rupees(c.avg_value)} a day
        </p>
      }
      {error && <p className="mt-3 text-sm text-down">{error}</p>}
      {data &&
      <>
          <CallTable calls={rows.rows} />
          <Pagination page={rows.page} pages={rows.pages} total={data.calls.length} onPage={setPage} noun="calls" />
        </>
      }
    </Panel>);

}
