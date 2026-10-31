import React, { useCallback, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { BellIcon, BellRingIcon, XIcon } from 'lucide-react';
import { usePreferences } from '../contexts/PreferencesContext';
import { useDismiss } from '../hooks/useDismiss';
import type { Direction, Market } from '../types/market';

interface AlertButtonProps {
  market: Market;
  symbol: string;
}

const thresholds = [60, 65, 70, 75, 80];
const directions: {id: Direction | 'any';label: string;}[] = [
{ id: 'any', label: 'Either' },
{ id: 'up', label: 'UP' },
{ id: 'down', label: 'DOWN' }];


export function AlertButton({ market, symbol }: AlertButtonProps) {
  const { alerts, addAlert, removeAlert } = usePreferences();
  const [open, setOpen] = useState(false);
  const [threshold, setThreshold] = useState(70);
  const [direction, setDirection] = useState<Direction | 'any'>('any');
  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>(
    'Notification' in window ? Notification.permission : 'unsupported'
  );
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(ref, open, close);

  const mine = alerts.filter((a) => a.market === market && a.symbol === symbol);
  const Icon = mine.length ? BellRingIcon : BellIcon;

  const seg = (active: boolean) =>
  `flex-1 rounded-md px-2 py-1 font-mono text-xs transition-colors duration-150 focus:outline-none focus-visible:ring-1 focus-visible:ring-accent ${
  active ? 'bg-raised text-ink' : 'text-muted hover:text-ink'}`;


  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={`Alerts for ${symbol}`}
        className={`flex h-10 items-center gap-1.5 rounded-lg border bg-surface px-3 text-sm transition-colors duration-150 focus:outline-none focus-visible:ring-1 focus-visible:ring-accent ${
        mine.length ? 'border-accent/50 text-accent' : 'border-line text-muted hover:text-ink'}`
        }>
        
        <Icon className="h-4 w-4" aria-hidden="true" />
        {mine.length > 0 && <span className="font-mono text-xs">{mine.length}</span>}
      </button>

      <AnimatePresence>
        {open &&
        <motion.div
          initial={{ opacity: 0, y: -4, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -4, scale: 0.98 }}
          transition={{ duration: 0.15, ease: [0.23, 1, 0.32, 1] }}
          className="absolute left-0 top-full z-30 mt-2 w-[min(320px,calc(100vw-2rem))] origin-top-left rounded-xl border border-line bg-surface p-4 shadow-[0_16px_40px_-12px_rgba(0,0,0,0.8)]">
          
            <p className="text-sm font-semibold text-ink">Alert me on {symbol}</p>
            <p className="mt-0.5 text-xs text-muted">when the model's signal is at least</p>

            <div role="group" aria-label="Probability threshold" className="mt-3 flex rounded-lg border border-line p-0.5">
              {thresholds.map((t) =>
            <button key={t} type="button" aria-pressed={threshold === t} onClick={() => setThreshold(t)} className={seg(threshold === t)}>
                  {t}%
                </button>
            )}
            </div>
            <div role="group" aria-label="Direction" className="mt-2 flex rounded-lg border border-line p-0.5">
              {directions.map((d) =>
            <button key={d.id} type="button" aria-pressed={direction === d.id} onClick={() => setDirection(d.id)} className={seg(direction === d.id)}>
                  {d.label}
                </button>
            )}
            </div>
            <button
            type="button"
            onClick={() => addAlert({ market, symbol, threshold, direction })}
            className="mt-3 w-full rounded-lg bg-accent py-2 text-sm font-semibold text-canvas transition-opacity duration-150 hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50">
            
              Add alert
            </button>

            {mine.length > 0 &&
          <ul className="mt-3 divide-y divide-line border-t border-line">
                {mine.map((a) =>
            <li key={a.id} className="flex items-center justify-between py-2 font-mono text-xs">
                    <span className="text-ink">
                      ≥{a.threshold}% <span className="text-muted">{a.direction === 'any' ? 'either way' : a.direction.toUpperCase()}</span>
                    </span>
                    <button
                type="button"
                onClick={() => removeAlert(a.id)}
                aria-label={`Remove alert ${a.threshold}%`}
                className="rounded p-1 text-muted transition-colors duration-150 hover:text-down focus:outline-none focus-visible:ring-1 focus-visible:ring-accent">
                
                      <XIcon className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                  </li>
            )}
              </ul>
          }

            {permission === 'default' &&
          <button
            type="button"
            onClick={() => Notification.requestPermission().then(setPermission)}
            className="mt-3 w-full rounded-lg border border-line py-1.5 text-xs text-ink transition-colors duration-150 hover:border-muted focus:outline-none focus-visible:ring-1 focus-visible:ring-accent">
            
                Also send browser notifications
              </button>
          }
            <p className="mt-3 text-xs leading-relaxed text-muted">
              Checked every time the model re-runs on {symbol}, while this page is open.
            </p>
          </motion.div>
        }
      </AnimatePresence>
    </div>);

}