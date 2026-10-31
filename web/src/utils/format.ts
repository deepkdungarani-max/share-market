import type { Confidence } from '../types/market';

export function formatPrice(value: number, decimals: number): string {
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

export function formatPct(value: number): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

export function formatVolume(value: number): string {
  if (value >= 1e7) return `${(value / 1e7).toFixed(2)}Cr`;
  if (value >= 1e5) return `${(value / 1e5).toFixed(2)}L`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return String(Math.round(value));
}

const DAY = 1440;

export function timeframeLabel(minutes: number): string {
  if (minutes >= DAY && minutes % DAY === 0) {
    const d = minutes / DAY;
    return `${d} day${d > 1 ? 's' : ''}`;
  }
  if (minutes >= 60 && minutes % 60 === 0) {
    const h = minutes / 60;
    return `${h} hour${h > 1 ? 's' : ''}`;
  }
  return `${minutes} min`;
}

export function shortTimeframe(minutes: number): string {
  if (minutes >= DAY && minutes % DAY === 0) return `${minutes / DAY}D`;
  if (minutes >= 60 && minutes % 60 === 0) return `${minutes / 60}h`;
  return `${minutes}m`;
}

/** 24h clock; prefixes the weekday when the time is not today. */
export function formatClock(ms: number): string {
  const d = new Date(ms);
  const time = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
  if (d.toDateString() === new Date().toDateString()) return time;
  return `${d.toLocaleDateString('en-IN', { weekday: 'short' })} ${time}`;
}

/** When a candle starts: the date for daily bars, the clock time otherwise. */
export function formatCandleTime(ms: number, minutes: number): string {
  if (minutes >= DAY) return new Date(ms).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });
  return formatClock(ms);
}

export function agoLabel(ms: number): string {
  const mins = Math.max(0, Math.round((Date.now() - ms) / 60_000));
  if (mins < 60) return `${mins}m ago`;
  const h = Math.floor(mins / 60);
  if (h >= 24) return `${Math.floor(h / 24)}d ago`;
  const m = mins % 60;
  return m ? `${h}h ${m}m ago` : `${h}h ago`;
}

export function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor(total % 3600 / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

const confidenceLabels: Record<Confidence, string> = {
  High: 'Strong signal',
  Medium: 'Moderate signal',
  Low: 'Weak signal'
};

export function confidenceLabel(c: Confidence): string {
  return confidenceLabels[c];
}