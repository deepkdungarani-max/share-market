import React, { useEffect } from 'react';
import { AlertTriangleIcon, ArrowLeftIcon, RefreshCwIcon, StarIcon } from 'lucide-react';
import { AlertButton } from './AlertButton';
import { ChartPanel } from './ChartPanel';
import { FactorsPanel } from './FactorsPanel';
import { HistoryPanel } from './HistoryPanel';
import { MinutesPicker } from './MinutesPicker';
import { ShareSwitcher } from './ShareSwitcher';
import { StatusNotices } from './StatusNotices';
import { TradeLevels } from './TradeLevels';
import { VerdictPanel } from './VerdictPanel';
import { useMarket } from '../contexts/MarketContext';
import { usePreferences } from '../contexts/PreferencesContext';
import { useAlertWatcher } from '../hooks/useAlertWatcher';
import { usePrediction } from '../hooks/usePrediction';
import { BAR_SIZES, barSize } from '../utils/marketData';
import type { Instrument, Market, ModelInfo } from '../types/market';

const card = 'rounded-2xl border border-line bg-surface p-5 sm:p-6';
const iconButton =
'flex h-10 w-10 items-center justify-center rounded-lg text-muted ring-1 ring-line transition-colors duration-150 hover:bg-raised hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/60';

interface PredictionViewProps {
  market: Market;
  instrument: Instrument;
  instruments: Instrument[];
  minutes: number;
  model: ModelInfo;
  onMinutesChange: (minutes: number) => void;
  onSelect: (symbol: string) => void;
  onClear: () => void;
}

/** Mounted only when a symbol is chosen — the model runs for this one instrument alone. */
export function PredictionView({
  market,
  instrument,
  instruments,
  minutes,
  model,
  onMinutesChange,
  onSelect,
  onClear
}: PredictionViewProps) {
  const { status } = useMarket();
  const { watchlist, toggleWatch, pushRecent } = usePreferences();
  const data = usePrediction({ instrument, market, minutes, status });
  const watched = watchlist[market].includes(instrument.symbol);

  useEffect(() => pushRecent(market, instrument.symbol), [market, instrument.symbol, pushRecent]);
  // The backend serves 15m / 1h only — snap any other value so the picker matches what's shown
  useEffect(() => {
    if (!BAR_SIZES.includes(minutes)) onMinutesChange(barSize(minutes));
  }, [minutes, onMinutesChange]);
  useAlertWatcher(market, instrument.symbol, data.prediction, data.barMinutes, status.open && !data.loading);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <button type="button" onClick={onClear} aria-label="Back to all stocks" className={iconButton}>
            <ArrowLeftIcon className="h-5 w-5" aria-hidden="true" />
          </button>
          <ShareSwitcher instrument={instrument} instruments={instruments} onSelect={onSelect} />
        </div>
        <div className="flex items-center gap-2">
          <MinutesPicker value={data.barMinutes} onChange={onMinutesChange} options={BAR_SIZES} />
          <button
            type="button"
            onClick={() => toggleWatch(market, instrument.symbol)}
            aria-pressed={watched}
            aria-label={watched ? `Remove ${instrument.symbol} from watchlist` : `Add ${instrument.symbol} to watchlist`}
            className={`${iconButton} ${watched ? 'text-accent' : ''}`}>

            <StarIcon className={`h-[18px] w-[18px] ${watched ? 'fill-accent' : ''}`} aria-hidden="true" />
          </button>
          <AlertButton market={market} symbol={instrument.symbol} />
        </div>
      </div>

      <h1 className="sr-only">{instrument.symbol} next-candle prediction</h1>

      {!data.ready ?
      data.feedStatus === 'error' ?
      <FeedError message={data.feedError} onRetry={data.retry} /> :
      <LoadingCards /> :

      <>
          <StatusNotices status={status} feedError={data.feedError} modelError={data.modelError} />

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="order-2 flex min-w-0 flex-col gap-6 lg:order-1">
              <section className={`${card} flex h-[440px] flex-col sm:h-[500px] lg:h-auto lg:min-h-[500px] lg:flex-1`}>
                <ChartPanel
                instrument={instrument}
                candles={data.candles}
                forming={data.forming}
                prediction={data.prediction}
                history={data.history}
                barMinutes={data.barMinutes}
                price={data.price}
                change={data.change}
                closesAt={data.closesAt}
                loading={data.loading} />

              </section>
            </div>

            <div className="order-1 flex flex-col gap-6 lg:order-2">
              <div className={card}>
                <VerdictPanel
                prediction={data.prediction}
                minutes={data.barMinutes}
                model={model}
                modelSource={data.modelSource}
                loading={data.loading} />

              </div>
              <div className={card}>
                <TradeLevels prediction={data.prediction} price={data.price} decimals={instrument.decimals} />
              </div>
            </div>
          </div>

          <div className={`grid gap-6 lg:grid-cols-2 transition-opacity duration-200 ${data.loading ? 'opacity-40' : 'opacity-100'}`}>
            <div className={card}>
              <HistoryPanel history={data.history} minutes={data.barMinutes} decimals={instrument.decimals} />
            </div>
            <div className={card}>
              <FactorsPanel prediction={data.prediction} modelSource={data.modelSource} />
            </div>
          </div>
        </>
      }
    </div>);

}

function LoadingCards() {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]" aria-busy="true" aria-label="Loading live data">
      <div className={`${card} h-[500px]`}>
        <div className="h-8 w-48 animate-pulse rounded-lg bg-raised" />
        <div className="mt-6 h-[400px] animate-pulse rounded-xl bg-raised/60" />
      </div>
      <div className={`${card} h-[500px]`}>
        <div className="h-5 w-32 animate-pulse rounded bg-raised" />
        <div className="mt-5 h-14 w-40 animate-pulse rounded-xl bg-raised" />
        <div className="mt-5 h-4 w-full animate-pulse rounded bg-raised" />
        <p className="mt-6 text-sm text-muted">Loading live candles…</p>
      </div>
    </div>);

}

function FeedError({ message, onRetry }: {message: string | null;onRetry: () => void;}) {
  return (
    <div className={`${card} flex flex-col items-center px-6 py-14 text-center`} role="alert">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-down/10 text-down">
        <AlertTriangleIcon className="h-6 w-6" aria-hidden="true" />
      </span>
      <h2 className="mt-4 text-lg font-semibold text-ink">Couldn't load live data</h2>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">
        {message ?? 'Unknown error'}. Make sure <span className="font-medium text-ink">start.bat</span> is running and the
        internet is on, then try again.
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-6 flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-canvas transition-opacity duration-150 hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50">

        <RefreshCwIcon className="h-4 w-4" aria-hidden="true" />
        Retry
      </button>
    </div>);

}
