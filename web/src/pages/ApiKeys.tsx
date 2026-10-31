import React, { useState } from 'react';
import { ExternalLinkIcon, KeyRoundIcon, PlusIcon } from 'lucide-react';
import { toast } from 'sonner';
import { PageTitle, Panel } from '../components/Bits';
import { ReadersPanel } from '../components/ReadersPanel';
import { WritersPanel } from '../components/WritersPanel';
import { addKey, type Provider } from '../utils/site';

const PROVIDERS: {key: Provider;label: string;getKey: string;note: string;}[] = [
{
  key: 'groq',
  label: 'Groq',
  getKey: 'https://console.groq.com/keys',
  note: 'Free tier: about 1,000 requests a day per key, 10 news per request. Reports what is left of its limit.'
},
{
  key: 'gemini',
  label: 'Gemini',
  getKey: 'https://aistudio.google.com/apikey',
  note: '25 news per request. Often busy at peak hours; then the key rests a few minutes while the others read.'
},
{
  key: 'openrouter',
  label: 'OpenRouter',
  getKey: 'https://openrouter.ai/settings/keys',
  note: "Free models (NVIDIA Nemotron, Google Gemma…), 30 news per request. Once your account has bought $10 of credit it gets 1,000 free requests a day (about 30,000 news); before that only 50. Narad picks the best free model on its own as OpenRouter's free list changes."
}];


/** Add and remove the cloud keys Narad reads the news with. Every key reads at the same time. */
export function ApiKeys() {
  const [provider, setProvider] = useState<Provider>('groq');
  const [key, setKey] = useState('');
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const chosen = PROVIDERS.find((p) => p.key === provider)!;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const added = await addKey(provider, key, name);
      toast.success(`${added.name} added — Narad is reading with it now`);
      setKey('');
      setName('');
      setVersion((v) => v + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add the key');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <PageTitle icon={KeyRoundIcon} title="API keys">
        Who does the reading and the thinking. Narad reads the news with your AI plans (Gemini on Google AI Pro, GPT on
        ChatGPT Pro) and with any API keys you add here; Drona studies with the plans. Everything reads at the same time,
        and a plan or key that hits its limit rests while the others carry on.
      </PageTitle>

      <Panel id="add-key-title" icon={PlusIcon} title="Add a key">
        <form onSubmit={submit} className="mt-3 flex flex-col gap-4">
          <div className="flex rounded-lg border border-line bg-canvas p-1 sm:w-fit" role="radiogroup" aria-label="Provider">
            {PROVIDERS.map((p) =>
            <button
              key={p.key}
              type="button"
              role="radio"
              aria-checked={provider === p.key}
              onClick={() => setProvider(p.key)}
              className={`flex-1 rounded-md px-4 py-1.5 text-sm font-medium sm:flex-none ${provider === p.key ? 'bg-raised text-ink' : 'text-muted hover:text-ink'}`}>

                {p.label}
              </button>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-[1fr_220px]">
            <label className="flex flex-col gap-1.5 text-sm text-muted">
              {chosen.label} API key
              <input
                type="password"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                autoComplete="off"
                spellCheck={false}
                required
                placeholder={provider === 'groq' ? 'gsk_…' : provider === 'openrouter' ? 'sk-or-v1-…' : 'AIza…'}
                className="rounded-lg border border-line bg-canvas px-3 py-2 font-mono text-sm text-ink focus:border-accent focus:outline-none" />

            </label>
            <label className="flex flex-col gap-1.5 text-sm text-muted">
              Name <span className="sr-only">(optional)</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={40}
                placeholder="optional, e.g. Groq – second account"
                className="rounded-lg border border-line bg-canvas px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none" />

            </label>
          </div>

          <p className="text-xs leading-relaxed text-muted">
            {chosen.note}{' '}
            <a href={chosen.getKey} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent hover:underline">
              Get a {chosen.label} key <ExternalLinkIcon className="h-3 w-3" aria-hidden="true" />
            </a>
          </p>

          {error && <p className="text-sm text-down" role="alert">{error}</p>}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={saving || key.trim() === ''}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-canvas hover:opacity-90 disabled:opacity-50">

              {saving ? `Checking with ${chosen.label}…` : 'Add key'}
            </button>
            <p className="text-xs text-muted">
              The key is checked with {chosen.label} first, then kept on this laptop only (outside the project folder).
              This page only ever shows its last 4 characters.
            </p>
          </div>
        </form>
      </Panel>

      <WritersPanel />

      <ReadersPanel manage version={version} />
    </div>);

}
