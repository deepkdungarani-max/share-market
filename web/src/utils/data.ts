import { getJson, sendJson } from './api';

export type BarSize = '1d' | '1h' | '15m' | '1m';

export const BAR_SIZES: {key: BarSize;label: string;}[] = [
{ key: '1d', label: '1 day' },
{ key: '1h', label: '1 hour' },
{ key: '15m', label: '15 min' },
{ key: '1m', label: '1 min' }];


/** What a running download is doing (written by the downloaders every few symbols or days). */
export interface Progress {
  job: string;
  /** The bar size being fetched (Yahoo), or "days" (NSE). */
  step: string;
  done: number;
  total: number;
  seconds_left: number | null;
  /** Yahoo: the whole run's time left (the steps still to come take what they took last time). */
  all_seconds_left?: number;
  /** Yahoo: the bar sizes still to fetch after this one. */
  steps_left?: string[];
  at: string;
}

export interface Keeper {
  /** IST date the downloads last finished. */
  done: string | null;
  last: {at: string;ok: boolean;results: Record<string, {code: number;minutes: number | null;}>;} | null;
  running: string | null;
  progress: Progress | null;
  due: boolean;
}

export interface IntervalSummary {
  interval: BarSize;
  label: string;
  first: string | null;
  last: string | null;
  /** Sessions missing after the last bar, up to the last finished session. */
  missing: number | null;
  kept_days: number | null;
  /** Whether Yahoo still serves the missing sessions (false: gone for good). */
  recoverable: boolean | null;
}

export interface DataSummary {
  last_session: string;
  intervals: IntervalSummary[];
  listed: number;
  bhavcopy: {last: string | null;missing: number | null;};
  keeper: Keeper;
}

export interface SymbolRow {
  symbol: string;
  name: string | null;
  bars: number;
  first: string | null;
  last: string | null;
  missing: number | null;
}

export interface Page<T> {
  page: number;
  pages: number;
  total: number;
  rows: T[];
}

export interface Bar {
  /** IST: YYYY-MM-DD for days, YYYY-MM-DD HH:MM for intraday bars. */
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}

export const fetchDataSummary = (signal?: AbortSignal) => getJson<DataSummary>('/data/summary', signal);
export const fetchSymbols = (interval: BarSize, page: number, q: string, signal?: AbortSignal) =>
getJson<Page<SymbolRow>>(`/data/symbols?${new URLSearchParams({ interval, page: String(page), q }).toString()}`, signal);
export const fetchBars = (interval: BarSize, symbol: string, page: number, signal?: AbortSignal) =>
getJson<Page<Bar>>(`/data/bars?${new URLSearchParams({ interval, symbol, page: String(page) }).toString()}`, signal);
export const syncNow = () => sendJson<{started: boolean;keeper: Keeper;}>('POST', '/data/sync');
