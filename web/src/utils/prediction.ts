import { ema, macd, rsi } from './indicators';
import { formatPct } from './format';
import type {
  Candle,
  Confidence,
  Direction,
  Factor,
  HistoryEntry,
  Instrument,
  Prediction } from
'../types/market';

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export function scaleFor(minutes: number): number {
  return Math.sqrt(Math.max(1, minutes) / 15);
}

export function seededRandom(seed: string): () => number {
  let h = 1779033703 ^ seed.length;
  for (let i = 0; i < seed.length; i++) {
    h = Math.imul(h ^ seed.charCodeAt(i), 3432918353);
    h = h << 13 | h >>> 19;
  }
  let a = h >>> 0;
  return () => {
    a = a + 0x6d2b79f5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

/** Typical traded volume per candle (shares for stocks, ticks for forex). */
export function baseVolume(instrument: Instrument, minutes: number): number {
  const per15 = instrument.symbol.includes('/') ? 2000 : 2e8 / instrument.price;
  return per15 * minutes / 15;
}

/** Demo candles. `anchor` = start time of the candle right after the last one returned. */
export function generateCandles(instrument: Instrument, minutes: number, anchor: number, count = 48): Candle[] {
  const rand = seededRandom(`${instrument.symbol}-${minutes}`);
  const vol = instrument.volatility * scaleFor(minutes);
  const step = minutes * 60_000;
  const base = baseVolume(instrument, minutes);
  let price = instrument.price;
  const raw: Candle[] = [];
  let trend = (rand() - 0.5) * vol * 0.6;

  for (let i = 0; i < count; i++) {
    if (i % 12 === 0) trend = (rand() - 0.5) * vol * 0.8;
    const open = price;
    const close = open * (1 + trend + (rand() - 0.5) * 2 * vol);
    const high = Math.max(open, close) * (1 + rand() * vol * 0.7);
    const low = Math.min(open, close) * (1 - rand() * vol * 0.7);
    const ret = Math.abs(close - open) / open;
    const volume = Math.round(base * (0.55 + rand() * 0.7) * (1 + Math.min(2, ret / vol) * 0.6));
    raw.push({ time: anchor - (count - i) * step, open, high, low, close, volume });
    price = close;
  }

  const ratio = instrument.price / price;
  return raw.map((c) => ({ ...c, open: c.open * ratio, high: c.high * ratio, low: c.low * ratio, close: c.close * ratio }));
}

export function computeFactors(candles: Candle[], vol: number, decimals: number): Factor[] {
  const closes = candles.map((c) => c.close);
  const last = candles[candles.length - 1];
  const unit = last.close * vol || 1;

  const r = rsi(closes);
  const rsiImpact = r > 70 ? -(r - 70) / 30 : r < 30 ? (30 - r) / 30 : (r - 50) / 20 * 0.5;

  const m = macd(closes);
  const e9 = ema(closes, 9);
  const e21 = ema(closes, 21);
  const trendGap = e9[e9.length - 1] - e21[e21.length - 1];

  const prior = candles.slice(-21, -1).map((c) => c.volume);
  const avgVol = prior.reduce((a, b) => a + b, 0) / Math.max(1, prior.length);
  const volRatio = avgVol ? last.volume / avgVol : 1;
  const lastDir = last.close >= last.open ? 1 : -1;

  const first = candles[Math.max(0, candles.length - 8)];
  const momentum = (last.close - first.open) / first.open;

  return [
  {
    id: 'trend',
    label: 'Trend',
    reading: `EMA 9 ${trendGap >= 0 ? 'above' : 'below'} EMA 21`,
    impact: clamp(trendGap / unit * 0.8, -1, 1),
    weight: 0.3
  },
  {
    id: 'macd',
    label: 'MACD',
    reading: `hist ${m.hist >= 0 ? '+' : ''}${m.hist.toFixed(decimals)}`,
    impact: clamp(m.hist / unit * 2.5, -1, 1),
    weight: 0.25
  },
  {
    id: 'rsi',
    label: 'RSI 14',
    reading: `${r.toFixed(0)} · ${r > 70 ? 'overbought' : r < 30 ? 'oversold' : 'neutral'}`,
    impact: clamp(rsiImpact, -1, 1),
    weight: 0.2
  },
  {
    id: 'momentum',
    label: 'Momentum',
    reading: `${formatPct(momentum * 100)} / 8 bars`,
    impact: clamp(momentum / (vol * 3), -1, 1),
    weight: 0.15
  },
  {
    id: 'volume',
    label: 'Volume',
    reading: `${volRatio.toFixed(1)}× 20-bar avg`,
    impact: clamp((volRatio - 1) * lastDir * 0.7, -1, 1),
    weight: 0.1
  }];

}

function confidenceFor(probability: number): Confidence {
  return probability >= 70 ? 'High' : probability >= 60 ? 'Medium' : 'Low';
}

/**
 * Built-in indicator engine. Swap this for your own model, or set a model endpoint in
 * Settings — the remote answer overrides direction & probability (see withRemote).
 */
export function predictNext(instrument: Instrument, minutes: number, candles: Candle[]): Prediction {
  const last = candles[candles.length - 1];
  const vol = instrument.volatility * scaleFor(minutes);
  const factors = computeFactors(candles, vol, instrument.decimals);
  const signal = factors.reduce((s, f) => s + f.impact * f.weight, 0);
  const score = clamp(0.5 + signal * 0.45, 0.02, 0.98);
  const direction: Direction = score >= 0.5 ? 'up' : 'down';
  const probability = Math.round(clamp(51 + Math.abs(score - 0.5) * 80, 51, 84));

  // No model predicts how far the price goes, only which way: the target is this stock's typical
  // candle-to-candle move (median of the last 20) in the called direction, so it comes from real data.
  const recent21 = candles.slice(-21).map((c) => c.close);
  const changes = recent21.slice(1).map((c, i) => Math.abs(c - recent21[i])).sort((a, b) => a - b);
  const move = changes[Math.floor(changes.length / 2)] || last.close * vol;
  const sign = direction === 'up' ? 1 : -1;
  const open = last.close;
  const close = open + sign * move;
  const high = Math.max(open, close) + move * 0.3;
  const low = Math.min(open, close) - move * 0.3;

  const recent = candles.slice(-14);
  const atr = recent.reduce((s, c) => s + (c.high - c.low), 0) / recent.length;
  const stopDist = clamp(atr * 0.9, move * 0.5, move * 1.2);

  return {
    direction,
    probability,
    expectedMovePct: move / open * 100,
    confidence: confidenceFor(probability),
    candle: { time: last.time + minutes * 60_000, open, high, low, close, volume: 0 },
    stopLoss: open - sign * stopDist,
    riskReward: move / stopDist,
    factors
  };
}

/** Applies a remote model's direction/probability, mirroring the price levels if it disagrees. */
export function withRemote(p: Prediction, remote: {direction: Direction;probability: number;}): Prediction {
  const probability = Math.round(clamp(remote.probability, 0, 100));
  if (remote.direction === p.direction) return { ...p, probability, confidence: confidenceFor(probability) };
  const o = p.candle.open;
  return {
    ...p,
    direction: remote.direction,
    probability,
    confidence: confidenceFor(probability),
    candle: { ...p.candle, close: 2 * o - p.candle.close, high: 2 * o - p.candle.low, low: 2 * o - p.candle.high },
    stopLoss: 2 * o - p.stopLoss
  };
}

export function historyEntry(prediction: Prediction, closed: Candle, minutes: number): HistoryEntry {
  const actual: Direction = closed.close >= closed.open ? 'up' : 'down';
  return {
    start: closed.time,
    end: closed.time + minutes * 60_000,
    predicted: prediction.direction,
    probability: prediction.probability,
    actual,
    movePct: (closed.close - closed.open) / closed.open * 100,
    hit: actual === prediction.direction,
    prevClose: closed.open,
    close: closed.close,
    high: closed.high,
    low: closed.low,
    highPct: (closed.high - closed.open) / closed.open * 100,
    lowPct: (closed.low - closed.open) / closed.open * 100
  };
}

/** Real backtest: re-runs the model on the data available before each of the last `count` candles. Newest first. */
export function predictionHistory(instrument: Instrument, minutes: number, candles: Candle[], count = 12): HistoryEntry[] {
  const entries: HistoryEntry[] = [];
  const from = Math.max(10, candles.length - count);
  for (let i = from; i < candles.length; i++) {
    entries.push(historyEntry(predictNext(instrument, minutes, candles.slice(0, i)), candles[i], minutes));
  }
  return entries.reverse();
}