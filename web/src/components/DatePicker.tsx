import React, { useEffect, useRef, useState } from 'react';
import { CalendarIcon, ChevronLeftIcon, ChevronRightIcon } from 'lucide-react';

const WEEKDAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** YYYY-MM-DD of a local date (toISOString would shift it to UTC). */
export function isoDay(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** The date `years` years and `days` days before today, as YYYY-MM-DD. */
export function daysAgo(days: number, years = 0): string {
  const t = new Date();
  return isoDay(new Date(t.getFullYear() - years, t.getMonth(), t.getDate() - days));
}

const parse = (s: string) => {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
};
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const addMonths = (d: Date, n: number) => {
  const first = new Date(d.getFullYear(), d.getMonth() + n, 1);
  const last = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
  return new Date(first.getFullYear(), first.getMonth(), Math.min(d.getDate(), last));
};
const weekday = (d: Date) => (d.getDay() + 6) % 7; // Monday 0 … Sunday 6
const long = (d: Date) => d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });

type View = 'days' | 'months' | 'years';

/** A date picker in the site's own look: a month grid starting Monday with weekends dimmed (no trading), quick
 *  presets, month and year views for jumping years back, and full keyboard use (arrows, Page Up/Down, Home/End,
 *  Enter, Esc). An empty value shows the placeholder, which stands for the caller's default. */
export function DatePicker({ value, onChange, min, max, presets = [], placeholder = 'Pick a date', describedBy }: {
  value: string;
  onChange: (value: string) => void;
  min?: string;
  max?: string;
  presets?: {label: string;value: string;}[];
  placeholder?: string;
  describedBy?: string;
}) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<View>('days');
  const minD = min ? parse(min) : null;
  const maxD = max ? parse(max) : null;
  const allowed = (d: Date) => (!minD || d >= minD) && (!maxD || d <= maxD);
  const start = () => value ? parse(value) : maxD && maxD < new Date() ? maxD : new Date();
  const [focus, setFocus] = useState<Date>(start);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const grid = useRef<HTMLDivElement>(null);
  const today = isoDay(new Date());

  const show = () => {
    setFocus(start());
    setView('days');
    setOpen(true);
  };
  const close = (refocus = true) => {
    setOpen(false);
    if (refocus) trigger.current?.focus();
  };
  const pick = (d: Date) => {
    if (!allowed(d)) return;
    onChange(isoDay(d));
    close();
  };

  useEffect(() => {
    if (!open) return undefined;
    const outside = (e: MouseEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) close(false);
    };
    document.addEventListener('mousedown', outside);
    return () => document.removeEventListener('mousedown', outside);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (open && view === 'days') grid.current?.querySelector<HTMLButtonElement>(`[data-day="${isoDay(focus)}"]`)?.focus();
  }, [focus, open, view]);

  const onGridKey = (e: React.KeyboardEvent) => {
    const moves: Record<string, () => Date> = {
      ArrowLeft: () => addDays(focus, -1),
      ArrowRight: () => addDays(focus, 1),
      ArrowUp: () => addDays(focus, -7),
      ArrowDown: () => addDays(focus, 7),
      PageUp: () => addMonths(focus, e.shiftKey ? -12 : -1),
      PageDown: () => addMonths(focus, e.shiftKey ? 12 : 1),
      Home: () => addDays(focus, -weekday(focus)),
      End: () => addDays(focus, 6 - weekday(focus))
    };
    if (moves[e.key]) {
      e.preventDefault();
      const next = moves[e.key]();  // kept inside the allowed range, so the focus never lands on a disabled day
      setFocus(minD && next < minD ? minD : maxD && next > maxD ? maxD : next);
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      pick(focus);
    }
  };

  const year = focus.getFullYear();
  const pageStart = year - year % 12;
  const step = (n: number) =>
  setFocus(view === 'days' ? addMonths(focus, n) : view === 'months' ? addMonths(focus, 12 * n) : addMonths(focus, 144 * n));
  const title =
  view === 'days' ? focus.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' }) :
  view === 'months' ? String(year) :
  `${pageStart} – ${pageStart + 11}`;
  const nav = 'flex h-8 w-8 items-center justify-center rounded-lg text-muted hover:bg-raised hover:text-ink';

  const first = new Date(year, focus.getMonth(), 1);
  const cells = Array.from({ length: 42 }, (_, i) => addDays(first, i - weekday(first)));

  return (
    <div ref={root} className="relative" onKeyDown={(e) => {if (e.key === 'Escape' && open) {e.stopPropagation();close();}}}>
      <button
        ref={trigger}
        type="button"
        onClick={() => open ? close() : show()}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-describedby={describedBy}
        className={`inline-flex items-center gap-2 rounded-lg border bg-canvas px-2.5 py-1.5 text-xs transition-colors ${
        open ? 'border-accent text-ink' : 'border-line text-ink hover:border-accent/60'}`
        }>

        <CalendarIcon className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
        <span className={value ? 'tabular-nums' : 'text-muted'}>{value ? long(parse(value)) : placeholder}</span>
      </button>

      {open &&
      <div
        role="dialog"
        aria-label="Choose a date"
        className="absolute right-0 top-full z-50 mt-2 w-[18.5rem] rounded-xl border border-line bg-surface p-3 shadow-2xl shadow-black/50">

          {presets.length > 0 &&
        <div className="mb-3 flex flex-wrap gap-1.5">
              {presets.map((p) => {
            const on = p.value === value;
            return (
              <button
                key={p.label}
                type="button"
                onClick={() => {onChange(p.value);close();}}
                aria-pressed={on}
                className={`rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors ${
                on ? 'border-accent bg-accent/15 text-accent' : 'border-line text-muted hover:border-accent/60 hover:text-ink'}`
                }>

                    {p.label}
                  </button>);

          })}
            </div>
        }

          <div className="flex items-center justify-between">
            <button type="button" onClick={() => step(-1)} className={nav} aria-label={view === 'days' ? 'Previous month' : view === 'months' ? 'Previous year' : 'Earlier years'}>
              <ChevronLeftIcon className="h-4 w-4" aria-hidden="true" />
            </button>
            <button
            type="button"
            onClick={() => setView(view === 'days' ? 'months' : view === 'months' ? 'years' : 'days')}
            className="rounded-lg px-2.5 py-1 text-sm font-semibold text-ink hover:bg-raised"
            aria-label={`${title}: ${view === 'years' ? 'back to days' : 'choose a different ' + (view === 'days' ? 'month' : 'year')}`}>

              {title}
            </button>
            <button type="button" onClick={() => step(1)} className={nav} aria-label={view === 'days' ? 'Next month' : view === 'months' ? 'Next year' : 'Later years'}>
              <ChevronRightIcon className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>

          {view === 'days' &&
        <div ref={grid} role="grid" aria-label={title} onKeyDown={onGridKey} className="mt-2">
              <div role="row" className="grid grid-cols-7">
                {WEEKDAYS.map((w, i) =>
            <span key={w} role="columnheader" className={`py-1.5 text-center text-[11px] font-medium uppercase tracking-wide ${i >= 5 ? 'text-muted/50' : 'text-muted'}`}>
                    {w}
                  </span>
            )}
              </div>
              {Array.from({ length: 6 }, (_, week) =>
          <div key={week} role="row" className="grid grid-cols-7 gap-0.5">
                  {cells.slice(week * 7, week * 7 + 7).map((d) => {
              const iso = isoDay(d);
              const inMonth = d.getMonth() === focus.getMonth();
              const ok = allowed(d);
              const chosen = iso === value;
              const focused = iso === isoDay(focus);
              return (
                <button
                  key={iso}
                  type="button"
                  role="gridcell"
                  data-day={iso}
                  tabIndex={focused ? 0 : -1}
                  disabled={!ok}
                  aria-selected={chosen}
                  aria-label={`${long(d)}${iso === today ? ', today' : ''}${weekday(d) >= 5 ? ', weekend' : ''}`}
                  onClick={() => pick(d)}
                  className={`flex h-9 items-center justify-center rounded-lg text-sm tabular-nums outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent ${
                  chosen ? 'bg-accent font-semibold text-canvas' :
                  !ok ? 'cursor-not-allowed text-muted/25' :
                  !inMonth ? 'text-muted/40 hover:bg-raised' :
                  weekday(d) >= 5 ? 'text-muted/70 hover:bg-raised' :
                  'text-ink hover:bg-raised'} ${
                  iso === today && !chosen ? 'ring-1 ring-inset ring-accent/60' : ''}`}>

                        {d.getDate()}
                      </button>);

            })}
                </div>
          )}
            </div>
        }

          {view === 'months' &&
        <div className="mt-3 grid grid-cols-3 gap-1.5">
              {MONTHS.map((name, m) => {
            const from = new Date(year, m, 1);
            const to = new Date(year, m + 1, 0);
            const ok = (!maxD || from <= maxD) && (!minD || to >= minD);
            const here = value && parse(value).getFullYear() === year && parse(value).getMonth() === m;
            return (
              <button
                key={name}
                type="button"
                disabled={!ok}
                onClick={() => {setFocus(new Date(year, m, Math.min(focus.getDate(), 28)));setView('days');}}
                className={`h-10 rounded-lg text-sm ${here ? 'bg-accent/15 font-semibold text-accent' : ok ? 'text-ink hover:bg-raised' : 'cursor-not-allowed text-muted/25'}`}>

                    {name}
                  </button>);

          })}
            </div>
        }

          {view === 'years' &&
        <div className="mt-3 grid grid-cols-3 gap-1.5">
              {Array.from({ length: 12 }, (_, i) => pageStart + i).map((y) => {
            const ok = (!minD || y >= minD.getFullYear()) && (!maxD || y <= maxD.getFullYear());
            const here = value && parse(value).getFullYear() === y;
            return (
              <button
                key={y}
                type="button"
                disabled={!ok}
                onClick={() => {setFocus(new Date(y, focus.getMonth(), Math.min(focus.getDate(), 28)));setView('months');}}
                className={`h-10 rounded-lg text-sm tabular-nums ${here ? 'bg-accent/15 font-semibold text-accent' : ok ? 'text-ink hover:bg-raised' : 'cursor-not-allowed text-muted/25'}`}>

                    {y}
                  </button>);

          })}
            </div>
        }

          <div className="mt-3 flex items-center justify-between border-t border-line pt-2.5 text-xs">
            <span className="text-muted">{value ? long(parse(value)) : placeholder}</span>
            {value &&
          <button type="button" onClick={() => {onChange('');close();}} className="font-medium text-accent hover:underline">
                Use default
              </button>
          }
          </div>
        </div>
      }
    </div>);

}
