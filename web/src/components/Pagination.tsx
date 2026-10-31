import React, { useState } from 'react';
import { ChevronLeftIcon, ChevronRightIcon, ChevronsLeftIcon, ChevronsRightIcon } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';

export const PAGE_SIZE = 20;

/** The page number kept in the URL (?page=… or another key), so a refresh or Back opens the same page. */
export function usePageParam(key = 'page'): [number, (page: number) => void] {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get(key)) || 1);
  const setPage = (next: number) =>
  setParams((prev) => {
    const p = new URLSearchParams(prev);
    if (next <= 1) p.delete(key);else
    p.set(key, String(next));
    return p;
  }, { replace: true });
  return [page, setPage];
}

/** One page of a list held in the browser, and the page count. */
export function pageOf<T>(rows: T[], page: number, size = PAGE_SIZE): {rows: T[];page: number;pages: number;} {
  const pages = Math.max(1, Math.ceil(rows.length / size));
  const p = Math.min(Math.max(1, page), pages);
  return { rows: rows.slice((p - 1) * size, p * size), page: p, pages };
}

/** Page numbers to show: the first, the last, and two on each side of the current one, with gaps as null. */
function numbers(page: number, pages: number): (number | null)[] {
  const keep = new Set([1, pages, page - 2, page - 1, page, page + 1, page + 2].filter((n) => n >= 1 && n <= pages));
  const sorted = [...keep].sort((a, b) => a - b);
  return sorted.flatMap((n, i) => i > 0 && n - sorted[i - 1] > 1 ? [null, n] : [n]);
}

/** First / previous / numbered pages / next / last, a box to jump to any page, and how many rows there are. */
export function Pagination({ page, pages, total, onPage, noun = 'rows' }: {page: number;pages: number;total: number;onPage: (page: number) => void;noun?: string;}) {
  const [jump, setJump] = useState('');
  if (total === 0) return null;
  const go = (n: number) => onPage(Math.min(Math.max(1, n), pages));
  const btn = 'flex h-8 min-w-8 items-center justify-center rounded-md px-2 text-sm tabular-nums disabled:opacity-40';

  return (
    <nav className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm text-muted" aria-label="Pages">
      <span>
        {((page - 1) * PAGE_SIZE + 1).toLocaleString()}–{Math.min(page * PAGE_SIZE, total).toLocaleString()} of {total.toLocaleString()} {noun}
      </span>
      {pages > 1 &&
      <div className="flex flex-wrap items-center gap-1">
          <button type="button" className={`${btn} hover:bg-raised`} onClick={() => go(1)} disabled={page <= 1} aria-label="First page">
            <ChevronsLeftIcon className="h-4 w-4" aria-hidden="true" />
          </button>
          <button type="button" className={`${btn} hover:bg-raised`} onClick={() => go(page - 1)} disabled={page <= 1} aria-label="Previous page">
            <ChevronLeftIcon className="h-4 w-4" aria-hidden="true" />
          </button>
          {numbers(page, pages).map((n, i) =>
        n === null ?
        <span key={`gap-${i}`} className="px-1">…</span> :

        <button
          key={n}
          type="button"
          onClick={() => go(n)}
          aria-current={n === page ? 'page' : undefined}
          className={`${btn} ${n === page ? 'bg-accent font-semibold text-canvas' : 'text-ink hover:bg-raised'}`}>

                {n.toLocaleString()}
              </button>
        )}
          <button type="button" className={`${btn} hover:bg-raised`} onClick={() => go(page + 1)} disabled={page >= pages} aria-label="Next page">
            <ChevronRightIcon className="h-4 w-4" aria-hidden="true" />
          </button>
          <button type="button" className={`${btn} hover:bg-raised`} onClick={() => go(pages)} disabled={page >= pages} aria-label="Last page">
            <ChevronsRightIcon className="h-4 w-4" aria-hidden="true" />
          </button>
          {pages > 7 &&
        <form
          className="ml-1 flex items-center gap-1"
          onSubmit={(e) => {
            e.preventDefault();
            const n = Number(jump);
            if (n) go(n);
            setJump('');
          }}>

              <label className="sr-only" htmlFor="page-jump">Go to page</label>
              <input
            id="page-jump"
            value={jump}
            onChange={(e) => setJump(e.target.value.replace(/\D/g, ''))}
            placeholder="Go to"
            inputMode="numeric"
            className="h-8 w-16 rounded-md border border-line bg-canvas px-2 text-ink placeholder:text-muted focus:border-accent focus:outline-none" />

            </form>
        }
        </div>
      }
    </nav>);

}
