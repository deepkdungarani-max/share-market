import React, { useEffect, useState } from 'react';
import { TimerIcon } from 'lucide-react';
import { formatClock, formatCountdown } from '../utils/format';

export function CandleCountdown({ closesAt }: {closesAt: number;}) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <span className="flex items-center gap-2 rounded-full bg-accent/10 px-3 py-1 text-[13px] text-accent" aria-live="off">
      <TimerIcon className="h-4 w-4" aria-hidden="true" />
      Candle closes in <span className="font-semibold tabular-nums">{formatCountdown(closesAt - now)}</span>
      <span className="hidden text-accent/70 xl:inline">({formatClock(closesAt)})</span>
    </span>);

}
