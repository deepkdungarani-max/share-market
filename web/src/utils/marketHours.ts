import type { Market, MarketStatus } from '../types/market';

const DAY = 86_400_000;
const MIN = 60_000;
const IST = 330 * MIN;
const NSE_OPEN = 9 * 60 + 15;
const NSE_CLOSE = 15 * 60 + 30;
const INR_OPEN = 9 * 60; // Indian banking hours, when the rupee pairs really trade (IST)
const INR_CLOSE = 17 * 60;
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const isWeekday = (dow: number) => dow >= 1 && dow <= 5;

function nseStatus(now: number): MarketStatus {
  const midnight = Math.floor((now + IST) / DAY) * DAY - IST;
  const dowAt = (ms: number) => new Date(ms + IST).getUTCDay();
  const mins = Math.floor((now - midnight) / MIN);
  const open = isWeekday(dowAt(midnight)) && mins >= NSE_OPEN && mins < NSE_CLOSE;

  if (open) return { open, label: 'NSE open', detail: 'closes 15:30 IST', lastActive: now };

  let lastActive = now;
  for (let k = 0; k < 8; k++) {
    const close = midnight - k * DAY + NSE_CLOSE * MIN;
    if (isWeekday(dowAt(midnight - k * DAY)) && close <= now) {
      lastActive = close;
      break;
    }
  }
  let detail = '';
  for (let k = 0; k < 8; k++) {
    const day = midnight + k * DAY;
    if (isWeekday(dowAt(day)) && day + NSE_OPEN * MIN > now) {
      detail = `opens ${k === 0 ? 'today' : k === 1 ? 'tomorrow' : WEEKDAYS[dowAt(day)]} 09:15 IST`;
      break;
    }
  }
  return { open, label: 'NSE closed', detail, lastActive };
}

function forexStatus(now: number): MarketStatus {
  const d = new Date(now);
  const dow = d.getUTCDay();
  const mins = d.getUTCHours() * 60 + d.getUTCMinutes();
  const closed = dow === 5 && mins >= 1320 || dow === 6 || dow === 0 && mins < 1320;
  if (!closed) {
    // The rupee trades mainly while Indian banks and NSE's currency segment are open: outside those hours the
    // global market is open, but USD/INR barely moves (flat candles all night)
    const ist = new Date(now + IST);
    const istMins = ist.getUTCHours() * 60 + ist.getUTCMinutes();
    const rupeeActive = isWeekday(ist.getUTCDay()) && istMins >= INR_OPEN && istMins < INR_CLOSE;
    return {
      open: true,
      label: 'Forex open',
      detail: rupeeActive ? 'rupee most active till 17:00 IST' : 'rupee quiet outside 09:00–17:00 IST',
      lastActive: now
    };
  }

  const midnight = Math.floor(now / DAY) * DAY;
  const daysSinceFri = (dow + 2) % 7;
  return {
    open: false,
    label: 'Forex closed',
    detail: 'opens Sun 22:00 UTC',
    lastActive: midnight - daysSinceFri * DAY + 1320 * MIN
  };
}

export function marketStatus(market: Market, now = Date.now()): MarketStatus {
  return market === 'stocks' ? nseStatus(now) : forexStatus(now);
}