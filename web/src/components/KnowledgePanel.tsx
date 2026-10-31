import React, { useEffect, useState } from 'react';
import { BrainIcon } from 'lucide-react';
import { fetchTeacherStatus, formatWhen, type TeacherStatus } from '../utils/teacher';

const POLL_MS = 30_000;

/** What the teacher has learned so far and what its self-study loop is doing right now. */
export function KnowledgePanel({ onOpenLesson }: {onOpenLesson: (id: number) => void;}) {
  const [status, setStatus] = useState<TeacherStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    const load = () =>
    fetchTeacherStatus(ctrl.signal).
    then((s) => {
      setStatus(s);
      setError(null);
    }).
    catch((err: unknown) => !ctrl.signal.aborted && setError(err instanceof Error ? err.message : 'Not available'));
    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      ctrl.abort();
      clearInterval(id);
    };
  }, []);

  return (
    <section aria-labelledby="knowledge-title" className="rounded-xl border border-line bg-surface p-4">
      <h2 id="knowledge-title" className="flex items-center gap-2 text-[15px] font-semibold text-ink">
        <BrainIcon className="h-4 w-4 text-accent" aria-hidden="true" /> What it knows
      </h2>

      {error && <p className="mt-3 text-sm text-down">{error}</p>}

      {status &&
      <>
          <dl className="mt-3 grid grid-cols-2 gap-2">
            <Stat label="Lessons learned" value={status.learned.toLocaleString()} />
            <Stat label="Hard Q&A" value={status.qa.toLocaleString()} />
            <Stat label="Words studied" value={status.words.toLocaleString()} />
            <Stat label="Deepest level" value={String(status.deepest)} />
          </dl>
          <div className="mt-3 flex flex-col gap-2">
            {status.levels.map((l) =>
          <div key={l.depth} className="text-[13px]">
                <div className="flex justify-between text-muted">
                  <span>{LEVELS[l.depth] ?? `Level ${l.depth}`}</span>
                  <span className="tabular-nums"><span className="text-ink">{l.done.toLocaleString()}</span> of {l.total.toLocaleString()}</span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-raised" role="presentation">
                  <div className="h-1.5 rounded-full bg-accent" style={{ width: `${l.total ? (100 * l.done) / l.total : 0}%` }} />
                </div>
              </div>
          )}
          </div>
          <p className="mt-3 text-xs leading-relaxed text-muted">
            <span className="tabular-nums text-ink">{status.queued.toLocaleString()}</span> topics queued
            {status.failed > 0 && <> · {status.failed} failed</>}. Basics first, then deeper. Every lesson queues 3–6
            deeper topics, so the queue keeps growing: there is always more to learn.
          </p>
          {status.learner &&
        <p className="mt-2 rounded-lg bg-raised/60 px-3 py-2 text-[13px] leading-snug text-ink/90">
              {status.learner.state}
              <span className="block text-xs text-muted">updated {new Date(status.learner.at).toLocaleTimeString()}</span>
            </p>
        }

          <h3 className="mt-4 text-[13px] font-medium text-muted">Recently learned</h3>
          {status.recent.length === 0 ?
        <p className="mt-2 text-sm text-muted">Nothing yet — the first lesson takes about 2 minutes once the server is running.</p> :

        <ul className="mt-1.5 flex flex-col">
              {status.recent.map((r) =>
          <li key={r.id}>
                  <button
              type="button"
              onClick={() => onOpenLesson(r.id)}
              className="w-full rounded-md px-2 py-1.5 text-left text-sm text-ink/90 hover:bg-raised">

                    <span className="line-clamp-2">{r.title}</span>
                    <span className="text-xs text-muted">
                      level {r.depth} · {r.level ?? '–'}{r.model && ` · ${r.model}`} · {formatWhen(r.learned_at)}
                    </span>
                  </button>
                </li>
          )}
            </ul>
        }
        </>
      }
    </section>);

}

/** Curriculum depth 0 = the 42 root subjects; each level below goes one step deeper. */
const LEVELS: Record<number, string> = { 0: 'Core subjects', 1: 'Level 1 · deeper', 2: 'Level 2 · advanced', 3: 'Level 3 · expert' };

function Stat({ label, value }: {label: string;value: string;}) {
  return (
    <div className="rounded-lg bg-raised/60 px-3 py-2">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums text-ink">{value}</dd>
    </div>);

}
