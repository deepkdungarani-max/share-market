import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { maxMinutesByMarket } from '../data/instruments';
import { marketStatus } from '../utils/marketHours';
import type { Market, MarketStatus } from '../types/market';

interface MarketState {
  market: Market;
  setMarket: (market: Market) => void;
  /** Only ONE symbol per market — the model runs for this share alone. null = nothing chosen yet. */
  selected: Record<Market, string | null>;
  select: (symbol: string) => void;
  clear: () => void;
  minutes: number;
  setMinutes: (minutes: number) => void;
  status: MarketStatus;
}

const MarketContext = createContext<MarketState | null>(null);

export function MarketProvider({ children }: {children: React.ReactNode;}) {
  const [market, setMarketState] = useState<Market>('stocks');
  const [selected, setSelected] = useState<Record<Market, string | null>>({ stocks: null, forex: null });
  const [minutes, setMinutes] = useState(15);
  const [status, setStatus] = useState<MarketStatus>(() => marketStatus('stocks'));

  useEffect(() => {
    const update = () =>
    setStatus((prev) => {
      const next = marketStatus(market);
      // keep identity stable while open so the live feed doesn't reset every tick
      return prev.open === next.open && prev.label === next.label && (next.open || prev.lastActive === next.lastActive) ?
      prev :
      next;
    });
    setStatus(marketStatus(market));
    const id = setInterval(update, 30_000);
    return () => clearInterval(id);
  }, [market]);

  const setMarket = useCallback((next: Market) => {
    setMarketState(next);
    setMinutes((m) => Math.min(m, maxMinutesByMarket[next]));
  }, []);

  const select = useCallback((symbol: string) => setSelected((prev) => ({ ...prev, [market]: symbol })), [market]);
  const clear = useCallback(() => setSelected((prev) => ({ ...prev, [market]: null })), [market]);

  const value = useMemo(
    () => ({ market, setMarket, selected, select, clear, minutes, setMinutes, status }),
    [market, setMarket, selected, select, clear, minutes, status]
  );

  return <MarketContext.Provider value={value}>{children}</MarketContext.Provider>;
}

export function useMarket(): MarketState {
  const ctx = useContext(MarketContext);
  if (!ctx) throw new Error('useMarket must be used inside MarketProvider');
  return ctx;
}