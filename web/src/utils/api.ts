import { LOCAL_API } from './marketData';

/** GET a JSON endpoint of the candlecast backend; errors carry the backend's own message. */
export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${LOCAL_API}${path}`, { signal }).catch(() => {
    throw new Error('backend not reachable — is start.bat running?');
  });
  const json = await res.json().catch(() => null);
  if (!res.ok) throw new Error(json?.detail ?? `backend returned ${res.status}`);
  return json as T;
}

/** POST (or DELETE) to the backend; errors carry the backend's own message. */
export async function sendJson<T>(method: 'POST' | 'DELETE', path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${LOCAL_API}${path}`, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body)
  }).catch(() => {
    throw new Error('backend not reachable — is start.bat running?');
  });
  const json = await res.json().catch(() => null);
  if (!res.ok) throw new Error(json?.detail ?? `backend returned ${res.status}`);
  return json as T;
}
