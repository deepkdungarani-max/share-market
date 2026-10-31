import type { Candle, Direction, HistoryEntry, Market } from '../types/market';

/** Bar sizes the local models were trained on (15m, 1h, 1 day). */
export const BAR_SIZES = [15, 60, 1440];

const IST_OFFSET = 330 * 60_000;

/** 15:30 IST on the trading day that contains `ms`: no candle stays open past the session close. */
export function sessionClose(ms: number): number {
  const day = Math.floor((ms + IST_OFFSET) / 86_400_000) * 86_400_000;
  return day + 15.5 * 3_600_000 - IST_OFFSET;
}

/** Base path of the candlecast Python backend (app/server.py); same origin as the UI. */
export const LOCAL_API = '/api';

/** Snap any minutes value to the nearest bar size the backend serves. */
export function barSize(minutes: number): number {
  return BAR_SIZES.reduce((best, m) => Math.abs(m - minutes) < Math.abs(best - minutes) ? m : best, BAR_SIZES[0]);
}

export async function fetchLocalCandles(symbol: string, minutes: number, signal: AbortSignal): Promise<Candle[]> {
  const params = new URLSearchParams({ symbol, minutes: String(minutes) });
  const res = await fetch(`${LOCAL_API}/candles?${params.toString()}`, { signal }).catch(() => {
    throw new Error('backend not reachable — is start.bat running?');
  });
  const json = await res.json().catch(() => null);
  if (!res.ok) throw new Error(json?.detail ?? `backend returned ${res.status}`);
  return json as Candle[];
}

/** Your model's saved calls for this symbol, scored against what happened. Newest first. */
export async function fetchLocalHistory(symbol: string, minutes: number, signal: AbortSignal): Promise<HistoryEntry[]> {
  const params = new URLSearchParams({ symbol, minutes: String(minutes) });
  const res = await fetch(`${LOCAL_API}/history?${params.toString()}`, { signal });
  if (!res.ok) throw new Error(`backend returned ${res.status}`);
  return res.json();
}

export interface Quote {
  price: number;
  changePct: number;
  /** Today's 15m closes, oldest first. */
  closes: number[];
}

export async function fetchLocalQuotes(signal: AbortSignal): Promise<Record<string, Quote>> {
  const res = await fetch(`${LOCAL_API}/quotes`, { signal }).catch(() => {
    throw new Error('backend not reachable — is start.bat running?');
  });
  if (!res.ok) throw new Error(`backend returned ${res.status}`);
  return res.json();
}

export interface RemotePrediction {
  direction: Direction;
  probability: number;
}

/** POSTs { symbol, market, minutes, candles } and expects { direction: 'up' | 'down', probability: 0–100 }. */
export async function fetchRemotePrediction(
endpoint: string,
payload: {symbol: string;market: Market;minutes: number;candles: Candle[];},
signal: AbortSignal)
: Promise<RemotePrediction> {
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal
  });
  if (!res.ok) throw new Error(`Model returned ${res.status}`);
  const json: {direction?: unknown;probability?: unknown;} = await res.json();
  if (json.direction !== 'up' && json.direction !== 'down' || typeof json.probability !== 'number') {
    throw new Error('Model response must be { direction, probability }');
  }
  return { direction: json.direction, probability: json.probability };
}
