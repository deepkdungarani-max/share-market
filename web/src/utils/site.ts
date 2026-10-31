import { getJson, sendJson } from './api';
import type { Pipeline, ScoreRow, TrikalCall } from './trikal';

export type ModelState = 'ok' | 'waiting' | 'late' | 'down' | 'off';

/** Whether one model did its job on schedule (see app/overview.py). */
export interface ModelHealth {
  key: string;
  name: string;
  role: string;
  state: ModelState;
  /** ISO time of its last activity. */
  last: string | null;
  detail: string;
}

export interface DronaAnswer {
  sentiment: number;
  confidence: number;
  reason: string;
}

/** One of Narad's notes, with Drona's answer when Narad asked for help. */
export interface Note {
  id: number;
  source: string;
  title: string;
  url: string;
  /** SQLite UTC time the news was published. */
  published: string | null;
  about: string;
  symbols: string[];
  event: string;
  positives: string[];
  negatives: string[];
  sentiment: number;
  confidence: number;
  help: {reason: string;status: string;answer: DronaAnswer | null;} | null;
}

export interface Overview {
  models: ModelHealth[];
  as_of: string | null;
  made_at: string | null;
  strongest: TrikalCall[];
  scorecard: ScoreRow[];
  pipeline: Pipeline;
  headlines: Note[];
}

export interface NewsFeed {
  notes: Note[];
  /** Collected items by status: new, read, duplicate, failed. */
  news: Record<string, number>;
  /** Help requests by status: pending, answered, skipped. */
  help: Record<string, number>;
  tracked: string[];
}

export interface World {
  as_of: string | null;
  made_at: string | null;
  /** Each overnight series' last change (sp500_ret …) and India VIX's level. */
  cues: Record<string, number>;
  trained_on: number | null;
  tickers: Record<string, string>;
  calls: {symbol: string;prob_up: number;market: 'stocks' | 'forex';}[];
}

export interface EventScore extends ScoreRow {
  event: string;
}

export interface ScoredCall {
  model: string;
  symbol: string;
  session: string;
  said: number;
  move: number;
  outcome: number;
  hit: number | null;
  title: string | null;
}

export interface Scores {
  total: number;
  models: ScoreRow[];
  events: EventScore[];
  calibration: {band: string;calls: number;right_pct: number | null;}[];
  recent: ScoredCall[];
}

export interface Mistakes {
  studying: {id: number;title: string;why: string | null;status: string;learned_at: string | null;}[];
  checked: {question: string;answer: string;}[];
}

/** Sanjay's daily call for the next session, and its daily model's walk-forward test. */
export interface SanjayView {
  as_of: string | null;
  made_at: string | null;
  calls: {symbol: string;prob_up: number;}[];
  accuracy: number | null;
  confident_accuracy: number | null;
  confident_share: number | null;
}

/** One cloud key Narad reads with, and what it has done since the server started. */
export interface KeyReader {
  id: string;
  name: string;
  /** An API key's provider, or an AI plan: agy / agy2 (Google AI Pro account 1 / 2), codex (ChatGPT). */
  provider: Provider | 'agy' | 'agy2' | 'codex';
  /** ISO time the key was added (null for an AI plan). */
  added: string | null;
  /** Last 4 characters of the key, so you can tell keys apart; the key itself never leaves the server. */
  hint: string;
  batch: number;
  state: 'reading' | 'resting' | 'paused';
  rests_for: number;
  requests: number;
  items: number;
  failures: number;
  model: string | null;
  last_ok: string | null;
  last_error: string | null;
  /** What is left of the key's limits, as its provider reported on the last reply (Groq only; Gemini doesn't say). */
  limits: {requests_left: string | null;requests_limit: string | null;requests_reset: string | null;tokens_left: string | null;tokens_limit: string | null;} | null;
}

export interface Readers {
  keys: KeyReader[];
  ollama: {model: string;state: 'off' | 'standby' | 'reading';};
  per_model: {model: string;notes: number;}[];
}

export const fetchOverview = (signal?: AbortSignal) => getJson<Overview>('/overview', signal);
export type Provider = 'gemini' | 'groq' | 'openrouter';

/** Calls, successful calls, calls that hit the usage limit, and tokens, over a window. */
export interface WriterWindow {
  calls: number;
  ok: number;
  limits: number;
  tokens: number;
}

/** One of Drona's writers: agy:<model> / agy2:<model> (Google AI Pro account 1 / 2), codex:<model> (ChatGPT Pro). */
export interface WriterUse {
  writer: string;
  /** "Google AI Pro · account 1", "ChatGPT Pro"… */
  plan: string;
  /** Account it is signed in as, when known. */
  account: string | null;
  /** working: writing something now; ready: standby; resting: out of quota until it resets; off: plan not set up. */
  state: 'working' | 'ready' | 'resting' | 'off';
  /** What it is writing right now (state working): lesson | help | answer, the topic, seconds so far, and how
   *  many seconds such a job usually takes (null with no record yet). */
  now: {kind: string;what: string;for: number;usual: number | null;} | null;
  rests_for: number;
  day: WriterWindow;
  week: WriterWindow;
  /** Successful calls in 24 h by kind: lesson, help, answer. */
  kinds: Record<string, number>;
  last_ok: string | null;
  last_error: string | null;
  last_error_at: string | null;
}

export interface Writers {
  writers: WriterUse[];
}

export const fetchWriters = (signal?: AbortSignal) => getJson<Writers>('/writers', signal);

export const fetchReaders = (signal?: AbortSignal) => getJson<Readers>('/readers', signal);
/** The server checks the key with its provider before storing it, and starts reading with it at once. */
export const addKey = (provider: Provider, key: string, name: string) =>
sendJson<KeyReader>('POST', '/keys', { provider, key, name });
export const pauseKey = (id: string, paused: boolean) =>
sendJson<{id: string;paused: boolean;}>('POST', `/keys/${id}/pause`, { paused });
export const removeKey = (id: string) => sendJson<{removed: string;}>('DELETE', `/keys/${id}`);
export const fetchSanjay = (market: string, signal?: AbortSignal) => getJson<SanjayView>(`/sanjay?market=${market}`, signal);
export const fetchNews = (scope: string, symbol: string, signal?: AbortSignal) =>
getJson<NewsFeed>(`/news?${new URLSearchParams({ scope, symbol, limit: '300' }).toString()}`, signal);
export const fetchWorld = (signal?: AbortSignal) => getJson<World>('/world', signal);
export const fetchScores = (signal?: AbortSignal) => getJson<Scores>('/scores', signal);
export const fetchMistakes = (signal?: AbortSignal) => getJson<Mistakes>('/teacher/mistakes', signal);

/** "results_beat" -> "results beat". */
export function eventLabel(event: string): string {
  return event.replace(/_/g, ' ');
}

/** One thing Krishna found wrong in its last check. */
export interface KrishnaFinding {
  area: string;
  /** problem: something stopped; warning: working, but worse than it should; info. */
  level: 'problem' | 'warning' | 'info';
  message: string;
  /** What to do about it, when it isn't something Krishna fixes itself. */
  todo: string | null;
}

/** Krishna's daily review of the team. */
export interface KrishnaReview {
  day: string;
  summary: string;
  advice: {model: string;advice: string;}[];
  study: {title: string;why?: string;}[];
  /** The study topics that were new to Drona's queue. */
  queued: string[];
  writer: string;
  at: string;
}

export interface Krishna {
  checked_at: string | null;
  findings: KrishnaFinding[];
  /** Newest first: problems found, fixes made, problems gone, reviews. */
  log: {kind: 'problem' | 'warning' | 'fixed' | 'resolved' | 'review';area: string;message: string;at: string;}[];
  review: KrishnaReview | null;
}

export const fetchKrishna = (signal?: AbortSignal) => getJson<Krishna>('/krishna', signal);
export const krishnaCheck = () => sendJson<Krishna>('POST', '/krishna/check');
export const krishnaReview = () => sendJson<Krishna>('POST', '/krishna/review');
