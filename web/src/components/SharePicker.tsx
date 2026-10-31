import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { CornerDownLeftIcon, SearchIcon } from 'lucide-react';
import { formatPct, formatPrice } from '../utils/format';
import type { Instrument } from '../types/market';

interface SharePickerProps {
  instruments: Instrument[];
  onSelect: (symbol: string) => void;
  placeholder: string;
  size?: 'lg' | 'sm';
  autoFocus?: boolean;
  /** Show the list as soon as the input gains focus (used inside the switcher popover). */
  openOnFocus?: boolean;
  /** Prices in the list are live quotes; false hides them. */
  showPrices?: boolean;
}

/** Search-only picker: lists names & prices — no model runs until a symbol is chosen. */
export function SharePicker({
  instruments,
  onSelect,
  placeholder,
  size = 'lg',
  autoFocus = false,
  openOnFocus = false,
  showPrices = false
}: SharePickerProps) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();
  const lg = size === 'lg';

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return instruments;
    return instruments.filter((i) => i.symbol.toLowerCase().includes(q) || i.name.toLowerCase().includes(q));
  }, [instruments, query]);

  useEffect(() => setActive(0), [query, instruments]);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  const choose = (symbol: string) => {
    onSelect(symbol);
    setQuery('');
    setOpen(false);
    inputRef.current?.blur();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setOpen(true);
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === 'Enter' && results[active]) {
      e.preventDefault();
      choose(results[active].symbol);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <div className="relative w-full">
      <div
        className={`flex items-center gap-3 border border-line bg-surface transition-colors duration-150 focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/15 ${
        lg ? 'h-14 rounded-xl px-4' : 'h-11 rounded-lg px-3'}`
        }>
        
        <SearchIcon className={`shrink-0 text-muted ${lg ? 'h-5 w-5' : 'h-4 w-4'}`} aria-hidden="true" />
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && results[active] ? `${listId}-${active}` : undefined}
          aria-label="Search symbol"
          value={query}
          placeholder={placeholder}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => openOnFocus && setOpen(true)}
          onClick={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
          className={`min-w-0 flex-1 bg-transparent text-ink placeholder:text-muted/70 focus:outline-none ${lg ? 'text-base' : 'text-sm'}`} />
        
        {lg &&
        <kbd className="hidden items-center gap-1 rounded-md border border-line bg-raised px-2 py-0.5 text-xs text-muted sm:flex">
            <CornerDownLeftIcon className="h-3 w-3" aria-hidden="true" /> enter
          </kbd>
        }
      </div>

      {open &&
      <ul
        id={listId}
        role="listbox"
        className="absolute left-0 right-0 top-full z-30 mt-2 max-h-80 overflow-y-auto rounded-xl border border-line bg-surface p-1 shadow-[0_16px_40px_-12px_rgba(0,0,0,0.8)]">
        
          {results.length === 0 ?
        <li className="px-3 py-6 text-center text-sm text-muted">No match for "{query}"</li> :

        results.map((inst, i) =>
        <li
          key={inst.symbol}
          id={`${listId}-${i}`}
          role="option"
          aria-selected={i === active}
          onMouseDown={(e) => e.preventDefault()}
          onMouseEnter={() => setActive(i)}
          onClick={() => choose(inst.symbol)}
          className={`flex cursor-pointer items-center justify-between gap-4 rounded-lg px-3 py-2.5 ${i === active ? 'bg-raised' : ''}`}>

                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-ink">{inst.symbol}</span>
                  <span className="block truncate text-[13px] text-muted">{inst.name}</span>
                </span>
                {showPrices &&
                <span className="shrink-0 text-right text-[13px] tabular-nums">
                  <span className="block font-medium text-ink">{formatPrice(inst.price, inst.decimals)}</span>
                  <span className={inst.changePct >= 0 ? 'text-up' : 'text-down'}>{formatPct(inst.changePct)}</span>
                </span>
                }
              </li>
        )
        }
        </ul>
      }
    </div>);

}