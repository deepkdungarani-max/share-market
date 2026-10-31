import React, { useMemo } from 'react';
import { PickerHero } from '../components/PickerHero';
import { PredictionView } from '../components/PredictionView';
import { SanjayCalls } from '../components/SanjayCalls';
import { useMarket } from '../contexts/MarketContext';
import { instrumentsByMarket } from '../data/instruments';
import { modelInfo } from '../data/models';
import { useLocalModelInfo } from '../hooks/useLocalModelInfo';
import { useLocalQuotes } from '../hooks/useLocalQuotes';

export function Predict() {
  const { market, setMarket, selected, select, clear, minutes, setMinutes } = useMarket();
  const localModel = useLocalModelInfo(minutes, market);
  const instruments = instrumentsByMarket[market];
  const instrument = instruments.find((i) => i.symbol === selected[market]);
  const quotes = useLocalQuotes(!instrument);

  // Picker only: live prices from the DB. The prediction view keeps stable instrument
  // objects so the live feed doesn't reset on every quotes poll.
  const pickerInstruments = useMemo(
    () => quotes.data ?
    instruments.map((i) => quotes.data?.[i.symbol] ? { ...i, price: quotes.data[i.symbol].price, changePct: quotes.data[i.symbol].changePct } : i) :
    instruments,
    [instruments, quotes.data]
  );

  if (!instrument) {
    return (
      <>
        <PickerHero
          market={market}
          onMarketChange={setMarket}
          instruments={pickerInstruments}
          quotes={quotes.data}
          quotesError={quotes.error}
          onSelect={select} />

        <SanjayCalls market={market} onSelect={select} />
      </>);

  }

  return (
    <PredictionView
      key={market}
      market={market}
      instrument={instrument}
      instruments={instruments}
      minutes={minutes}
      model={localModel ?? modelInfo}
      onMinutesChange={setMinutes}
      onSelect={select}
      onClear={clear} />);

}
