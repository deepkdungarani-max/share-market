export function ema(values: number[], period: number): number[] {
  const k = 2 / (period + 1);
  const out: number[] = [];
  values.forEach((v, i) => out.push(i === 0 ? v : v * k + out[i - 1] * (1 - k)));
  return out;
}

export function rsi(closes: number[], period = 14): number {
  let gains = 0;
  let losses = 0;
  for (let i = Math.max(1, closes.length - period); i < closes.length; i++) {
    const d = closes[i] - closes[i - 1];
    if (d > 0) gains += d;else
    losses -= d;
  }
  if (losses === 0) return gains === 0 ? 50 : 100;
  return 100 - 100 / (1 + gains / losses);
}

export function macd(closes: number[]): {line: number;signal: number;hist: number;} {
  const fast = ema(closes, 12);
  const slow = ema(closes, 26);
  const line = closes.map((_, i) => fast[i] - slow[i]);
  const signal = ema(line, 9);
  const n = closes.length - 1;
  return { line: line[n], signal: signal[n], hist: line[n] - signal[n] };
}