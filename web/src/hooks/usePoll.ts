import { useEffect, useState } from 'react';

/** Loads now and every `ms`, keeping the last good data if a later poll fails. Starts over when `deps` change. */
export function usePoll<T>(fetcher: (signal: AbortSignal) => Promise<T>, ms: number, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    const load = () =>
    fetcher(ctrl.signal).
    then((d) => {
      setData(d);
      setError(null);
    }).
    catch((err: unknown) => !ctrl.signal.aborted && setError(err instanceof Error ? err.message : 'Not available'));
    load();
    const id = setInterval(load, ms);
    return () => {
      ctrl.abort();
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error };
}
