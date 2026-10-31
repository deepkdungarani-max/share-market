import React, { useState } from 'react';
import { ExternalLinkIcon, MinusIcon, NewspaperIcon, PlusIcon } from 'lucide-react';
import { Empty, ErrorNote, PageTitle, SymbolChip, signed, tone } from '../components/Bits';
import { Pagination, pageOf, usePageParam } from '../components/Pagination';
import { usePoll } from '../hooks/usePoll';
import { eventLabel, fetchNews, type Note } from '../utils/site';
import { formatWhen } from '../utils/teacher';

const SCOPES = [
{ key: 'tracked', label: 'Tracked stocks' },
{ key: 'help', label: 'Sent to Drona' },
{ key: 'all', label: 'Everything' }];


const REASONS: Record<string, string> = {
  mixed: 'Good and bad facts together',
  unsure: 'Narad was unsure',
  unreliable: 'Narad often gets this kind of news wrong'
};

export function News() {
  const [scope, setScope] = useState('tracked');
  const [symbol, setSymbol] = useState('');
  const { data, error } = usePoll((signal) => fetchNews(scope, symbol, signal), 60_000, [scope, symbol]);
  const n = (rec: Record<string, number> | undefined, key: string) => (rec?.[key] ?? 0).toLocaleString();
  const [page, setPage] = usePageParam('page');
  const notes = pageOf(data?.notes ?? [], page);

  return (
    <div className="flex flex-col gap-5">
      <PageTitle icon={NewspaperIcon} title="News">
        Every note Narad wrote, newest first, with Drona's answer wherever Narad asked for help.
      </PageTitle>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex rounded-lg border border-line bg-surface p-1" role="group" aria-label="Which notes">
          {SCOPES.map((s) =>
          <button
            key={s.key}
            type="button"
            onClick={() => {setScope(s.key);setPage(1);}}
            aria-pressed={scope === s.key}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${scope === s.key ? 'bg-raised text-ink' : 'text-muted hover:text-ink'}`}>

              {s.label}
            </button>
          )}
        </div>
        <label className="flex items-center gap-2 text-sm text-muted">
          Stock
          <select
            id="news-symbol"
            value={symbol}
            onChange={(e) => {setSymbol(e.target.value);setPage(1);}}
            className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-sm text-ink focus:border-accent focus:outline-none">

            <option value="">All</option>
            {(data?.tracked ?? []).map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
      </div>

      {data &&
      <p className="text-[13px] text-muted">
          <span className="tabular-nums text-ink">{n(data.news, 'read')}</span> read ·{' '}
          <span className="tabular-nums text-ink">{n(data.news, 'new')}</span> waiting ·{' '}
          <span className="tabular-nums text-ink">{n(data.news, 'duplicate')}</span> skipped as the same story ·{' '}
          <span className="tabular-nums text-ink">{n(data.help, 'pending')}</span> help requests waiting for Drona,{' '}
          <span className="tabular-nums text-ink">{n(data.help, 'answered')}</span> answered
        </p>
      }

      {error && <ErrorNote>{error}</ErrorNote>}
      {data && (
      data.notes.length === 0 ?
      <Empty>No notes here yet. Narad reads the news while the server runs: tracked companies and publisher news first.</Empty> :

      <>
            <div className="flex flex-col gap-3">
              {notes.rows.map((note) => <NoteCard key={note.id} note={note} />)}
            </div>
            <Pagination page={notes.page} pages={notes.pages} total={data.notes.length} onPage={setPage} noun="latest notes" />
          </>)
      }
    </div>);

}

function NoteCard({ note: n }: {note: Note;}) {
  const answer = n.help?.answer;
  return (
    <article className="rounded-xl border border-line bg-surface p-4">
      <header className="flex flex-col gap-1.5">
        <a href={n.url} target="_blank" rel="noreferrer" className="group inline-flex items-start gap-1.5 text-[15px] font-semibold text-ink hover:text-accent">
          {n.title}
          <ExternalLinkIcon className="mt-1 h-3.5 w-3.5 shrink-0 text-muted group-hover:text-accent" aria-hidden="true" />
        </a>
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
          {n.symbols.map((s) => <SymbolChip key={s} symbol={s} />)}
          {n.symbols.length === 0 && <span className="rounded-md bg-raised px-1.5 py-0.5">{n.about}</span>}
          <span className="rounded-md border border-line px-1.5 py-0.5">{eventLabel(n.event)}</span>
          <span>{n.source}{n.published && ` · ${formatWhen(n.published)}`}</span>
        </div>
      </header>

      <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm">
        <span>
          Narad: <span className={`font-semibold tabular-nums ${tone(n.sentiment)}`}>{signed(n.sentiment)}</span>
          <span className="ml-1 text-xs text-muted">confidence {n.confidence.toFixed(2)}</span>
        </span>
        {answer &&
        <span>
            Drona: <span className={`font-semibold tabular-nums ${tone(answer.sentiment)}`}>{signed(answer.sentiment)}</span>
            <span className="ml-1 text-xs text-muted">confidence {answer.confidence.toFixed(2)}</span>
          </span>
        }
      </div>

      {(n.positives.length > 0 || n.negatives.length > 0) &&
      <div className="mt-2 grid gap-2 text-[13px] sm:grid-cols-2">
          <Points icon={PlusIcon} className="text-up" points={n.positives} />
          <Points icon={MinusIcon} className="text-down" points={n.negatives} />
        </div>
      }

      {n.help &&
      <p className="mt-3 rounded-lg bg-raised/60 px-3 py-2 text-[13px] leading-relaxed text-ink/90">
          <span className="font-medium text-amber-400">Sent to Drona</span>
          <span className="text-muted"> · {REASONS[n.help.reason] ?? n.help.reason}</span>
          {answer ?
        <span className="block">{answer.reason}</span> :
        <span className="block text-muted">{n.help.status === 'skipped' ? 'Skipped.' : 'Waiting for an answer.'}</span>}
        </p>
      }
    </article>);

}

function Points({ icon: Icon, className, points }: {icon: typeof PlusIcon;className: string;points: string[];}) {
  if (points.length === 0) return <div />;
  return (
    <ul className="flex flex-col gap-1">
      {points.map((p) =>
      <li key={p} className="flex gap-1.5 text-ink/85">
          <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${className}`} aria-hidden="true" />
          {p}
        </li>
      )}
    </ul>);

}
