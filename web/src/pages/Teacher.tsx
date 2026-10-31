import React, { useEffect, useState } from 'react';
import { BookOpenIcon, GraduationCapIcon, Loader2Icon, SendIcon, ShieldCheckIcon } from 'lucide-react';
import { toast } from 'sonner';
import { KnowledgePanel } from '../components/KnowledgePanel';
import { LessonDialog } from '../components/LessonDialog';
import { SyllabusPanel } from '../components/SyllabusPanel';
import { MistakesPanel } from '../components/MistakesPanel';
import { Markdown } from '../components/Markdown';
import { askTeacher, fetchTeacherHistory, formatWhen, reviewModels, type TeacherAnswer } from '../utils/teacher';

const EXAMPLES = [
'Iron condor me short strikes ka delta kaise choose karte hai, aur gamma risk expiry ke paas kyu badhta hai?',
'Why can a stock fall on good quarterly results? Explain with expectations, guidance and positioning.',
'DCF me terminal value 70% se zyada ho to valuation pe kitna trust kare? Sensitivity ka example do.',
'Walk-forward backtest me look-ahead bias kaise ghus jata hai? 5 subtle examples do.'];


export function Teacher() {
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState<'ask' | 'review' | null>(null);
  const [answers, setAnswers] = useState<TeacherAnswer[]>([]);
  const [lessonId, setLessonId] = useState<number | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchTeacherHistory(ctrl.signal).then(setAnswers).catch(() => undefined);
    return () => ctrl.abort();
  }, []);

  const run = async (kind: 'ask' | 'review') => {
    const q = question.trim();
    if (busy || (kind === 'ask' && !q)) return;
    setBusy(kind);
    try {
      const a = kind === 'ask' ? await askTeacher(q) : await reviewModels(q);
      setAnswers((prev) => [a, ...prev]);
      setQuestion('');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Teacher did not answer');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-8">
      <div className="min-w-0">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/15 text-accent" aria-hidden="true">
            <GraduationCapIcon className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-ink">Market teacher</h1>
            <p className="text-sm text-muted">Ask anything about the stock market — basics to expert. Answers draw on what it has learned.</p>
          </div>
        </div>

        <form
          className="mt-5 rounded-xl border border-line bg-surface p-4"
          onSubmit={(e) => {
            e.preventDefault();
            run('ask');
          }}>

          <label htmlFor="teacher-question" className="sr-only">Your question</label>
          <textarea
            id="teacher-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) run('ask');
            }}
            rows={3}
            placeholder="Hard question puchho… English, Hindi, Gujarati or Hinglish"
            className="w-full resize-y rounded-lg border border-line bg-canvas px-3 py-2.5 text-[15px] text-ink placeholder:text-muted focus:border-accent focus:outline-none" />

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => run('review')}
              disabled={busy !== null}
              title="Teacher checks your LightGBM prediction models; anything typed above is sent as your note"
              className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-sm font-medium text-ink hover:bg-raised disabled:opacity-50">

              {busy === 'review' ?
              <Loader2Icon className="h-4 w-4 animate-spin" aria-hidden="true" /> :
              <ShieldCheckIcon className="h-4 w-4" aria-hidden="true" />}
              Review my prediction model
            </button>
            <button
              type="submit"
              disabled={busy !== null || !question.trim()}
              className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-canvas hover:bg-accent/90 disabled:opacity-50">

              {busy === 'ask' ?
              <Loader2Icon className="h-4 w-4 animate-spin" aria-hidden="true" /> :
              <SendIcon className="h-4 w-4" aria-hidden="true" />}
              Ask
              <kbd className="hidden text-xs font-normal opacity-70 sm:inline">Ctrl+Enter</kbd>
            </button>
          </div>
        </form>

        {answers.length === 0 && !busy &&
        <div className="mt-4">
            <p className="text-[13px] text-muted">Try one:</p>
            <div className="mt-2 flex flex-col gap-2">
              {EXAMPLES.map((ex) =>
            <button
              key={ex}
              type="button"
              onClick={() => setQuestion(ex)}
              className="rounded-lg border border-line bg-surface px-3 py-2 text-left text-sm text-ink/90 hover:border-accent/60">

                  {ex}
                </button>
            )}
            </div>
          </div>
        }

        {busy &&
        <div className="mt-5 flex items-center gap-3 rounded-xl border border-line bg-surface px-4 py-4 text-sm text-muted" role="status">
            <Loader2Icon className="h-5 w-5 animate-spin text-accent" aria-hidden="true" />
            {busy === 'ask' ?
          'Teacher is thinking and checking sources — usually 30 seconds to 2 minutes.' :
          'Teacher is reviewing your prediction models…'}
          </div>
        }

        <div className="mt-5 flex flex-col gap-4">
          {answers.map((a) =>
          <AnswerCard key={a.id} answer={a} onOpenLesson={setLessonId} />
          )}
        </div>

        <SyllabusPanel onOpenLesson={setLessonId} />
      </div>

      <aside className="flex flex-col gap-4 lg:sticky lg:top-8 lg:max-h-[calc(100vh-4rem)] lg:self-start lg:overflow-y-auto">
        <KnowledgePanel onOpenLesson={setLessonId} />
        <MistakesPanel onOpenLesson={setLessonId} />
      </aside>

      {lessonId !== null && <LessonDialog id={lessonId} onOpen={setLessonId} onClose={() => setLessonId(null)} />}
    </div>);

}

function AnswerCard({ answer, onOpenLesson }: {answer: TeacherAnswer;onOpenLesson: (id: number) => void;}) {
  const review = answer.kind === 'review';
  return (
    <article className="rounded-xl border border-line bg-surface p-4 sm:p-5">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <h2 className="min-w-0 flex-1 text-[15px] font-semibold text-ink">
          {review &&
          <span className="mr-2 rounded-md bg-accent/15 px-1.5 py-0.5 text-xs font-medium text-accent">Model review</span>
          }
          {answer.question}
        </h2>
        <span className="text-xs text-muted">
          {answer.engine} · {formatWhen(answer.created_at)}
        </span>
      </header>
      <div className="mt-3 border-t border-line pt-3">
        <Markdown>{answer.answer}</Markdown>
      </div>
      {(answer.used.length > 0 || answer.queued && answer.queued.length > 0) &&
      <footer className="mt-4 flex flex-col gap-2 border-t border-line pt-3 text-xs text-muted">
          {answer.used.length > 0 &&
        <div className="flex flex-wrap items-center gap-1.5">
              <BookOpenIcon className="h-3.5 w-3.5" aria-hidden="true" /> From lessons:
              {answer.used.map((u) =>
          <button
            key={u.id}
            type="button"
            onClick={() => onOpenLesson(u.id)}
            className="max-w-full truncate rounded-md bg-raised px-2 py-0.5 text-ink/80 hover:text-accent">

                  {u.title}
                </button>
          )}
            </div>
        }
          {answer.queued && answer.queued.length > 0 &&
        <p>Learning next because of this question: {answer.queued.join(' · ')}</p>
        }
        </footer>
      }
    </article>);

}
