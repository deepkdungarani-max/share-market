import React from 'react';
import { MarketWatch } from './MarketWatch';
import { SavedSymbols } from './SavedSymbols';
import { SharePicker } from './SharePicker';
import type { Quote } from '../utils/marketData';
import type { Instrument, Market } from '../types/market';

interface PickerHeroProps {
  market: Market;
  onMarketChange: (market: Market) => void;
  instruments: Instrument[];
  /** Live prices from the local backend; null until the first load. */
  quotes: Record<string, Quote> | null;
  quotesError: string | null;
  onSelect: (symbol: string) => void;
}

const MARKETS: {key: Market;label: string;}[] = [{ key: 'stocks', label: 'NSE stocks' }, { key: 'forex', label: 'Forex (INR pairs)' }];

export function PickerHero({ market, onMarketChange, instruments, quotes, quotesError, onSelect }: PickerHeroProps) {
  const forex = market === 'forex';
  return (
    <div className="flex w-full flex-1 flex-col">
      <section className="mx-auto w-full max-w-2xl pt-4 text-center lg:pt-10">
        <div className="mx-auto mb-6 flex w-fit rounded-lg border border-line bg-surface p-1" role="group" aria-label="Market">
          {MARKETS.map((m) =>
          <button
            key={m.key}
            type="button"
            onClick={() => onMarketChange(m.key)}
            aria-pressed={market === m.key}
            className={`rounded-md px-4 py-1.5 text-sm font-medium ${market === m.key ? 'bg-raised text-ink' : 'text-muted hover:text-ink'}`}>

              {m.label}
            </button>
          )}
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">{forex ? 'Pick a rupee pair' : 'Pick a stock'}</h1>
        <p className="mx-auto mt-3 max-w-lg text-base text-muted">
          See whether the next candle is more likely to close <span className="font-medium text-up">up</span> or{' '}
          <span className="font-medium text-down">down</span> — and how sure your model is.
        </p>
        <div className="mt-8 text-left">
          <SharePicker instruments={instruments} onSelect={onSelect} placeholder={forex ? 'Search USDINR, EURINR…' : 'Search RELIANCE, TCS, INFY…'} showPrices={!!quotes} autoFocus />
        </div>
        {forex &&
        <p className="mt-4 text-xs leading-relaxed text-muted">
            Only rupee pairs: the forex an Indian resident may trade, on NSE/BSE currency derivatives. Pairs like EUR/USD
            on overseas apps are not allowed under RBI rules. Rates are the 24-hour interbank ones, Monday to Friday.
          </p>
        }
        <SavedSymbols instruments={instruments} showChange={!!quotes} onSelect={onSelect} />
      </section>

      <MarketWatch instruments={instruments} quotes={quotes} error={quotesError} onSelect={onSelect} />
    </div>);

}
