import React, { useState } from 'react';
import { AlertTriangleIcon, CheckCircle2Icon, CompassIcon, InfoIcon, ListChecksIcon, RefreshCwIcon, ScrollTextIcon, WrenchIcon, XCircleIcon } from 'lucide-react';
import { toast } from 'sonner';
import { Empty, ErrorNote, PageTitle, Panel } from '../components/Bits';
import { usePoll } from '../hooks/usePoll';
import { agoLabel } from '../utils/format';
import { fetchKrishna, krishnaCheck, krishnaReview, type Krishna as KrishnaView, type KrishnaFinding } from '../utils/site';
import { formatWhen } from '../utils/teacher';

const LEVEL = {
  problem: { icon: XCircleIcon, tone: 'text-down', label: 'Problem' },
  warning: { icon: AlertTriangleIcon, tone: 'text-amber-400', label: 'Warning' },
  info: { icon: InfoIcon, tone: 'text-muted', label: 'Note' }
} as const;

const KIND: Record<string, {label: string;tone: string;}> = {
  fixed: { label: 'Fixed', tone: 'bg-up/10 text-up' },
  problem: { label: 'Problem', tone: 'bg-down/10 text-down' },
  warning: { label: 'Warning', tone: 'bg-amber-400/15 text-amber-400' },
  resolved: { label: 'Resolved', tone: 'bg-raised text-muted' },
  review: { label: 'Review', tone: 'bg-accent/15 text-accent' }
};

/** Krishna, the guide: what is wrong right now, what it fixed on its own, and its daily review of every model. */
export function Krishna() {
  const [version, setVersion] = useState(0);
  const { data, error } = usePoll(fetchKrishna, 60_000, [version]);
  const [busy, setBusy] = useState<'check' | 'review' | null>(null);

  const act = async (what: 'check' | 'review') => {
    setBusy(what);
    try {
      await (what === 'check' ? krishnaCheck() : krishnaReview());
      toast.success(what === 'check' ? 'Checked everything' : "Today's review is ready");
      setVersion((v) => v + 1);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Krishna could not do that right now');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <PageTitle icon={CompassIcon} title="Krishna">
        The guide. Every 10 minutes Krishna checks every model, fixes what is safe to fix on its own, and tells you what
        needs you. Once a day after 19:00 IST it reviews the whole team and sets Drona's study where the models are weakest.
      </PageTitle>

      {error && <ErrorNote>{error}</ErrorNote>}
      {data &&
      <>
          <NowPanel data={data} busy={busy === 'check'} onCheck={() => act('check')} />
          <ReviewPanel data={data} busy={busy === 'review'} onReview={() => act('review')} />
          <LogPanel data={data} />
        </>
      }
    </div>);

}

function NowPanel({ data, busy, onCheck }: {data: KrishnaView;busy: boolean;onCheck: () => void;}) {
  const order = { problem: 0, warning: 1, info: 2 };
  const findings = [...data.findings].sort((a, b) => order[a.level] - order[b.level]);
  const problems = findings.filter((f) => f.level === 'problem').length;
  const warnings = findings.filter((f) => f.level === 'warning').length;

  return (
    <Panel
      id="krishna-now"
      icon={ListChecksIcon}
      title="Right now"
      aside={
      <button
        type="button"
        onClick={onCheck}
        disabled={busy}
        className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink hover:bg-raised disabled:opacity-50">

          <RefreshCwIcon className={`h-3.5 w-3.5 ${busy ? 'animate-spin' : ''}`} aria-hidden="true" />
          {busy ? 'Checking…' : 'Check now'}
        </button>
      }>

      <p className="mt-2 text-sm text-muted">
        {findings.length === 0 ?
        <span className="inline-flex items-center gap-1.5 font-medium text-up">
            <CheckCircle2Icon className="h-4 w-4" aria-hidden="true" /> Everything is running
          </span> :
        <>
            <span className={problems ? 'font-semibold text-down' : 'text-ink'}>{problems} {problems === 1 ? 'problem' : 'problems'}</span> ·{' '}
            <span className={warnings ? 'font-semibold text-amber-400' : 'text-ink'}>{warnings} {warnings === 1 ? 'warning' : 'warnings'}</span>
          </>
        }
        {data.checked_at && <> · checked {agoLabel(Date.parse(data.checked_at))}</>}
      </p>
      {findings.length > 0 &&
      <ul className="mt-3 flex flex-col divide-y divide-line/60">
          {findings.map((f, i) => <FindingRow key={`${f.area}-${i}`} finding={f} />)}
        </ul>
      }
    </Panel>);

}

function FindingRow({ finding: f }: {finding: KrishnaFinding;}) {
  const level = LEVEL[f.level];
  const Icon = level.icon;
  return (
    <li className="flex gap-3 py-2.5">
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${level.tone}`} aria-label={level.label} />
      <div className="text-sm">
        <p className="text-ink">
          <span className="font-semibold">{f.area}</span> · {f.message}
        </p>
        {f.todo && <p className="mt-0.5 text-xs text-muted">{f.todo}</p>}
      </div>
    </li>);

}

function ReviewPanel({ data, busy, onReview }: {data: KrishnaView;busy: boolean;onReview: () => void;}) {
  const r = data.review;
  return (
    <Panel
      id="krishna-review"
      icon={ScrollTextIcon}
      title={r ? `Review of ${formatWhen(r.at)}` : 'Daily review'}
      aside={
      <button
        type="button"
        onClick={onReview}
        disabled={busy}
        className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink hover:bg-raised disabled:opacity-50">

          <RefreshCwIcon className={`h-3.5 w-3.5 ${busy ? 'animate-spin' : ''}`} aria-hidden="true" />
          {busy ? 'Writing… a few minutes' : 'Review now'}
        </button>
      }>

      {!r ?
      <Empty>No review yet. Krishna writes one each day after 19:00 IST, or now if you press "Review now".</Empty> :

      <div className="mt-3 flex flex-col gap-4">
          <p className="text-sm leading-relaxed text-ink/90">{r.summary}</p>
          {r.advice.length > 0 &&
        <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Advice for each model</h3>
              <ul className="mt-2 flex flex-col gap-2">
                {r.advice.map((a, i) =>
            <li key={`${a.model}-${i}`} className="text-sm leading-relaxed">
                    <span className="font-semibold text-ink">{a.model}</span>
                    <span className="text-ink/85"> · {a.advice}</span>
                  </li>
            )}
              </ul>
            </div>
        }
          {r.study.length > 0 &&
        <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Study set for Drona</h3>
              <ul className="mt-2 flex flex-col gap-1.5">
                {r.study.map((s) =>
            <li key={s.title} className="text-sm">
                    <span className="text-ink">{s.title}</span>
                    {s.why && <span className="text-muted"> · {s.why}</span>}
                    {!r.queued.includes(s.title) && <span className="text-xs text-muted"> (already known to Drona)</span>}
                  </li>
            )}
              </ul>
            </div>
        }
          <p className="text-xs text-muted">Written by {r.writer.replace(/^agy2?:|^codex:/, '').replace('@', ' · ')}.</p>
        </div>
      }
    </Panel>);

}

function LogPanel({ data }: {data: KrishnaView;}) {
  return (
    <Panel id="krishna-log" icon={WrenchIcon} title="What Krishna found and fixed">
      {data.log.length === 0 ?
      <Empty>Nothing yet: Krishna writes here when it fixes something, finds a new problem, or sees one go away.</Empty> :

      <ul className="mt-3 flex flex-col divide-y divide-line/60">
          {data.log.map((e, i) =>
        <li key={`${e.at}-${i}`} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2 text-sm">
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${KIND[e.kind]?.tone ?? 'bg-raised text-muted'}`}>
                {KIND[e.kind]?.label ?? e.kind}
              </span>
              <span className="font-medium text-ink">{e.area}</span>
              <span className="min-w-0 flex-1 text-ink/85">{e.message}</span>
              <span className="text-xs text-muted">{agoLabel(Date.parse(e.at))}</span>
            </li>
        )}
        </ul>
      }
    </Panel>);

}
