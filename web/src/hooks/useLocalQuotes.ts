import { useEffect, useState } from 'react';
import { fetchLocalQuotes, type Quote } from '../utils/marketData';

const POLL_MS = 60_000;

interface QuotesState {
  data: Record<string, Quote> | null;
  error: string | null;
}

/** Live last price / day change / today's closes per symbol from the local DB. */
export function useLocalQuotes(enabled: boolean): QuotesState {
  const [state, setState] = useState<QuotesState>({ data: null, error: null });

  useEffect(() => {
    if (!enabled) return;
    const ctrl = new AbortController();
    const load = () =>
    fetchLocalQuotes(ctrl.signal).
    then((data) => setState({ data, error: null })).
    catch((err: unknown) => {
      if (ctrl.signal.aborted) return;
      setState((prev) => ({ ...prev, error: err instanceof Error ? err.message : 'Could not load prices' }));
    });
    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      ctrl.abort();
      clearInterval(id);
    };
  }, [enabled]);

  return state;
}
