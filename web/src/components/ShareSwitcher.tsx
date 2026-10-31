import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronsUpDownIcon } from 'lucide-react';
import { SharePicker } from './SharePicker';
import type { Instrument } from '../types/market';

interface ShareSwitcherProps {
  instrument: Instrument;
  instruments: Instrument[];
  onSelect: (symbol: string) => void;
}

export function ShareSwitcher({ instrument, instruments, onSelect }: ShareSwitcherProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label={`${instrument.symbol}, change symbol`}
        className="flex items-center gap-3 rounded-xl py-1 pl-1 pr-2 text-left transition-colors duration-150 hover:bg-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/60">

        <span className="min-w-0">
          <span className="block text-xl font-semibold leading-tight tracking-tight text-ink sm:text-2xl">{instrument.symbol}</span>
          <span className="block max-w-[220px] truncate text-[13px] text-muted">{instrument.name}</span>
        </span>
        <ChevronsUpDownIcon className="h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
      </button>

      <AnimatePresence>
        {open &&
        <motion.div
          initial={{ opacity: 0, y: -4, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -4, scale: 0.98 }}
          transition={{ duration: 0.15, ease: [0.23, 1, 0.32, 1] }}
          className="absolute left-0 top-full z-30 mt-2 w-[min(360px,calc(100vw-2rem))] origin-top-left">
          
            <SharePicker
            instruments={instruments}
            onSelect={(s) => {
              onSelect(s);
              setOpen(false);
            }}
            placeholder="Search symbol…"
            size="sm"
            autoFocus
            openOnFocus />
          
          </motion.div>
        }
      </AnimatePresence>
    </div>);

}