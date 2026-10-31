import React, { useEffect, useState } from 'react';
import { ArrowLeftIcon, DatabaseIcon, RefreshCwIcon, SearchIcon } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Empty, ErrorNote, PageTitle, Panel } from '../components/Bits';
import { Pagination, usePageParam } from '../components/Pagination';
import { usePoll } from '../hooks/usePoll';
import { agoLabel } from '../utils/format';
import {
  BAR_SIZES,
  fetchBars,
  fetchDataSummary,
  fetchSymbols,
  syncNow,
  type BarSize,
  type DataSummary } from
'../utils/data';
import { formatSession } from '../utils/trikal';

/** Everything the data keeper has downloaded into market.db: how many sessions are missing per bar size, a Sync
 *  button with the progress of the download, and every symbol's bars, 20 a page. */
export function Data() {
  const [version, setVersion] = useState(0);
  const { data, error } = usePoll(fetchDataSummary, 5_000, [version]);
  // The tab, the symbol opened and the pages live in the URL, so a refresh or Back keeps your place
  const [params, setParams] = useSearchParams();
  const size = (BAR_SIZES.find((b) => b.key === params.get('size'))?.key ?? '1d') as BarSize;
  const setSize = (next: BarSize) => setParams(next === '1d' ? {} : { size: next }, { replace: true });

  return (
    <div className="flex flex-col gap-5">
      <PageTitle icon={DatabaseIcon} title="Data">
        The market history on the E: drive: every listed NSE company, the indices and the rupee pairs, at four bar sizes.
        It downloads on its own every weekday after 19:00 IST, and you can sync any time.
      </PageTitle>
      {error && <ErrorNote>{error}</ErrorNote>}
      {data && <SummaryPanel data={data} onSynced={() => setVersion((v) => v + 1)} />}

      <div className="flex w-fit flex-wrap rounded-lg border border-line bg-surface p-1" role="tablist" aria-label="Bar size">
        {BAR_SIZES.map((b) =>
        <button
          key={b.key}
          type="button"
          role="tab"
          aria-selected={size === b.key}
          onClick={() => setSize(b.key)}
          className={`rounded-md px-4 py-1.5 text-sm font-medium ${size === b.key ? 'bg-raised text-ink' : 'text-muted hover:text-ink'}`}>

            {b.label}
          </button>
        )}
      </div>
      <SymbolList key={size} size={size} />
    </div>);

}

/** "12 min", "1 h 5 min" */
function duration(seconds: number): string {
  const m = Math.max(1, Math.round(seconds / 60));
  return m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`;
}

function SummaryPanel({ data, onSynced }: {data: DataSummary;onSynced: () => void;}) {
  const [busy, setBusy] = useState(false);
  const k = data.keeper;
  const p = k.progress;

  const sync = async () => {
    setBusy(true);
    try {
      const r = await syncNow();
      toast.success(r.started ? 'Sync started: NSE bhavcopy first, then Yahoo' : 'A sync is already running');
      onSynced();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not start the sync');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel
      id="data-summary"
      title={`Up to the last session, ${formatSession(data.last_session)}`}
      aside={
      <button
        type="button"
        onClick={sync}
        disabled={busy || !!k.running}
        className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-canvas hover:opacity-90 disabled:opacity-50">

          <RefreshCwIcon className={`h-3.5 w-3.5 ${k.running ? 'animate-spin' : ''}`} aria-hidden="true" />
          {k.running ? 'Syncing…' : 'Sync now'}
        </button>
      }>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {data.intervals.map((i) =>
        <div key={i.interval} className="rounded-lg bg-raised/50 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">{i.label}</p>
            <Missing n={i.missing} />
            <p className="mt-1 text-xs text-muted">
              {i.last ? <>has {formatSession(i.first ?? i.last)} → {formatSession(i.last)}</> : 'nothing yet'}
            </p>
            {i.kept_days &&
          <p className={`mt-1 text-xs ${i.recoverable === false ? 'text-down' : 'text-muted'}`}>
                {i.recoverable === false ? 'Older than Yahoo keeps: gone for good' : `Yahoo keeps the last ~${i.kept_days} days`}
              </p>
          }
          </div>
        )}
        <div className="rounded-lg bg-raised/50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">NSE bhavcopy</p>
          <Missing n={data.bhavcopy.missing} />
          <p className="mt-1 text-xs text-muted">{data.bhavcopy.last ? <>up to {formatSession(data.bhavcopy.last)}</> : 'nothing yet'}</p>
          <p className="mt-1 text-xs text-muted">{data.listed.toLocaleString()} companies listed today</p>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-line px-3 py-2.5 text-sm">
        {k.running ?
        <>
            <p className="text-ink">
              Downloading: <span className="font-semibold">{p ? `${p.job} ${p.step}` : k.running}</span>
              {p && <> · {p.done.toLocaleString()} of {p.total.toLocaleString()}</>}
              {p?.seconds_left != null && <span className="text-accent"> · about {duration(p.seconds_left)} left for this step</span>}
            </p>
            {p?.all_seconds_left != null &&
          <p className="mt-1 text-sm font-semibold text-ink">
                Whole sync: about {duration(p.all_seconds_left)} left
                <span className="font-normal text-muted">
                  {' '}(finishing around {new Date(Date.now() + p.all_seconds_left * 1000).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                  {p.steps_left && p.steps_left.length > 0 && `; still to come: ${p.steps_left.join(', ')}`})
                </span>
              </p>
          }
            {p &&
          <div className="mt-2 h-1.5 rounded-full bg-raised" role="progressbar" aria-valuemin={0} aria-valuemax={p.total} aria-valuenow={p.done}>
                <div className="h-1.5 rounded-full bg-accent" style={{ width: `${p.total ? (100 * p.done) / p.total : 0}%` }} />
              </div>
          }
            <p className="mt-1.5 text-xs text-muted">
              Yahoo goes 1 min → 15 min → 1 hour → 1 day, about 3,200 symbols each. The whole-sync time counts the steps
              still to come at what they took last time.
            </p>
          </> :

        <p className="text-muted">
            {k.done ? <>Last full download finished for {formatSession(k.done)}</> : 'No full download yet'}
            {k.last && <> · last run {agoLabel(Date.parse(k.last.at))}{!k.last.ok && ' (cut short: it resumes on the next run)'}</>}
            {k.due ? ' · due now: starts within 10 minutes, or press Sync now' : ' · next run on the next weekday after 19:00 IST'}
          </p>
        }
      </div>
    </Panel>);

}

function Missing({ n }: {n: number | null;}) {
  if (n == null) return <p className="mt-1 text-lg font-semibold text-muted">–</p>;
  return (
    <p className={`mt-1 text-lg font-semibold ${n === 0 ? 'text-up' : 'text-amber-400'}`}>
      {n === 0 ? 'Complete' : `${n} ${n === 1 ? 'session' : 'sessions'} missing`}
    </p>);

}

function SymbolList({ size }: {size: BarSize;}) {
  const [params, setParams] = useSearchParams();
  const [page, setPage] = usePageParam('page');
  const query = params.get('q') ?? '';
  const [q, setQ] = useState(query);
  const symbol = params.get('symbol');
  const setSymbol = (next: string | null) =>
  setParams((prev) => {
    const p = new URLSearchParams(prev);
    if (next) p.set('symbol', next);else
    p.delete('symbol');
    p.delete('bpage');
    return p;
  });
  useEffect(() => {
    if (q === query) return undefined;
    const id = setTimeout(() =>
    setParams((prev) => {
      const p = new URLSearchParams(prev);
      if (q) p.set('q', q);else
      p.delete('q');
      p.delete('page'); // a new search starts on its first page
      return p;
    }, { replace: true }), 300);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);
  const { data, error } = usePoll((signal) => fetchSymbols(size, page, query, signal), 60_000, [size, page, query]);
  const label = BAR_SIZES.find((b) => b.key === size)?.label;

  if (symbol) return <BarList size={size} symbol={symbol} onBack={() => setSymbol(null)} />;

  return (
    <Panel
      id="symbols"
      title={`${label} bars by symbol`}
      aside={
      <label className="flex items-center gap-2 rounded-lg border border-line bg-canvas px-2.5 py-1.5 text-sm">
          <SearchIcon className="h-4 w-4 text-muted" aria-hidden="true" />
          <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search symbol or company"
          aria-label="Search symbol or company"
          className="w-48 bg-transparent text-ink placeholder:text-muted focus:outline-none" />

        </label>
      }>

      {error && <p className="mt-3 text-sm text-down">{error}</p>}
      {data && (
      data.rows.length === 0 ?
      <Empty>No symbol matches.</Empty> :

      <>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead className="text-xs text-muted">
                  <tr className="border-b border-line">
                    <th scope="col" className="py-2 pr-3 text-left font-medium">Symbol</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Bars</th>
                    <th scope="col" className="px-3 py-2 text-left font-medium">From</th>
                    <th scope="col" className="px-3 py-2 text-left font-medium">To</th>
                    <th scope="col" className="py-2 pl-3 text-right font-medium">Missing</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r) =>
              <tr
                key={r.symbol}
                onClick={() => setSymbol(r.symbol)}
                className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-raised/40">

                      <td className="py-2.5 pr-3">
                        <button type="button" className="text-left font-medium text-ink hover:text-accent">{r.symbol}</button>
                        {r.name && <span className="block max-w-[260px] truncate text-xs text-muted">{r.name}</span>}
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-ink">{r.bars.toLocaleString()}</td>
                      <td className="px-3 py-2.5 text-muted">{r.first ? formatSession(r.first) : '–'}</td>
                      <td className="px-3 py-2.5 text-muted">{r.last ? formatSession(r.last) : '–'}</td>
                      <td className={`py-2.5 pl-3 text-right tabular-nums ${r.missing ? 'text-amber-400' : 'text-up'}`}>
                        {r.missing == null ? 'none yet' : r.missing === 0 ? 'none' : `${r.missing} ${r.missing === 1 ? 'session' : 'sessions'}`}
                      </td>
                    </tr>
              )}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} noun="symbols" />
          </>)
      }
    </Panel>);

}

function BarList({ size, symbol, onBack }: {size: BarSize;symbol: string;onBack: () => void;}) {
  const [page, setPage] = usePageParam('bpage');
  const { data, error } = usePoll((signal) => fetchBars(size, symbol, page, signal), 60_000, [size, symbol, page]);
  const label = BAR_SIZES.find((b) => b.key === size)?.label;
  const digits = symbol.endsWith('INR') ? 4 : 2;
  const price = (v: number) => v.toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits });

  return (
    <Panel
      id="bars"
      title={`${symbol} · ${label} bars, newest first`}
      aside={
      <button type="button" onClick={onBack} className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink hover:bg-raised">
          <ArrowLeftIcon className="h-3.5 w-3.5" aria-hidden="true" /> All symbols
        </button>
      }>

      {error && <p className="mt-3 text-sm text-down">{error}</p>}
      {data && (
      data.rows.length === 0 ?
      <Empty>No {label} bars downloaded for {symbol} yet.</Empty> :

      <>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[600px] text-sm tabular-nums">
                <thead className="text-xs text-muted">
                  <tr className="border-b border-line">
                    <th scope="col" className="py-2 pr-3 text-left font-medium">Time (IST)</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Open</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">High</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Low</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Close</th>
                    <th scope="col" className="py-2 pl-3 text-right font-medium">Volume</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((b) =>
              <tr key={b.time} className="border-b border-line/60 last:border-0">
                      <td className="whitespace-nowrap py-2 pr-3 text-ink">{b.time}</td>
                      <td className="px-3 py-2 text-right text-muted">{price(b.open)}</td>
                      <td className="px-3 py-2 text-right text-up">{price(b.high)}</td>
                      <td className="px-3 py-2 text-right text-down">{price(b.low)}</td>
                      <td className={`px-3 py-2 text-right font-medium ${b.close >= b.open ? 'text-up' : 'text-down'}`}>{price(b.close)}</td>
                      <td className="py-2 pl-3 text-right text-muted">{b.volume == null ? '–' : b.volume.toLocaleString('en-IN')}</td>
                    </tr>
              )}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} noun="bars" />
          </>)
      }
    </Panel>);

}
