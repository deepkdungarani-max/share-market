import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRightIcon, LayoutDashboardIcon, NewspaperIcon, SparklesIcon } from 'lucide-react';
import { CallTag, Empty, ErrorNote, PageTitle, PairTag, Panel, SymbolChip, signed, tone } from '../components/Bits';
import { PipelinePanel, Scorecard } from '../components/ModelPanels';
import { usePoll } from '../hooks/usePoll';
import { agoLabel } from '../utils/format';
import { fetchOverview, type ModelHealth, type ModelState, type Note } from '../utils/site';
import { formatWhen } from '../utils/teacher';
import { formatSession } from '../utils/trikal';

const PAGE: Record<string, string> = {
  narad: '/news',
  drona: '/teacher',
  sanjay: '/chart',
  chanakya: '/world',
  trikal: '/trikal',
  chitragupta: '/scores'
};

const STATES: Record<ModelState, {label: string;className: string;}> = {
  ok: { label: 'Working', className: 'bg-up/10 text-up' },
  waiting: { label: 'Waiting', className: 'bg-raised text-muted' },
  late: { label: 'Late', className: 'bg-amber-400/15 text-amber-400' },
  down: { label: 'Down', className: 'bg-down/10 text-down' },
  off: { label: 'Not started', className: 'bg-raised text-muted' }
};

export function Overview() {
  const { data, error } = usePoll(fetchOverview, 60_000);
  const late = data?.models.filter((m) => m.state === 'late' || m.state === 'down') ?? [];

  return (
    <div className="flex flex-col gap-6">
      <PageTitle icon={LayoutDashboardIcon} title="Overview">
        What every model is doing, today's strongest calls, and how the calls have scored.
      </PageTitle>
      {error && <ErrorNote>{error}</ErrorNote>}

      {data &&
      <>
          {late.length > 0 &&
        <p className="rounded-xl border border-amber-400/40 bg-amber-400/10 px-4 py-3 text-sm leading-relaxed text-amber-400" role="status">
              {late.map((m) => m.name).join(', ')} {late.length === 1 ? 'is' : 'are'} behind schedule. Usually the laptop was
              asleep (every model picks up again within a minute of waking) or the server (start.bat) isn't running. The
              Krishna tab says what is wrong.
            </p>
        }

          <section aria-labelledby="models-title">
            <h2 id="models-title" className="sr-only">Models</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {data.models.map((m) => <ModelCard key={m.key} model={m} />)}
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-8">
            <div className="flex min-w-0 flex-col gap-6">
              <Panel
              id="strongest-title"
              icon={SparklesIcon}
              title={data.as_of ? `Strongest calls for the session after ${formatSession(data.as_of)}` : 'Strongest calls'}
              aside={<MoreLink to="/trikal">All calls</MoreLink>}>

                {data.strongest.length === 0 ?
              <Empty>No Trikal call yet. It calls on weekdays from 06:00 IST, once Sanjay and Chanakya have called.</Empty> :

              <ul className="mt-3 flex flex-col divide-y divide-line/60">
                    {data.strongest.map((c) =>
                <li key={c.symbol} className="flex items-center justify-between gap-3 py-2.5">
                        <span className="font-medium text-ink">{c.symbol}<PairTag market={c.market} /></span>
                        <CallTag p={c.prob_up} />
                      </li>
                )}
                  </ul>
              }
              </Panel>

              <Panel id="headlines-title" icon={NewspaperIcon} title="Latest news on tracked stocks" aside={<MoreLink to="/news">All news</MoreLink>}>
                {data.headlines.length === 0 ?
              <Empty>No notes on tracked stocks yet. Narad reads the news while the server runs.</Empty> :

              <ul className="mt-3 flex flex-col divide-y divide-line/60">
                    {data.headlines.map((n) => <Headline key={n.id} note={n} />)}
                  </ul>
              }
              </Panel>
            </div>

            <aside className="flex flex-col gap-4">
              <Scorecard rows={data.scorecard} />
              <PipelinePanel pipeline={data.pipeline} />
            </aside>
          </div>
        </>
      }
    </div>);

}

function ModelCard({ model: m }: {model: ModelHealth;}) {
  const state = STATES[m.state];
  return (
    <Link to={PAGE[m.key] ?? '/'} className="group flex flex-col gap-2 rounded-xl border border-line bg-surface p-4 hover:border-accent/60 focus-visible:border-accent">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[15px] font-semibold text-ink group-hover:text-accent">{m.name}</p>
          <p className="text-xs text-muted">{m.role}</p>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${state.className}`}>{state.label}</span>
      </div>
      <p className="line-clamp-2 text-[13px] leading-snug text-ink/85">{m.detail}</p>
      <p className="text-xs text-muted">{m.last ? `last active ${agoLabel(Date.parse(m.last))}` : 'never active yet'}</p>
    </Link>);

}

function Headline({ note: n }: {note: Note;}) {
  return (
    <li className="flex flex-col gap-1.5 py-3">
      <a href={n.url} target="_blank" rel="noreferrer" className="text-sm font-medium text-ink hover:text-accent">{n.title}</a>
      <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
        {n.symbols.map((s) => <SymbolChip key={s} symbol={s} />)}
        <span className={`font-semibold tabular-nums ${tone(n.sentiment)}`}>{signed(n.sentiment)}</span>
        {n.help?.answer && <span>· Drona <span className={`font-semibold ${tone(n.help.answer.sentiment)}`}>{signed(n.help.answer.sentiment)}</span></span>}
        <span>· {n.source}{n.published && ` · ${formatWhen(n.published)}`}</span>
      </div>
    </li>);

}

function MoreLink({ to, children }: {to: string;children: React.ReactNode;}) {
  return (
    <Link to={to} className="inline-flex items-center gap-1 text-[13px] font-medium text-accent hover:underline">
      {children} <ArrowRightIcon className="h-3.5 w-3.5" aria-hidden="true" />
    </Link>);

}
