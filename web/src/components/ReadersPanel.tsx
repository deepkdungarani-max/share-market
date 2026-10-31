import React, { useState } from 'react';
import { KeyRoundIcon, PauseIcon, PlayIcon, Trash2Icon } from 'lucide-react';
import { toast } from 'sonner';
import { usePoll } from '../hooks/usePoll';
import { agoLabel } from '../utils/format';
import { fetchReaders, pauseKey, removeKey, type KeyReader } from '../utils/site';
import { Panel } from './Bits';

/** Every key Narad reads the news with (Gemini, Groq) and the local Ollama backup: state and work so far.
 *  `manage` adds a Remove button per key; a change of `version` loads the list again (after a key is added). */
export function ReadersPanel({ manage = false, version = 0 }: {manage?: boolean;version?: number;}) {
  const [removed, setRemoved] = useState(0);
  const { data, error } = usePoll(fetchReaders, 20_000, [version, removed]);
  const [busy, setBusy] = useState<string | null>(null);

  const togglePause = async (k: KeyReader) => {
    const pause = k.state !== 'paused';
    setBusy(k.id);
    try {
      await pauseKey(k.id, pause);
      toast.success(`${k.name} ${pause ? 'paused' : 'resumed'}`);
      setRemoved((n) => n + 1);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not change the key');
    } finally {
      setBusy(null);
    }
  };

  const remove = async (k: KeyReader) => {
    if (!window.confirm(`Remove ${k.name} (${k.hint})? Narad stops reading with it.`)) return;
    setBusy(k.id);
    try {
      await removeKey(k.id);
      toast.success(`${k.name} removed`);
      setRemoved((n) => n + 1);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not remove the key');
    } finally {
      setBusy(null);
    }
  };

  return (
    <Panel id="readers-title" icon={KeyRoundIcon} title="Who reads the news" aside={<p className="text-xs text-muted">since the server started</p>}>
      {error && <p className="mt-3 text-sm text-down">{error}</p>}
      {data &&
      <>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="text-xs text-muted">
                <tr className="border-b border-line">
                  <th scope="col" className="py-2 pr-3 text-left font-medium">Key</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">State</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Requests</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">News read</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Limits hit</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Limit left</th>
                  <th scope="col" className="py-2 pl-3 text-left font-medium">Model · last read</th>
                  {manage && <th scope="col" className="py-2 pl-3"><span className="sr-only">Pause or remove</span></th>}
                </tr>
              </thead>
              <tbody>
                {data.keys.map((k) =>
              <tr key={k.id} className="border-b border-line/60 align-top last:border-0">
                    <td className="whitespace-nowrap py-2.5 pr-3">
                      <span className="font-medium text-ink">{k.name}</span>
                      <span className="ml-1.5 text-xs text-muted">{k.hint} · {k.batch} per request</span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5">
                      {k.state === 'paused' ?
                  <span className="rounded-full bg-raised px-2 py-0.5 text-xs font-medium text-muted">Paused</span> :
                  k.state === 'reading' ?
                  <span className="rounded-full bg-up/10 px-2 py-0.5 text-xs font-medium text-up">Reading</span> :
                  <span className="rounded-full bg-amber-400/15 px-2 py-0.5 text-xs font-medium text-amber-400">
                          Resting {Math.max(1, Math.ceil(k.rests_for / 60))} min
                        </span>
                  }
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-ink">{k.requests.toLocaleString()}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums font-semibold text-ink">{k.items.toLocaleString()}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-muted" title={k.last_error ?? undefined}>{k.failures}</td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-xs text-muted"><LimitLeft reader={k} /></td>
                    <td className="py-2.5 pl-3 text-xs text-muted">
                      {k.model ?? '–'}
                      {k.last_ok && <span className="block">{agoLabel(Date.parse(k.last_ok))}</span>}
                    </td>
                    {manage &&
                <td className="whitespace-nowrap py-2 pl-3 text-right">
                        <button
                    type="button"
                    onClick={() => togglePause(k)}
                    disabled={busy === k.id}
                    aria-label={`${k.state === 'paused' ? 'Resume' : 'Pause'} ${k.name}`}
                    title={k.state === 'paused' ? 'Resume' : 'Pause'}
                    className="rounded-md p-1.5 text-muted hover:bg-raised hover:text-ink disabled:opacity-50">

                          {k.state === 'paused' ?
                    <PlayIcon className="h-4 w-4" aria-hidden="true" /> :
                    <PauseIcon className="h-4 w-4" aria-hidden="true" />}
                        </button>
                        {!isPlan(k) &&
                  <button
                    type="button"
                    onClick={() => remove(k)}
                    title="Remove"
                    disabled={busy === k.id}
                    aria-label={`Remove ${k.name}`}
                    className="rounded-md p-1.5 text-muted hover:bg-down/10 hover:text-down disabled:opacity-50">

                            <Trash2Icon className="h-4 w-4" aria-hidden="true" />
                          </button>
                  }
                      </td>
                }
                  </tr>
              )}
                {data.keys.length === 0 &&
              <tr className="border-b border-line/60">
                    <td colSpan={manage ? 8 : 7} className="py-3 text-sm text-muted">No cloud keys yet: add one on the API keys tab.</td>
                  </tr>
              }
                <tr>
                  <td className="whitespace-nowrap py-2.5 pr-3">
                    <span className="font-medium text-ink">Ollama</span>
                    <span className="ml-1.5 text-xs text-muted">{data.ollama.model} · on this laptop</span>
                  </td>
                  <td className="px-3 py-2.5" colSpan={manage ? 7 : 6}>
                    <span className="rounded-full bg-raised px-2 py-0.5 text-xs font-medium text-muted">
                      {data.ollama.state === 'off' ? 'Off: the news is read by Gemini and ChatGPT' :
                  data.ollama.state === 'standby' ? 'Backup: reads only while every reader rests' : 'Reading'}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          {data.per_model.length > 0 &&
        <p className="mt-3 text-xs leading-relaxed text-muted">
              Notes in the last 24 hours:{' '}
              {data.per_model.map((m, i) =>
          <span key={m.model}>
                  {i > 0 && ' · '}
                  <span className="text-ink">{m.model}</span> {m.notes.toLocaleString()}
                </span>
          )}
              . Hover "Limits hit" to see the last error. The AI plans (Google AI Pro, ChatGPT Pro) read 30 items per
              call, at most one call a minute each, and rest when their quota runs out until it resets. Gemini keys don't
              report what is left of their limits: see{' '}
              <a href="https://aistudio.google.com/usage" target="_blank" rel="noreferrer" className="text-accent hover:underline">AI Studio usage</a>.
            </p>
        }
        </>
      }
    </Panel>);

}

/** An AI plan reader (Google AI Pro through agy, ChatGPT through Codex): paused, never removed. */
function isPlan(reader: KeyReader): boolean {
  return ['agy', 'agy2', 'codex'].includes(reader.provider);
}

/** "812 of 1,000 requests today · 6.2k of 8k tokens this minute" from what Groq last reported. */
function LimitLeft({ reader }: {reader: KeyReader;}) {
  const l = reader.limits;
  if (!l) {
    return <span>{isPlan(reader) ? 'plan quota: see its settings' : reader.provider === 'openrouter' ? '1,000 free requests a day' :
      reader.provider === 'gemini' ? 'not reported' : '–'}</span>;
  }
  const n = (v: string | null) => (v === null ? '?' : Number(v).toLocaleString());
  if (reader.provider === 'openrouter') {
    // OpenRouter counts free-model requests per UTC day: 50 until the account has bought $10 of credit, 1,000 after
    return (
      <span>
        <span className="text-ink">{n(l.requests_left)}</span> of {n(l.requests_limit)} free requests left today
        <span className="block">resets 05:30 IST{l.requests_limit === '50' && ' · $10 of credit raises it to 1,000'}</span>
      </span>);

  }
  return (
    <span>
      <span className="text-ink">{n(l.requests_left)}</span> of {n(l.requests_limit)} requests today
      <span className="block"><span className="text-ink">{n(l.tokens_left)}</span> of {n(l.tokens_limit)} tokens this minute</span>
    </span>);

}
