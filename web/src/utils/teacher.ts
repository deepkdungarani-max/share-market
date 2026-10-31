import { LOCAL_API } from './marketData';

export interface TeacherAnswer {
  id: number;
  kind: 'question' | 'review';
  question: string;
  answer: string;
  used: {id: number;title: string;}[];
  engine: string;
  created_at: string;
  /** Topics the knowledge base was missing, queued for the learner to study next. */
  queued?: string[];
}

export interface TeacherStatus {
  learned: number;
  queued: number;
  failed: number;
  qa: number;
  words: number;
  deepest: number;
  /** Topics learned and in total at each curriculum depth (0 = the root subjects). */
  levels: {depth: number;done: number;total: number;}[];
  learner: {state: string;at: string;} | null;
  /** model: who wrote the lesson (sonnet, or groq:… / gemini:… while Claude's usage limit was used up). */
  recent: {id: number;title: string;depth: number;learned_at: string;level: string | null;model: string | null;}[];
  /** The beginner-to-expert syllabus (app/syllabus.py), level by level. */
  syllabus?: SyllabusLevel[];
}

export interface SyllabusLevel {
  level: number;
  name: string;
  /** The books and sources the level follows. */
  books: string;
  done: number;
  total: number;
  topics: {id: number;title: string;status: 'pending' | 'done' | 'failed';}[];
}

export interface Lesson {
  id: number;
  title: string;
  depth: number;
  learned_at: string;
  level: string | null;
  body: string;
  sources: {url: string;title: string;}[];
  qa: {question: string;answer: string;difficulty: string | null;}[];
  subtopics: {id: number;title: string;status: string;}[];
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${LOCAL_API}/teacher${path}`, init).catch(() => {
    throw new Error('backend not reachable — is start.bat running?');
  });
  const json = await res.json().catch(() => null);
  if (!res.ok) throw new Error(json?.detail ?? `backend returned ${res.status}`);
  return json as T;
}

const post = (body: object): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body)
});

export const askTeacher = (question: string) => call<TeacherAnswer>('/ask', post({ question }));
export const reviewModels = (question: string) => call<TeacherAnswer>('/review', post({ question }));
export const fetchTeacherStatus = (signal?: AbortSignal) => call<TeacherStatus>('/status', { signal });
export const fetchTeacherHistory = (signal?: AbortSignal) => call<TeacherAnswer[]>('/history', { signal });
export const fetchLesson = (id: number, signal?: AbortSignal) => call<Lesson>(`/lesson/${id}`, { signal });

/** SQLite datetime('now') is UTC without a zone marker. */
export function formatWhen(utc: string): string {
  const d = new Date(utc.replace(' ', 'T') + 'Z');
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}
