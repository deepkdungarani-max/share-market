import { useEffect, useMemo, useRef, useState } from 'react';
import { useLiveFeed } from './useLiveFeed';
import { fetchLocalHistory, fetchRemotePrediction, LOCAL_API, type RemotePrediction } from '../utils/marketData';
import { predictNext, withRemote } from '../utils/prediction';
import type { HistoryEntry, Instrument, Market, MarketStatus, ModelSource, Prediction } from '../types/market';

interface UsePredictionArgs {
  instrument: Instrument;
  market: Market;
  minutes: number;
  status: MarketStatus;
}

/** Runs your model for ONE instrument only, re-running each time a candle closes. */
export function usePrediction({ instrument, market, minutes, status }: UsePredictionArgs) {
  const feed = useLiveFeed(instrument, minutes, status);
  const { candles, barMinutes } = feed;
  const ready = feed.status === 'live';
  const lastTime = candles[candles.length - 1].time;

  // Indicator readings for the "what the indicators say" panel and trade levels
  const indicators = useMemo(() => predictNext(instrument, barMinutes, candles), [instrument, barMinutes, candles]);

  const [remote, setRemote] = useState<(RemotePrediction & {key: number;}) | null>(null);
  const [modelError, setModelError] = useState<string | null>(null);
  const candlesRef = useRef(candles);
  candlesRef.current = candles;

  useEffect(() => {
    if (!ready) return;
    const ctrl = new AbortController();
    fetchRemotePrediction(`${LOCAL_API}/predict`, { symbol: instrument.symbol, market, minutes: barMinutes, candles: candlesRef.current }, ctrl.signal).
    then((r) => {
      setRemote({ ...r, key: lastTime });
      setModelError(null);
    }).
    catch((err: unknown) => {
      if (ctrl.signal.aborted) return;
      setRemote(null);
      setModelError(err instanceof Error ? err.message : 'Model request failed');
    });
    return () => ctrl.abort();
  }, [ready, instrument.symbol, market, barMinutes, lastTime]);

  const useRemote = remote !== null && remote.key === lastTime;
  const prediction = useMemo<Prediction>(
    () => useRemote && remote ? withRemote(indicators, remote) : indicators,
    [useRemote, remote, indicators]
  );
  const modelSource: ModelSource = useRemote ? 'remote' : 'local';

  // Past calls are your model's saved predictions, scored by the DB — refetch whenever a new one lands
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  useEffect(() => {
    if (!ready) return;
    const ctrl = new AbortController();
    fetchLocalHistory(instrument.symbol, barMinutes, ctrl.signal).then(setHistory).catch(() => undefined);
    return () => ctrl.abort();
  }, [ready, instrument.symbol, barMinutes, lastTime, remote?.key]);

  const [flash, setFlash] = useState(true);
  useEffect(() => {
    setFlash(true);
    const timer = setTimeout(() => setFlash(false), 250);
    return () => clearTimeout(timer);
  }, [instrument.symbol, minutes]);

  return {
    candles,
    forming: feed.forming,
    price: feed.price,
    change: { pct: (feed.price - candles[0].open) / candles[0].open * 100, label: `${candles.length} bars` },
    closesAt: feed.closesAt,
    barMinutes,
    ready,
    feedStatus: feed.status,
    feedError: feed.error,
    retry: feed.retry,
    prediction,
    modelSource,
    modelError,
    history,
    loading: flash || !ready
  };
}
