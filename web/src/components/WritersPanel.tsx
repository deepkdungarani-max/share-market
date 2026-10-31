import React from 'react';
import { SparklesIcon } from 'lucide-react';
import { usePoll } from '../hooks/usePoll';
import { agoLabel } from '../utils/format';
import { fetchWriters, type WriterUse } from '../utils/site';
import { Panel } from './Bits';

const KINDS: Record<string, string> = { lesson: 'lessons', help: 'help answers', answer: 'your questions', guide: "Krishna's reviews" };
const DOING: Record<string, string> = { lesson: 'Writing a lesson', help: 'Answering', answer: 'Answering', guide: 'Writing' };

/** "3h 45m", "12 min" */
function span(seconds: number): string {
  const m = Math.max(1, Math.round(seconds / 60));
  return m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m} min`;
}

/** "about 4 min left", from how long this kind of job usually takes this model. */
function left(elapsed: number, usual: number | null): string {
  if (!usual) return 'First job of this kind: no estimate yet';
  const rest = usual - elapsed;
  if (rest < 60) return `Usually takes ${span(usual)}: should finish any moment`;
  return `About ${span(rest)} left (usually takes ${span(usual)})`;
}

/** Drona's AI plans (Google AI Pro accounts through Antigravity, ChatGPT Pro through Codex): what each model is
 *  doing right now, when a used-up quota resets, and the work done. Grouped by plan. */
export function WritersPanel() {
  const { data, error } = usePoll(fetchWriters, 15_000);
  const plans = data ? [...new Set(data.writers.map((w) => w.plan))] : [];
  const count = (s: WriterUse['state']) => data?.writers.filter((w) => w.state === s).length ?? 0;

  return (
    <Panel id="writers-title" icon={SparklesIcon} title="Drona's AI plans">
      {error && <p className="mt-3 text-sm text-down">{error}</p>}
      {data &&
      <>
          <p className="mt-2 text-sm text-muted">
            <span className="font-semibold text-accent">{count('working')} working now</span> ·{' '}
            <span className="text-ink">{count('ready')} on standby</span> ·{' '}
            <span className="text-amber-400">{count('resting')} out of quota</span>
            {count('off') > 0 && <> · {count('off')} not set up</>}
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="text-xs text-muted">
                <tr className="border-b border-line">
                  <th scope="col" className="py-2 pr-3 text-left font-medium">Model</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Right now</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Done in 24 h</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Tokens 24 h</th>
                  <th scope="col" className="py-2 pl-3 text-left font-medium">Last success</th>
                </tr>
              </thead>
              {plans.map((plan) => {
              const rows = data.writers.filter((w) => w.plan === plan);
              return (
                <tbody key={plan}>
                    <tr className="border-b border-line bg-raised/40">
                      <th scope="colgroup" colSpan={5} className="px-2 py-1.5 text-left text-xs font-semibold text-ink">
                        {plan}
                        {rows[0].account && <span className="ml-1.5 font-normal text-muted">{rows[0].account}</span>}
                      </th>
                    </tr>
                    {rows.map((w) => <WriterRow key={w.writer} w={w} />)}
                  </tbody>);

            })}
            </table>
          </div>
          <p className="mt-3 text-xs leading-relaxed text-muted">
            Each plan has its own learner, so all plans study at the same time. Within a plan, the top model writes
            and the ones below are backups: they take over when the one above is out of quota (Opus and Sonnet share
            one Claude quota). Standby means ready but not needed at this moment. Neither CLI reports how much quota is
            left: see Antigravity → Settings → Models, and ChatGPT → Settings → Usage.
          </p>
        </>
      }
    </Panel>);

}

function WriterRow({ w }: {w: WriterUse;}) {
  const failed = w.day.calls - w.day.ok - w.day.limits;
  return (
    <tr className="border-b border-line/60 align-top">
      <td className="whitespace-nowrap py-2.5 pl-2 pr-3 font-medium text-ink">
        {w.writer.replace(/^[a-z0-9]+:/, '').replace('@', ' · ')}
      </td>
      <td className="px-3 py-2.5">
        <State w={w} />
      </td>
      <td className="px-3 py-2.5 text-xs text-muted">
        {Object.keys(w.kinds).length === 0 ? '–' :
        Object.entries(w.kinds).map(([k, n]) =>
        <span key={k} className="block"><span className="tabular-nums text-ink">{n.toLocaleString()}</span> {KINDS[k] ?? k}</span>
        )}
        {failed > 0 && <span className="block text-down" title={w.last_error ?? undefined}>{failed} failed</span>}
      </td>
      <td className="px-3 py-2.5 text-right tabular-nums text-ink">{w.day.tokens.toLocaleString()}</td>
      <td className="py-2.5 pl-3 text-xs text-muted">{w.last_ok ? agoLabel(Date.parse(w.last_ok)) : 'not yet'}</td>
    </tr>);

}

function State({ w }: {w: WriterUse;}) {
  if (w.state === 'working' && w.now) {
    return (
      <div className="flex flex-col gap-0.5">
        <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-accent/15 px-2 py-0.5 text-xs font-semibold text-accent">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" aria-hidden="true" />
          Working · {span(w.now.for)}
        </span>
        <span className="text-xs text-ink/90">{DOING[w.now.kind] ?? 'Writing'}: {w.now.what || '…'}</span>
        <span className="text-xs text-muted">{left(w.now.for, w.now.usual)}</span>
      </div>);

  }
  if (w.state === 'resting') {
    return (
      <span className="w-fit rounded-full bg-amber-400/15 px-2 py-0.5 text-xs font-medium text-amber-400" title={w.last_error ?? undefined}>
        Out of quota · resets in {span(w.rests_for)}
      </span>);

  }
  if (w.state === 'off') {
    return <span className="w-fit rounded-full bg-raised px-2 py-0.5 text-xs font-medium text-muted">Not set up</span>;
  }
  return <span className="w-fit rounded-full bg-up/10 px-2 py-0.5 text-xs font-medium text-up">Standby</span>;
}
