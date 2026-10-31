import React from 'react';
import { HistoryIcon, StarIcon } from 'lucide-react';
import { usePreferences } from '../contexts/PreferencesContext';
import { formatPct } from '../utils/format';
import type { Instrument } from '../types/market';

interface SavedSymbolsProps {
  instruments: Instrument[];
  /** Change % is a live quote; false hides it. */
  showChange: boolean;
  onSelect: (symbol: string) => void;
}

export function SavedSymbols({ instruments, showChange, onSelect }: SavedSymbolsProps) {
  const { watchlist, recent } = usePreferences();
  const market = 'stocks';
  const lookup = (symbols: string[]) =>
  symbols.map((s) => instruments.find((i) => i.symbol === s)).filter((i): i is Instrument => Boolean(i));
  const watched = lookup(watchlist[market]);
  const recents = lookup(recent[market]).filter((i) => !watchlist[market].includes(i.symbol));

  if (watched.length === 0 && recents.length === 0) return null;

  return (
    <div className="mt-5 flex flex-col items-center gap-2.5">
      {watched.length > 0 && <Row icon={<StarIcon className="h-4 w-4 fill-accent text-accent" />} label="Watchlist" items={watched} showChange={showChange} onSelect={onSelect} />}
      {recents.length > 0 && <Row icon={<HistoryIcon className="h-4 w-4 text-muted" />} label="Recent" items={recents} showChange={showChange} onSelect={onSelect} />}
    </div>);

}

function Row({ icon, label, items, showChange, onSelect }: {icon: React.ReactNode;label: string;items: Instrument[];showChange: boolean;onSelect: (s: string) => void;}) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      <span className="flex items-center gap-1.5 text-[13px] text-muted" aria-hidden="true">
        {icon}
        {label}
      </span>
      <ul className="flex flex-wrap justify-center gap-2" aria-label={label}>
        {items.map((inst) =>
        <li key={inst.symbol}>
            <button
            type="button"
            onClick={() => onSelect(inst.symbol)}
            className="flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-[13px] transition-colors duration-150 hover:border-accent/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/60">

              <span className="font-medium text-ink">{inst.symbol}</span>
              {showChange && <span className={`tabular-nums ${inst.changePct >= 0 ? 'text-up' : 'text-down'}`}>{formatPct(inst.changePct)}</span>}
            </button>
          </li>
        )}
      </ul>
    </div>);

}
