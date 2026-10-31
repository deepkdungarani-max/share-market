import React, { useEffect, useRef, useState } from 'react';
import { Loader2Icon, XIcon } from 'lucide-react';
import { useDismiss } from '../hooks/useDismiss';
import { fetchLesson, type Lesson } from '../utils/teacher';
import { Markdown } from './Markdown';

/** One learned lesson: the text, its hard Q&A, sources, and the deeper subtopics it opened. */
export function LessonDialog({ id, onOpen, onClose }: {id: number;onOpen: (id: number) => void;onClose: () => void;}) {
  const panel = useRef<HTMLDivElement>(null);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [error, setError] = useState<string | null>(null);
  useDismiss(panel, true, onClose);

  useEffect(() => {
    const ctrl = new AbortController();
    setLesson(null);
    setError(null);
    fetchLesson(id, ctrl.signal).
    then(setLesson).
    catch((err: unknown) => !ctrl.signal.aborted && setError(err instanceof Error ? err.message : 'Could not load'));
    panel.current?.scrollTo(0, 0);
    return () => ctrl.abort();
  }, [id]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-canvas/70 backdrop-blur-sm">
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={lesson?.title ?? 'Lesson'}
        className="h-full w-full max-w-3xl overflow-y-auto border-l border-line bg-surface px-4 py-5 sm:px-6">

        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            {lesson &&
            <p className="text-xs text-muted">
                Level {lesson.depth} · {lesson.level ?? '–'} · {lesson.qa.length} hard Q&A
              </p>
            }
            <h2 className="mt-1 text-lg font-semibold text-ink">{lesson?.title ?? 'Lesson'}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-md p-1.5 text-muted hover:bg-raised hover:text-ink">
            <XIcon className="h-5 w-5" />
          </button>
        </div>

        {error && <p className="mt-4 text-sm text-down">{error}</p>}
        {!lesson && !error && <Loader2Icon className="mt-6 h-5 w-5 animate-spin text-accent" aria-label="Loading" />}

        {lesson &&
        <>
            <div className="mt-4">
              <Markdown>{lesson.body}</Markdown>
            </div>

            {lesson.qa.length > 0 &&
          <section className="mt-6">
                <h3 className="text-[15px] font-semibold text-ink">Hard questions</h3>
                <div className="mt-2 flex flex-col gap-2">
                  {lesson.qa.map((q, i) =>
              <details key={i} className="rounded-lg border border-line bg-canvas/50 px-3 py-2">
                      <summary className="cursor-pointer text-sm font-medium text-ink">
                        {q.difficulty && <span className="mr-2 text-xs font-normal uppercase text-accent">{q.difficulty}</span>}
                        {q.question}
                      </summary>
                      <div className="mt-2 border-t border-line pt-2">
                        <Markdown>{q.answer}</Markdown>
                      </div>
                    </details>
              )}
                </div>
              </section>
          }

            {lesson.subtopics.length > 0 &&
          <section className="mt-6">
                <h3 className="text-[15px] font-semibold text-ink">Goes deeper into</h3>
                <ul className="mt-2 flex flex-col gap-1 text-sm">
                  {lesson.subtopics.map((s) =>
              <li key={s.id}>
                      {s.status === 'done' ?
                <button type="button" onClick={() => onOpen(s.id)} className="text-left text-accent hover:underline">
                          {s.title}
                        </button> :

                <span className="text-muted">
                          {s.title} <span className="text-xs">({s.status === 'pending' ? 'queued' : s.status})</span>
                        </span>
                }
                    </li>
              )}
                </ul>
              </section>
          }

            {lesson.sources.length > 0 &&
          <section className="mt-6 pb-6">
                <h3 className="text-[15px] font-semibold text-ink">Sources</h3>
                <ul className="mt-2 flex flex-col gap-1 text-sm">
                  {lesson.sources.map((s) =>
              <li key={s.url} className="truncate">
                      <a href={s.url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                        {s.title || s.url}
                      </a>
                    </li>
              )}
                </ul>
              </section>
          }
          </>
        }
      </div>
    </div>);

}
