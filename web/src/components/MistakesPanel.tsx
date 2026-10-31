import React from 'react';
import { TargetIcon } from 'lucide-react';
import { usePoll } from '../hooks/usePoll';
import { fetchMistakes } from '../utils/site';
import { Panel } from './Bits';

/** What Drona is studying because a call went wrong, and the help answers the market proved right. */
export function MistakesPanel({ onOpenLesson }: {onOpenLesson: (id: number) => void;}) {
  const { data, error } = usePoll(fetchMistakes, 60_000);

  return (
    <Panel id="mistakes-title" icon={TargetIcon} title="Learning from mistakes" className="sm:p-4">
      {error && <p className="mt-3 text-sm text-down">{error}</p>}
      {data && data.studying.length === 0 && data.checked.length === 0 &&
      <p className="mt-3 text-sm leading-relaxed text-muted">
          Nothing yet. When a call on a tracked stock is wrong and the stock moved 3% or more, Drona queues it here and researches
          what really moved it.
        </p>
      }
      {data && data.studying.length > 0 &&
      <>
          <h3 className="mt-3 text-[13px] font-medium text-muted">Studying wrong calls</h3>
          <ul className="mt-1.5 flex flex-col">
            {data.studying.map((t) =>
          <li key={t.id}>
                <button
              type="button"
              disabled={t.status !== 'done'}
              onClick={() => onOpenLesson(t.id)}
              title={t.why ?? undefined}
              className="flex w-full items-start justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm text-ink/90 enabled:hover:bg-raised">

                  <span className="line-clamp-2">{t.title}</span>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${t.status === 'done' ? 'bg-up/10 text-up' : 'bg-raised text-muted'}`}>
                    {t.status === 'done' ? 'learned' : 'queued'}
                  </span>
                </button>
              </li>
          )}
          </ul>
        </>
      }
      {data && data.checked.length > 0 &&
      <>
          <h3 className="mt-4 text-[13px] font-medium text-muted">Answers the market proved right</h3>
          <ul className="mt-1.5 flex flex-col gap-2">
            {data.checked.slice(0, 6).map((c) =>
          <li key={c.question} className="rounded-lg bg-raised/60 px-3 py-2 text-[13px] leading-snug">
                <p className="font-medium text-ink">{c.question}</p>
                <p className="mt-0.5 line-clamp-3 text-ink/80">{c.answer}</p>
              </li>
          )}
          </ul>
        </>
      }
    </Panel>);

}
