import React from 'react';
import { formatPrice } from '../utils/format';
import type { Prediction } from '../types/market';

interface TradeLevelsProps {
  prediction: Prediction;
  price: number;
  decimals: number;
}

/** Where a trade on this call would aim and where it would bail out. */
export function TradeLevels({ prediction, price, decimals }: TradeLevelsProps) {
  const up = prediction.direction === 'up';
  const pctFrom = (v: number) => (v - price) / price * 100;
  const rr = prediction.riskReward;
  const rows = [
  { label: 'Now', value: price, tone: 'text-ink', hint: 'last price' },
  { label: 'Target', value: prediction.candle.close, tone: up ? 'text-up' : 'text-down', hint: 'a typical move this way' },
  { label: 'Stop loss', value: prediction.stopLoss, tone: 'text-down', hint: 'exit if wrong' }];


  return (
    <section aria-labelledby="levels-title">
      <h2 id="levels-title" className="text-[15px] font-semibold text-ink">Trade levels</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-muted">
        From this stock's recent moves, not from the model: the model only says up or down, and how sure.
      </p>
      <dl className="mt-3 divide-y divide-line">
        {rows.map((r) =>
        <div key={r.label} className="flex items-center justify-between gap-3 py-2.5">
            <dt>
              <span className="block text-sm text-ink">{r.label}</span>
              <span className="block text-xs text-muted">{r.hint}</span>
            </dt>
            <dd className="text-right tabular-nums">
              <span className={`block text-[15px] font-semibold ${r.tone}`}>{formatPrice(r.value, decimals)}</span>
              {r.label !== 'Now' &&
            <span className="block text-xs text-muted">
                  {pctFrom(r.value) >= 0 ? '+' : ''}
                  {pctFrom(r.value).toFixed(2)}%
                </span>
            }
            </dd>
          </div>
        )}
      </dl>
      <div className={`mt-3 rounded-lg px-3 py-2.5 text-[13px] leading-relaxed ${rr >= 1 ? 'bg-up/10 text-up' : 'bg-down/10 text-down'}`}>
        <span className="font-semibold tabular-nums">Reward : risk = {rr.toFixed(2)}</span>
        <span className="block text-ink/80">
          {rr >= 1 ? 'Possible gain is bigger than the possible loss.' : 'Possible gain is smaller than the possible loss — usually a skip.'}
        </span>
      </div>
    </section>);

}
