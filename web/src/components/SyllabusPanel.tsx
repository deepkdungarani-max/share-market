import React, { useState } from 'react';
import { BookOpenIcon, ChevronDownIcon, CircleCheckIcon, CircleIcon, CircleXIcon } from 'lucide-react';
import { usePoll } from '../hooks/usePoll';
import { fetchTeacherStatus, type SyllabusLevel } from '../utils/teacher';

/** Drona's beginner-to-expert syllabus: seven levels after the books traders and quants learn from, each with its
 *  progress; a level opens its topics, and a learned topic opens its lesson. */
export function SyllabusPanel({ onOpenLesson }: {onOpenLesson: (id: number) => void;}) {
  const { data, error } = usePoll(fetchTeacherStatus, 60_000);
  const [open, setOpen] = useState<number | null>(null);
  const levels = data?.syllabus ?? [];
  const done = levels.reduce((n, l) => n + l.done, 0);
  const total = levels.reduce((n, l) => n + l.total, 0);
  const next = levels.flatMap((l) => l.topics).find((t) => t.status === 'pending');

  return (
    <section aria-labelledby="syllabus-title" className="mt-6 rounded-xl border border-line bg-surface p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="syllabus-title" className="flex items-center gap-2 text-[15px] font-semibold text-ink">
          <BookOpenIcon className="h-4 w-4 text-accent" aria-hidden="true" /> Syllabus: beginner to expert
        </h2>
        {total > 0 &&
        <span className="text-xs text-muted">
            <span className="tabular-nums text-ink">{done}</span> of <span className="tabular-nums">{total}</span> topics learned
          </span>
        }
      </div>
      <p className="mt-1 text-[13px] leading-relaxed text-muted">
        Seven levels after the books traders, investors and quants learn from, and India's official sources. Drona writes
        each lesson itself from web research and official documents, in order, and every lesson adds deeper topics of its own.
      </p>
      {error && <p className="mt-3 text-sm text-down">{error}</p>}
      {data && total === 0 &&
      <p className="mt-3 text-sm text-muted">The syllabus is queued when the learner next starts (after a server restart).</p>
      }
      {next && <p className="mt-2 text-[13px] text-ink/90"><span className="text-muted">Next up:</span> {next.title}</p>}

      <ol className="mt-3 flex flex-col gap-2">
        {levels.map((l) =>
        <Level key={l.level} level={l} open={open === l.level} onToggle={() => setOpen(open === l.level ? null : l.level)} onOpenLesson={onOpenLesson} />
        )}
      </ol>
    </section>);

}

function Level({ level: l, open, onToggle, onOpenLesson }: {level: SyllabusLevel;open: boolean;onToggle: () => void;onOpenLesson: (id: number) => void;}) {
  const pct = l.total ? (100 * l.done) / l.total : 0;
  return (
    <li className="rounded-lg border border-line/70 bg-canvas/40">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={`syllabus-level-${l.level}`}
        className="flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-raised/40">

        <span className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-xs font-semibold tabular-nums ${
        l.total && l.done === l.total ? 'bg-up/15 text-up' : 'bg-accent/15 text-accent'}`
        }>
          {l.level}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-3">
            <span className="text-sm font-medium text-ink">{l.name}</span>
            <span className="shrink-0 text-xs tabular-nums text-muted"><span className="text-ink">{l.done}</span> of {l.total}</span>
          </span>
          <span className="mt-0.5 block text-xs text-muted">{l.books}</span>
          <span className="mt-2 block h-1.5 rounded-full bg-raised" role="presentation">
            <span className="block h-1.5 rounded-full bg-accent" style={{ width: `${pct}%` }} />
          </span>
        </span>
        <ChevronDownIcon className={`mt-0.5 h-4 w-4 shrink-0 text-muted transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>

      {open &&
      <ul id={`syllabus-level-${l.level}`} className="flex flex-col border-t border-line/70 px-2 py-1.5">
          {l.topics.map((t) => {
          const Icon = t.status === 'done' ? CircleCheckIcon : t.status === 'failed' ? CircleXIcon : CircleIcon;
          const look = t.status === 'done' ? 'text-up' : t.status === 'failed' ? 'text-amber-400' : 'text-muted/60';
          const body =
          <>
                <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${look}`} aria-hidden="true" />
                <span className={t.status === 'done' ? 'text-ink' : 'text-muted'}>{t.title}</span>
                <span className="sr-only"> ({t.status === 'done' ? 'learned' : t.status === 'failed' ? 'failed, will be retried' : 'not learned yet'})</span>
              </>;

          return (
            <li key={t.id}>
                {t.status === 'done' ?
              <button
                type="button"
                onClick={() => onOpenLesson(t.id)}
                className="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-[13px] hover:bg-raised">

                    {body}
                  </button> :

              <div className="flex items-start gap-2 px-2 py-1.5 text-[13px]">{body}</div>
              }
              </li>);

        })}
        </ul>
      }
    </li>);

}
