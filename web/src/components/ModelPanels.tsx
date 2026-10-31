import React from 'react';
import { ActivityIcon, ScaleIcon } from 'lucide-react';
import { formatPct } from '../utils/format';
import type { Pipeline, ScoreRow } from '../utils/trikal';
import { MODEL_LABELS, Panel, Stat, rightTone, tone } from './Bits';

/** Chitragupta's scorecard: calls scored, share right and average move in the called direction, per model. */
export function Scorecard({ rows }: {rows: ScoreRow[];}) {
  const ordered = Object.keys(MODEL_LABELS).
  map((m) => rows.find((r) => r.model === m)).
  filter((r): r is ScoreRow => r !== undefined);
  return (
    <Panel id="score-title" icon={ScaleIcon} title="Chitragupta's scorecard">
      {ordered.length === 0 ?
      <p className="mt-3 text-sm leading-relaxed text-muted">
          Every call is scored against the market after its session closes (4 PM IST). Scores appear after the next close
          with the server running.
        </p> :

      <>
          <table className="mt-3 w-full text-sm">
            <thead className="text-xs text-muted">
              <tr className="border-b border-line">
                <th scope="col" className="py-1.5 pr-2 text-left font-medium">Model</th>
                <th scope="col" className="px-2 py-1.5 text-right font-medium">Calls</th>
                <th scope="col" className="px-2 py-1.5 text-right font-medium">Right</th>
                <th scope="col" className="py-1.5 pl-2 text-right font-medium">Avg move</th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((r) =>
            <tr key={r.model} className="border-b border-line/60 last:border-0">
                  <td className="py-2 pr-2 text-ink">{MODEL_LABELS[r.model]}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-muted">{r.calls.toLocaleString()}</td>
                  <td className={`px-2 py-2 text-right font-semibold tabular-nums ${rightTone(r.right_pct)}`}>
                    {r.right_pct === null ? '–' : `${r.right_pct}%`}
                  </td>
                  <td className={`py-2 pl-2 text-right tabular-nums ${tone(r.gain_pct)}`}>
                    {r.gain_pct === null ? '–' : formatPct(r.gain_pct)}
                  </td>
                </tr>
            )}
            </tbody>
          </table>
          <p className="mt-3 text-xs leading-relaxed text-muted">
            50% is a coin flip. Avg move is how far the stock went in the direction called. Narad and Drona are judged on the
            move beyond Nifty, the others on plain up or down.
          </p>
        </>
      }
    </Panel>);

}

/** Narad's and Drona's last 24 hours: news collected and read, the backlog and help requests. */
export function PipelinePanel({ pipeline: p }: {pipeline: Pipeline;}) {
  return (
    <Panel id="pipeline-title" icon={ActivityIcon} title="Last 24 hours">
      <dl className="mt-3 grid grid-cols-2 gap-2">
        <Stat label="News collected" value={p.news_24h.toLocaleString()} />
        <Stat label="Read by Narad" value={p.read_24h.toLocaleString()} />
        <Stat label="Waiting to be read" value={p.unread.toLocaleString()} />
        <Stat label="Answered by Drona" value={p.help_answered_24h.toLocaleString()} />
      </dl>
      <p className="mt-3 text-[13px] text-muted">
        <span className="tabular-nums text-ink">{p.help_pending.toLocaleString()}</span> help{' '}
        {p.help_pending === 1 ? 'request' : 'requests'} waiting for Drona
      </p>
    </Panel>);

}
