import { useEffect, useState } from 'react';
import { barSize, LOCAL_API } from '../utils/marketData';
import type { Market, ModelInfo } from '../types/market';

interface LocalModels {
  [interval: string]: {name: string;accuracy: number | null;confident_accuracy: number | null;};
}

/** Name + walk-forward accuracy of the trained model the backend uses for this market and bar size. null = not available. */
export function useLocalModelInfo(minutes: number, market: Market): ModelInfo | null {
  const [models, setModels] = useState<LocalModels | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${LOCAL_API}/models?market=${market}`, { signal: ctrl.signal }).
    then((r) => r.ok ? r.json() : null).
    then(setModels).
    catch(() => setModels(null));
    return () => ctrl.abort();
  }, [market]);

  if (!models) return null;
  const interval = ({ 60: '1h', 1440: '1d' } as Record<number, string>)[barSize(minutes)] ?? '15m';
  const m = models[interval];
  if (!m || m.accuracy == null) return null;
  return {
    name: `LightGBM ${market === 'forex' ? 'INR pairs ' : ''}${interval} (yours)`,
    accuracy: Math.round(m.accuracy * 10) / 10,
    lookback: `calls ≥55% sure: ${m.confident_accuracy ?? '–'}% right`
  };
}
