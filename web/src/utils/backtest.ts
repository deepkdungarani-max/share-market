import { getJson, sendJson } from './api';
import type { Page } from './data';

export type RunStatus = 'running' | 'done' | 'failed' | 'stopped';
/** How often a run trains a fresh model through the test year. */
export type Retrain = 'once' | 'quarter' | 'month';
/** How many years of sessions each model learns from: all since 1994, or the last 10 or 5. */
export type HistorySpan = 'all' | '10y' | '5y';
/** How far each Auto run's cutoff moves past the last run's. */
export type AutoStep = 'session' | 'week' | 'month';
/** The Auto run: it starts each next run by itself, a step after the last cutoff. */
export interface AutoRun {
  on: boolean;
  step?: AutoStep;
  /** Runs it may still start. */
  left?: number;
  retrain?: Retrain;
  history?: HistorySpan;
  /** What it did last, or why it stopped. */
  note?: string | null;
  /** While on: the cutoff its next run takes. */
  next?: string | null;
}

/** A run in the list: its headline numbers only. */
export interface RunBrief {
  id: number;
  /** YYYY-MM-DD: trained on every session before it, tested on every session from it. */
  cutoff: string | null;
  started_at: string;
  finished_at: string | null;
  status: RunStatus;
  /** What a running run is doing, or why a failed one failed. */
  step: string | null;
  right_pct: number | null;
  auc: number | null;
  calls: number | null;
  minutes: number | null;
  /** 'quarter' or 'month': a fresh model for each stretch of the test year (null in runs made before). */
  retrain: Retrain | null;
  models: number | null;
  history: HistorySpan | null;
  /** How long it worked (so far, while running), leaving out pauses. */
  seconds: number | null;
}

export type StageStatus = 'done' | 'running' | 'paused' | 'stopped' | 'waiting';

export interface Stage {
  key: string;
  label: string;
  status: StageStatus;
  /** What the stage reported, with its numbers. */
  detail: string | null;
  /** How long it worked (so far, while running). */
  seconds: number | null;
  /** What it took in the last finished run. */
  usually: number;
}

/** The latest run's stages, the numbers they reported, and (while it runs) its time left. */
export interface Progress {
  stages: Stage[];
  facts: Partial<Record<'rows' | 'companies' | 'fit_rows' | 'check_rows' | 'train_rows' | 'rounds' | 'calls' | 'models', number>>;
  seconds_left: number | null;
  paused_since: string | null;
}

export interface Metrics {
  /** Calls scored (the next close moved); `flat` more were called but the close didn't move. */
  calls: number;
  flat: number;
  companies: number;
  sessions: number;
  right_pct: number;
  /** How often a stock really closed up. */
  up_pct: number;
  /** Right % of always calling the direction most common before the cutoff. */
  always_pct: number;
  said_up_pct: number;
  /** 0.5 is a coin toss: how well the calls rank risers above fallers. */
  auc: number | null;
  daily_auc: number | null;
  /** How often it trained a fresh model through the test year, and how many models that made. */
  retrain?: Retrain;
  models?: number;
  history?: HistorySpan;
  confident: {calls: number;right_pct: number | null;};
  /** Stocks trading ₹5 crore+ a day; up_pct gives their always-down baseline. */
  liquid: {calls: number;right_pct: number | null;auc: number | null;up_pct?: number | null;confident_calls: number;confident_right_pct: number | null;};
  bands: {from: number;to: number;calls: number;up_pct: number | null;}[];
  by_turnover: {label: string;calls: number;right_pct: number | null;up_pct?: number | null;auc: number | null;}[];
  months: {month: string;calls: number;right_pct: number | null;auc: number | null;}[];
  /** Each day's TOP highest and lowest calls among the liquid companies, and how they moved next day. */
  picks: {
    days: number;
    top: number;
    top_avg_pct: number | null;
    bottom_avg_pct: number | null;
    liquid_avg_pct: number | null;
    top_beat_days_pct: number | null;
    top_year_pct: number;
    bottom_year_pct: number;
    liquid_year_pct: number;
    /** A delivery round trip's taxes and charges, in %, and the top picks' year after paying it daily. */
    cost_pct?: number;
    top_year_after_cost_pct?: number;
    /** Share of the raw top 10 skipped for being locked at the upper price band (not buyable). */
    skipped_locked_pct?: number | null;
  } | null;
  /** Symbols taken out of the scoring after the run (ETFs and fund units). */
  excluded?: {symbols: number;calls: number;note: string;};
  train_rows: number;
  train_from: string;
  train_up_pct: number;
  rounds: number;
  val_auc: number;
  /** Share of the model's total gain per feature, biggest first. */
  features: Record<string, number>;
  minutes: number;
}

export interface Run {
  id: number;
  cutoff: string;
  started_at: string;
  finished_at: string;
  status: RunStatus;
  metrics: Metrics;
  /** Rows written to backtest.db. */
  saved?: {predictions: number;days: number;companies: number;};
  /** Written by the run's last step (app/backtest_report.py); null for runs made before reports. */
  report?: Report | null;
}

/** Calls grouped by a condition: how often right, how often it said up, how often they rose. */
export interface ReportGroup {
  label: string;
  calls: number;
  right_pct: number | null;
  said_up_pct: number | null;
  went_up_pct: number | null;
  sessions?: number;
  next_move_pct?: number | null;
  /** Months: share of its sessions where its call for the market as a whole was right. */
  market_call_pct?: number;
}

export interface ReportDay {
  date: string;
  calls: number;
  right_pct: number;
  said_up_pct: number;
  went_up_pct: number;
  /** The typical stock's next-day move, in %. */
  market_pct: number;
  why: string;
}

export interface ReportMiss {
  date: string;
  symbol: string;
  name: string | null;
  prob_up: number;
  next_ret: number;
  day_ret: number | null;
  locked: number | null;
}

export interface Report {
  generated_at: string;
  error?: string;
  headline: string;
  failed: string[];
  worked: string[];
  limits: string[];
  next: string[];
  checks: string[];
  /** Against the finished run before it; null for the first. */
  compare: {run: number;cutoff: string;rows: {label: string;now: number | null;before: number | null;unit: string;}[];notes: string[];} | null;
  market_moves: ReportGroup[];
  own_moves: ReportGroup[];
  months: ReportGroup[];
  worst_days: ReportDay[];
  best_days: ReportDay[];
  /** Its worst confident misses on stocks trading ₹5 crore+ a day. */
  misses: {said_up: ReportMiss[];said_down: ReportMiss[];};
}

export interface BacktestDay {
  date: string;
  calls: number;
  scored: number;
  hits: number;
  ups: number;
  auc: number | null;
  top_ret: number | null;
  bottom_ret: number | null;
  liquid_ret: number | null;
}

export interface BacktestView {
  running: boolean;
  runs: RunBrief[];
  /** The finished run shown: the latest unless ?run= picks another. */
  run: Run | null;
  days: BacktestDay[];
  progress: Progress | null;
  /** Bytes on disk: market.db on E:, its copy on the SSD (only while a run reads it), backtest.db. */
  files: {market_db: number | null;snapshot: number | null;backtest_db: number | null;};
  auto: AutoRun;
  /** The next session after the latest run's cutoff: the cutoff picker starts there. */
  next_cutoff: string | null;
}

/** One call: a company on a day (a day's list has symbol and name, a company's list has date). */
export interface BacktestCall {
  symbol?: string;
  name?: string | null;
  date?: string;
  prob_up: number;
  close: number;
  next_close: number;
  /** The next session's move (split-adjusted), as a fraction. */
  next_ret: number;
  avg_value: number | null;
  /** 1 right, 0 wrong, null when the close didn't move. */
  hit: number | null;
  /** 1: closed locked at the upper price band (not buyable), -1: at the lower band (not sellable). */
  locked?: number | null;
}

export interface CompanyYear {
  symbol: string;
  name: string | null;
  calls: number;
  scored: number;
  hits: number;
  ups: number;
  said_up: number;
  avg_value: number | null;
}

export type DayShow = 'all' | 'right' | 'wrong' | 'confident' | 'liquid';
export type DaySort = 'confidence' | 'move' | 'symbol' | 'turnover';
export type CompanySort = 'right' | 'worst' | 'symbol' | 'turnover';

const query = (params: Record<string, string | number>) =>
new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();

export const fetchBacktest = (run: number | null, signal?: AbortSignal) =>
getJson<BacktestView>(`/backtest${run ? `?run=${run}` : ''}`, signal);
export const fetchBacktestDay = (run: number, date: string, page: number, q: string, show: DayShow, sort: DaySort, signal?: AbortSignal) =>
getJson<Page<BacktestCall>>(`/backtest/day?${query({ run, date, page, q, show, sort })}`, signal);
export const fetchBacktestCompanies = (run: number, page: number, q: string, sort: CompanySort, signal?: AbortSignal) =>
getJson<Page<CompanyYear>>(`/backtest/companies?${query({ run, page, q, sort })}`, signal);
export const fetchBacktestCompany = (run: number, symbol: string, signal?: AbortSignal) =>
getJson<{company: CompanyYear;calls: BacktestCall[];}>(`/backtest/company?${query({ run, symbol })}`, signal);
export const startBacktest = (cutoff: string | null, retrain: Retrain = 'once', history: HistorySpan = 'all') =>
sendJson<BacktestView & {started: boolean;}>('POST', '/backtest/run', { cutoff, retrain, history });
export const pauseBacktest = () => sendJson<BacktestView & {done: boolean;}>('POST', '/backtest/pause');
export const resumeBacktest = () => sendJson<BacktestView & {done: boolean;}>('POST', '/backtest/resume');
export const setBacktestAuto = (body: {on: boolean;step: AutoStep;runs: number;retrain: Retrain;history: HistorySpan;}) =>
sendJson<BacktestView>('POST', '/backtest/auto', body);

/** What each feature means, for the "what it leaned on" list. */
export const FEATURE_LABELS: Record<string, string> = {
  ret_1: "The day's move",
  ret_3: '3-day move',
  ret_6: '6-day move',
  ret_12: '12-day move',
  ret_60: '3-month move',
  ret_250: '1-year move',
  rsi_14: 'RSI (14)',
  macd_hist: 'MACD',
  ema_9_21: '9- vs 21-day average',
  close_ema_21: 'Price vs 21-day average',
  volatility_12: 'Volatility',
  range: "Day's high–low range",
  body: 'Candle body',
  upper_wick: 'Upper wick',
  lower_wick: 'Lower wick',
  vol_ratio: 'Volume vs usual',
  liquidity: 'Turnover rank',
  dow: 'Weekday',
  mkt_ret: "Market's move that day",
  breadth: 'Share of stocks up',
  rel_1: 'Move vs the market'
};

/** "Fri, 30 Oct 2025" */
export function fullDay(day: string): string {
  return new Date(`${day}T00:00:00`).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
}

/** "2025-11" -> "Nov 2025" */
export function monthLabel(month: string): string {
  return new Date(`${month}-01T00:00:00`).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' });
}

/** Average daily turnover in rupees as "₹12.3 cr" or "₹45 lakh". */
export function rupees(v: number | null): string {
  if (v == null) return '–';
  if (v >= 1e7) return `₹${(v / 1e7).toLocaleString('en-IN', { maximumFractionDigits: v >= 1e9 ? 0 : 1 })} cr`;
  return `₹${Math.max(0, Math.round(v / 1e5)).toLocaleString('en-IN')} lakh`;
}

/** A move as "+1.23%" (from a fraction). */
export function movePct(r: number, digits = 2): string {
  const pct = r * 100;
  return `${pct > 0 ? '+' : ''}${pct.toFixed(digits)}%`;
}
