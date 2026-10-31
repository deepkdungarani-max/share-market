import React from 'react';
import { ArrowDownRightIcon, ArrowUpRightIcon, CheckIcon, XIcon, type LucideIcon } from 'lucide-react';

/** A call at least this far from 50% counts as confident (the line the walk-forward tests used). */
export const CONFIDENT = 0.05;

export const MODEL_LABELS: Record<string, string> = {
  trikal: 'Trikal · main call',
  sanjay: 'Sanjay · chart',
  chanakya: 'Chanakya · world',
  narad: 'Narad · news',
  drona: 'Drona · help answers',
  drona_call: "Drona · knowledge call"
};

export function PageTitle({ icon: Icon, title, children }: {icon: LucideIcon;title: string;children: React.ReactNode;}) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent/15 text-accent" aria-hidden="true">
        <Icon className="h-5 w-5" />
      </span>
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
        <p className="text-sm text-muted">{children}</p>
      </div>
    </div>);

}

/** A titled card. `aside` sits at the right of the title row (a link, a timestamp). */
export function Panel({ id, icon: Icon, title, aside, children, className = '' }: {id: string;icon?: LucideIcon;title: React.ReactNode;aside?: React.ReactNode;children: React.ReactNode;className?: string;}) {
  return (
    <section aria-labelledby={id} className={`rounded-xl border border-line bg-surface p-4 sm:p-5 ${className}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={id} className="flex items-center gap-2 text-[15px] font-semibold text-ink">
          {Icon && <Icon className="h-4 w-4 text-accent" aria-hidden="true" />}
          {title}
        </h2>
        {aside}
      </div>
      {children}
    </section>);

}

export function Empty({ children }: {children: React.ReactNode;}) {
  return <p className="mt-4 rounded-lg bg-raised/50 px-4 py-6 text-center text-sm leading-relaxed text-muted">{children}</p>;
}

export function ErrorNote({ children }: {children: React.ReactNode;}) {
  return <p className="rounded-xl border border-down/40 bg-down/10 px-4 py-3 text-sm text-down" role="alert">{children}</p>;
}

export function DirectionTag({ up }: {up: boolean;}) {
  const Icon = up ? ArrowUpRightIcon : ArrowDownRightIcon;
  return (
    <span className={`inline-flex items-center gap-0.5 font-semibold ${up ? 'text-up' : 'text-down'}`}>
      <Icon className="h-4 w-4" aria-hidden="true" />
      {up ? 'Up' : 'Down'}
    </span>);

}

/** "Up 54%" for a probability of closing up, with a Confident tag when it is far enough from 50%. */
export function CallTag({ p, showConfident = true }: {p: number;showConfident?: boolean;}) {
  return (
    <span className="whitespace-nowrap">
      <DirectionTag up={p >= 0.5} />
      <span className="ml-1.5 text-xs tabular-nums text-muted">{callPct(p)}%</span>
      {showConfident && Math.abs(p - 0.5) >= CONFIDENT &&
      <span className="ml-2 rounded-md bg-accent/15 px-1.5 py-0.5 text-[11px] font-medium text-accent">Confident</span>
      }
    </span>);

}

export function ResultTag({ hit }: {hit: number | null;}) {
  if (hit === null) return <span className="text-xs text-muted">no call</span>;
  return hit ?
  <span className="inline-flex items-center gap-1 rounded-full bg-up/10 px-2 py-0.5 text-xs font-medium text-up">
      <CheckIcon className="h-3.5 w-3.5" aria-hidden="true" /> Right
    </span> :

  <span className="inline-flex items-center gap-1 rounded-full bg-down/10 px-2 py-0.5 text-xs font-medium text-down">
      <XIcon className="h-3.5 w-3.5" aria-hidden="true" /> Wrong
    </span>;

}

/** A probability of closing up as "55%", green above 50% and red below. */
export function Chance({ p }: {p: number | null;}) {
  if (p === null) return <span className="text-muted">–</span>;
  return <span className={`tabular-nums ${p >= 0.5 ? 'text-up' : 'text-down'}`}>{Math.round(p * 100)}%</span>;
}

export function Stat({ label, value }: {label: string;value: React.ReactNode;}) {
  return (
    <div className="rounded-lg bg-raised/60 px-3 py-2">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums text-ink">{value}</dd>
    </div>);

}

/** Marks a rupee pair among the stocks. */
export function PairTag({ market }: {market?: string;}) {
  if (market !== 'forex') return null;
  return <span className="ml-1.5 rounded-md border border-accent/40 px-1 py-px text-[10px] font-medium uppercase tracking-wide text-accent">INR pair</span>;
}

export function SymbolChip({ symbol }: {symbol: string;}) {
  return <span className="rounded-md bg-raised px-1.5 py-0.5 text-xs font-medium text-ink">{symbol}</span>;
}

/** Percent of the called direction: 0.46 -> 54 (a 54% "down" call). */
export function callPct(p: number): number {
  return Math.round((p >= 0.5 ? p : 1 - p) * 100);
}

export function signed(n: number, digits = 2): string {
  return `${n > 0 ? '+' : ''}${n.toFixed(digits)}`;
}

export function tone(n: number | null): string {
  if (n === null || n === 0) return 'text-muted';
  return n > 0 ? 'text-up' : 'text-down';
}

/** Colour for a hit rate: 50% is a coin flip. */
export function rightTone(pct: number | null): string {
  if (pct === null) return 'text-muted';
  return pct > 52 ? 'text-up' : pct < 48 ? 'text-down' : 'text-ink';
}
