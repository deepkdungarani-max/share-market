import { getJson } from './api';

/** Trikal's call on one symbol for the next session, with the inputs it was made from. */
export interface TrikalCall {
  symbol: string;
  market: 'stocks' | 'forex';
  /** The session the call was made on (its close is last_close); the call is for the one after. */
  as_of: string;
  /** In price: the close the call was made on, the latest 15-minute price, and where a typical day's move
   *  (median of the last 60) would take it. The models call the direction only, never the size. */
  last_close?: number;
  price?: number | null;
  typical_move?: number;
  up_to?: number;
  down_to?: number;
  prob_up: number;
  sanjay: number | null;
  chanakya: number | null;
  /** Drona's chance of closing up, and whether Trikal's call is Drona's (else Sanjay's and Chanakya's average). */
  drona?: number | null;
  drona_first?: boolean;
  /** Drona's call in full: why, what would prove it wrong, and the lessons it used. */
  drona_call?: DronaCall | null;
  /** Narad's notes on the symbol reaching this session (0 = none; null = before news collection began). */
  news_n: number | null;
  news_mean: number | null;
  market_news: number | null;
}

export interface DronaCall {
  prob_up: number;
  made_at: string;
  confidence: string;
  reasons: string[];
  risks: string[];
  lessons: {id: number;title: string;}[];
  /** Which plan wrote it, e.g. agy:gemini-3.8-flash-high. */
  writer: string;
}

/** Chitragupta's scorecard row for one model. */
export interface ScoreRow {
  model: string;
  calls: number;
  right_pct: number | null;
  /** Average move in the direction called, in % (beyond Nifty for news calls). */
  gain_pct: number | null;
}

export interface PastCall {
  session: string;
  symbol: string;
  market: 'stocks' | 'forex';
  prob_up: number;
  move: number;
  hit: number | null;
}

export interface Pipeline {
  news_24h: number;
  read_24h: number;
  unread: number;
  help_pending: number;
  help_answered_24h: number;
}

export interface TrikalView {
  /** Last finished session the call used; the call is for the session after it. */
  as_of: string | null;
  made_at: string | null;
  /** Probability added per unit of a stock's average news sentiment; 0 until news has proven itself. */
  news_weight: number;
  /** Whether Drona's call comes first in Trikal right now, and why (its record against the models' average). */
  drona?: {first: boolean;why: string;};
  calls: TrikalCall[];
  scorecard: ScoreRow[];
  past: PastCall[];
  pipeline: Pipeline;
}

export const fetchTrikal = (signal?: AbortSignal) => getJson<TrikalView>('/trikal', signal);

/** "Wed, 28 Oct" for a YYYY-MM-DD session date. */
export function formatSession(day: string): string {
  return new Date(`${day}T00:00:00`).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });
}
