import { useEffect } from 'react';
import { toast } from 'sonner';
import { usePreferences } from '../contexts/PreferencesContext';
import { timeframeLabel } from '../utils/format';
import type { Market, Prediction } from '../types/market';

/** Fires matching alerts for the symbol on screen each time the model re-runs. */
export function useAlertWatcher(market: Market, symbol: string, prediction: Prediction, minutes: number, enabled: boolean) {
  const { alerts, markFired } = usePreferences();

  useEffect(() => {
    if (!enabled) return;
    const key = `${prediction.candle.time}-${minutes}-${prediction.direction}`;
    alerts.
    filter((a) => a.market === market && a.symbol === symbol).
    forEach((a) => {
      const dirOk = a.direction === 'any' || a.direction === prediction.direction;
      if (!dirOk || prediction.probability < a.threshold || a.lastFiredKey === key) return;
      markFired(a.id, key);
      const msg = `${symbol}: ${prediction.direction.toUpperCase()} ${prediction.probability}% for the next ${timeframeLabel(minutes)}`;
      toast(msg, {
        description: `Your alert: ≥${a.threshold}% ${a.direction === 'any' ? 'either way' : a.direction.toUpperCase()}`
      });
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('candlecast alert', { body: msg });
      }
    });
  }, [enabled, market, symbol, prediction, minutes, alerts, markFired]);
}