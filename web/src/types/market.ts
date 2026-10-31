export type Market = 'stocks' | 'forex';
export type Direction = 'up' | 'down';
export type Confidence = 'High' | 'Medium' | 'Low';
export type FeedStatus = 'loading' | 'live' | 'error';
export type ModelSource = 'local' | 'remote';

export interface Instrument {
  symbol: string;
  name: string;
  price: number;
  changePct: number;
  volatility: number;
  decimals: number;
}

export interface Candle {
  /** Candle start time, epoch ms. */
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/** One input the model weighed. impact: -1 (pushes DOWN) … +1 (pushes UP). */
export interface Factor {
  id: string;
  label: string;
  reading: string;
  impact: number;
  weight: number;
}

export interface Prediction {
  direction: Direction;
  probability: number;
  expectedMovePct: number;
  confidence: Confidence;
  candle: Candle;
  stopLoss: number;
  riskReward: number;
  factors: Factor[];
}

export interface ModelInfo {
  name: string;
  accuracy: number;
  lookback: string;
}

/** What the model called for a candle that has already closed, vs what actually happened. */
export interface HistoryEntry {
  start: number;
  end: number;
  predicted: Direction;
  probability: number;
  /** flat: the close didn't change, so the call is neither right nor wrong. */
  actual: Direction | 'flat';
  /** Close-to-close change, %. */
  movePct: number;
  /** null when the price didn't move. */
  hit: boolean | null;
  /** The close before this candle, this candle's close, and its high and low. */
  prevClose: number;
  close: number;
  high: number;
  low: number;
  /** How far it went up (high) and down (low) from the close before, %. */
  highPct: number;
  lowPct: number;
}

export interface PriceAlert {
  id: string;
  market: Market;
  symbol: string;
  threshold: number;
  direction: Direction | 'any';
  lastFiredKey: string | null;
}


export interface MarketStatus {
  open: boolean;
  label: string;
  detail: string;
  /** When open: now. When closed: the moment the last session ended. */
  lastActive: number;
}