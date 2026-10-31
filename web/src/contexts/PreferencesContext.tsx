import React, { createContext, useCallback, useContext, useMemo } from 'react';
import { useLocalStorage } from '../hooks/useLocalStorage';
import type { Market, PriceAlert } from '../types/market';

type SymbolLists = Record<Market, string[]>;

interface PreferencesState {
  watchlist: SymbolLists;
  toggleWatch: (market: Market, symbol: string) => void;
  recent: SymbolLists;
  pushRecent: (market: Market, symbol: string) => void;
  alerts: PriceAlert[];
  addAlert: (alert: Omit<PriceAlert, 'id' | 'lastFiredKey'>) => void;
  removeAlert: (id: string) => void;
  markFired: (id: string, key: string) => void;
}

const empty: SymbolLists = { stocks: [], forex: [] };
const PreferencesContext = createContext<PreferencesState | null>(null);

export function PreferencesProvider({ children }: {children: React.ReactNode;}) {
  const [watchlist, setWatchlist] = useLocalStorage<SymbolLists>('candlecast:watchlist', empty);
  const [recent, setRecent] = useLocalStorage<SymbolLists>('candlecast:recent', empty);
  const [alerts, setAlerts] = useLocalStorage<PriceAlert[]>('candlecast:alerts', []);

  const toggleWatch = useCallback(
    (market: Market, symbol: string) =>
    setWatchlist((prev) => ({
      ...prev,
      [market]: prev[market].includes(symbol) ? prev[market].filter((s) => s !== symbol) : [...prev[market], symbol]
    })),
    [setWatchlist]
  );

  const pushRecent = useCallback(
    (market: Market, symbol: string) =>
    setRecent((prev) => ({ ...prev, [market]: [symbol, ...prev[market].filter((s) => s !== symbol)].slice(0, 6) })),
    [setRecent]
  );

  const addAlert = useCallback(
    (alert: Omit<PriceAlert, 'id' | 'lastFiredKey'>) =>
    setAlerts((prev) => [...prev, { ...alert, id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, lastFiredKey: null }]),
    [setAlerts]
  );
  const removeAlert = useCallback((id: string) => setAlerts((prev) => prev.filter((a) => a.id !== id)), [setAlerts]);
  const markFired = useCallback(
    (id: string, key: string) => setAlerts((prev) => prev.map((a) => a.id === id ? { ...a, lastFiredKey: key } : a)),
    [setAlerts]
  );

  const value = useMemo(
    () => ({ watchlist, toggleWatch, recent, pushRecent, alerts, addAlert, removeAlert, markFired }),
    [watchlist, toggleWatch, recent, pushRecent, alerts, addAlert, removeAlert, markFired]
  );

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences(): PreferencesState {
  const ctx = useContext(PreferencesContext);
  if (!ctx) throw new Error('usePreferences must be used inside PreferencesProvider');
  return ctx;
}
