import React from 'react';
import { AlertTriangleIcon, MoonIcon } from 'lucide-react';
import type { MarketStatus } from '../types/market';

interface StatusNoticesProps {
  status: MarketStatus;
  feedError: string | null;
  modelError: string | null;
}

export function StatusNotices({ status, feedError, modelError }: StatusNoticesProps) {
  const notices: {key: string;warn: boolean;text: React.ReactNode;}[] = [];

  if (!status.open) {
    notices.push({
      key: 'closed',
      warn: false,
      text:
      <>
          <span className="font-medium text-ink">Market is closed</span> ({status.detail}). The prediction is for the first candle of the
          next session, based on the last session. Alerts are paused.
        </>

    });
  }
  if (feedError) {
    notices.push({
      key: 'feed',
      warn: true,
      text: <>Couldn't refresh prices ({feedError}). Showing the last data received — check that start.bat is running.</>
    });
  }
  if (modelError) {
    notices.push({
      key: 'model',
      warn: true,
      text: <>Your model didn't answer ({modelError}). Showing the indicator readings only — check that start.bat is running.</>
    });
  }

  if (notices.length === 0) return null;

  return (
    <div className="flex flex-col gap-2" role="status">
      {notices.map((n) =>
      <p
        key={n.key}
        className={`flex items-start gap-3 rounded-xl px-4 py-3 text-sm leading-relaxed ${
        n.warn ? 'bg-down/10 text-ink/90' : 'bg-surface text-muted ring-1 ring-line'}`
        }>

          <span className="mt-0.5 shrink-0">
            {n.warn ?
          <AlertTriangleIcon className="h-4 w-4 text-down" aria-hidden="true" /> :
          <MoonIcon className="h-4 w-4 text-muted" aria-hidden="true" />}
          </span>
          <span>{n.text}</span>
        </p>
      )}
    </div>);

}
