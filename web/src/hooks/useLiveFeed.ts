import { useCallback, useEffect, useState } from 'react';
import { barSize, fetchLocalCandles, sessionClose } from '../utils/marketData';
import { generateCandles } from '../utils/prediction';
import type { Candle, FeedStatus, Instrument, MarketStatus } from '../types/market';

interface FeedState {
  candles: Candle[];
  forming: Candle | null;
  status: FeedStatus;
  error: string | null;
}

/**
 * Never displayed: keeps the candle arrays non-empty until the first real candles arrive.
 * The UI shows a loader (or an error) instead of anything built from these.
 */
function placeholder(instrument: Instrument, minutes: number): FeedState {
  const step = minutes * 60_000;
  return { candles: generateCandles(instrument, minutes, Math.floor(Date.now() / step) * step), forming: null, status: 'loading', error: null };
}

/** Live NSE candles for ONE instrument from the local backend; polls every 15s while the market is open. */
export function useLiveFeed(instrument: Instrument, minutes: number, status: MarketStatus) {
  const isOpen = status.open;
  const barMinutes = barSize(minutes);
  const step = barMinutes * 60_000;
  const [state, setState] = useState<FeedState>(() => placeholder(instrument, barMinutes));
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((a) => a + 1), []);

  useEffect(() => {
    const ctrl = new AbortController();
    setState(placeholder(instrument, barMinutes));

    const load = async () => {
      try {
        const candles = await fetchLocalCandles(instrument.symbol, barMinutes, ctrl.signal);
        setState({
          // While open, the newest bar is still forming
          candles: isOpen ? candles.slice(0, -1) : candles.slice(-48),
          forming: isOpen ? candles[candles.length - 1] : null,
          status: 'live',
          error: null
        });
      } catch (err) {
        if (ctrl.signal.aborted) return;
        const message = err instanceof Error ? err.message : 'Could not load market data';
        // Keep showing the last real candles if a later refresh fails
        setState((prev) => prev.status === 'live' ? { ...prev, error: message } : { ...prev, status: 'error', error: message });
      }
    };

    load();
    const poll = isOpen ? setInterval(load, 15_000) : undefined;
    return () => {
      ctrl.abort();
      if (poll) clearInterval(poll);
    };
  }, [instrument, barMinutes, isOpen, attempt]);

  const last = state.candles[state.candles.length - 1];
  return {
    ...state,
    barMinutes,
    price: state.forming?.close ?? last.close,
    closesAt: state.forming ? Math.min(state.forming.time + step, sessionClose(state.forming.time)) : null,
    retry
  };
}
