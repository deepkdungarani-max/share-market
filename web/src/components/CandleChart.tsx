import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { formatCandleTime, formatClock, formatPct, formatPrice, formatVolume, shortTimeframe } from '../utils/format';
import type { Candle, HistoryEntry, Prediction } from '../types/market';

interface CandleChartProps {
  width: number;
  height: number;
  candles: Candle[];
  forming: Candle | null;
  prediction: Prediction;
  history: HistoryEntry[];
  decimals: number;
  minutes: number;
}

const PAD_R = 84;
const PAD_T = 36;
const PAD_B = 6;
const UP = 'rgb(var(--up))';
const DOWN = 'rgb(var(--down))';
const MUTED = 'rgb(var(--muted))'; // a call on a candle that closed unchanged: neither right nor wrong
const TIP_W = 196;

export function CandleChart({ width: W, height: H, candles, forming, prediction, history, decimals, minutes }: CandleChartProps) {
  const [hover, setHover] = useState<{index: number;y: number;} | null>(null);

  const p = prediction.candle;
  const volH = Math.max(32, Math.round(H * 0.15));
  const priceBottom = H - PAD_B - volH - 12;
  const levels = [...candles, p, ...(forming ? [forming] : [])];
  const max = Math.max(...levels.map((c) => c.high), prediction.stopLoss);
  const min = Math.min(...levels.map((c) => c.low), prediction.stopLoss);
  const range = max - min || 1;
  const plotW = W - PAD_R;
  const slot = plotW / (candles.length + 2);
  const bodyW = slot * 0.62;
  const pIndex = candles.length;

  const y = (v: number) => PAD_T + (max - v) / range * (priceBottom - PAD_T);
  const priceAt = (py: number) => max - (py - PAD_T) / (priceBottom - PAD_T) * range;
  const x = (i: number) => slot * i + slot / 2;
  const maxVol = Math.max(...candles.map((c) => c.volume), forming?.volume ?? 0, 1);
  const vTop = (v: number) => H - PAD_B - v / maxVol * volH;

  const gridCount = priceBottom - PAD_T > 260 ? 6 : 4;
  const gridLevels = Array.from({ length: gridCount + 1 }, (_, i) => min + range * i / gridCount);
  const lastPrice = forming?.close ?? candles[candles.length - 1].close;
  const pColor = prediction.direction === 'up' ? UP : DOWN;
  const sepX = x(pIndex) - slot / 2 - 2;
  const marks = new Map(history.map((h) => [h.start, h]));

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    if (mx > plotW || my > priceBottom + 12) return setHover(null);
    setHover({ index: Math.min(pIndex, Math.max(0, Math.floor(mx / slot))), y: Math.min(priceBottom, Math.max(PAD_T, my)) });
  };

  // Right-axis tags (stop loss, target, last price) are 18px tall: push them apart so they never
  // overlap, and hide grid labels they would cover.
  const tags = [
  { key: 'sl', value: prediction.stopLoss, label: 'SL', fill: 'rgb(var(--down) / 0.18)', text: DOWN },
  { key: 'tp', value: p.close, label: 'TP', fill: prediction.direction === 'up' ? 'rgb(var(--up) / 0.18)' : 'rgb(var(--down) / 0.18)', text: pColor },
  { key: 'now', value: lastPrice, label: '', fill: 'rgb(var(--raised))', text: 'rgb(var(--ink))' }].
  map((t) => ({ ...t, ty: y(t.value) })).
  sort((a, b) => a.ty - b.ty);
  for (let i = 1; i < tags.length; i++) tags[i].ty = Math.max(tags[i].ty, tags[i - 1].ty + 19);
  const coveredByTag = (py: number) => tags.some((t) => Math.abs(t.ty - py) < 15);

  const tag = (t: (typeof tags)[number]) =>
  <g key={t.key}>
      <rect x={plotW + 4} y={t.ty - 9} width={PAD_R - 6} height={18} rx={3} fill="rgb(var(--surface))" />
      <rect x={plotW + 4} y={t.ty - 9} width={PAD_R - 6} height={18} rx={3} fill={t.fill} />
      <text x={plotW + 9} y={t.ty + 4} fill={t.text} fontSize={11} fontWeight={600}>
        {t.label} {formatPrice(t.value, decimals)}
      </text>
    </g>;


  const tipLeft = hover ? x(hover.index) + 14 + TIP_W > W ? x(hover.index) - 14 - TIP_W : x(hover.index) + 14 : 0;

  return (
    <>
      <svg
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        className="absolute inset-0 cursor-crosshair font-sans"
        role="img"
        aria-label="Candlestick chart with volume, predicted next candle, stop loss and target"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}>
        
        {gridLevels.map((lvl) =>
        <g key={lvl}>
            <line x1={0} x2={plotW} y1={y(lvl)} y2={y(lvl)} stroke="rgb(var(--line))" strokeWidth={1} strokeDasharray="2 4" />
            {!coveredByTag(y(lvl)) &&
          <text x={plotW + 10} y={y(lvl) + 4} fill="rgb(var(--muted))" fontSize={12}>
                {formatPrice(lvl, decimals)}
              </text>
          }
          </g>
        )}

        <line x1={0} x2={plotW} y1={H - PAD_B - volH - 4} y2={H - PAD_B - volH - 4} stroke="rgb(var(--line))" strokeWidth={1} />
        <text x={plotW + 10} y={H - PAD_B - volH + 8} fill="rgb(var(--muted))" fontSize={10}>
          vol
        </text>

        {candles.map((c, i) => {
          const up = c.close >= c.open;
          const color = up ? UP : DOWN;
          const mark = marks.get(c.time);
          return (
            <g key={c.time}>
              <rect x={x(i) - bodyW / 2} y={vTop(c.volume)} width={bodyW} height={H - PAD_B - vTop(c.volume)} fill={color} opacity={0.3} />
              <line x1={x(i)} x2={x(i)} y1={y(c.high)} y2={y(c.low)} stroke={color} strokeWidth={1} />
              <rect
                x={x(i) - bodyW / 2}
                y={y(Math.max(c.open, c.close))}
                width={bodyW}
                height={Math.max(1, Math.abs(y(c.open) - y(c.close)))}
                fill={color}
                rx={1} />
              
              {mark &&
              <circle cx={x(i)} cy={y(c.high) - 7} r={2.5} fill={mark.hit ? UP : 'none'} stroke={mark.hit ? UP : mark.hit === null ? MUTED : DOWN} strokeWidth={1.25} />
              }
            </g>);

        })}

        <line x1={0} x2={plotW} y1={y(lastPrice)} y2={y(lastPrice)} stroke="rgb(var(--muted))" strokeDasharray="2 4" strokeWidth={1} />

        <line x1={sepX} x2={sepX} y1={PAD_T - 22} y2={H - PAD_B} stroke="rgb(var(--accent))" strokeDasharray="3 3" strokeWidth={1} opacity={0.6} />
        <text x={sepX - 6} y={PAD_T - 24} fill="rgb(var(--accent))" fontSize={10} fontWeight={500} textAnchor="end">
          {forming ? 'Now →' : 'Next →'}
        </text>

        <line x1={sepX} x2={plotW} y1={y(prediction.stopLoss)} y2={y(prediction.stopLoss)} stroke={DOWN} strokeDasharray="4 3" strokeWidth={1} opacity={0.8} />
        <line x1={sepX} x2={plotW} y1={y(p.close)} y2={y(p.close)} stroke={pColor} strokeDasharray="4 3" strokeWidth={1} opacity={0.8} />

        <motion.g
          key={`${p.time}-${prediction.direction}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.25, ease: [0.23, 1, 0.32, 1] }}>
          
          <line x1={x(pIndex)} x2={x(pIndex)} y1={y(p.high)} y2={y(p.low)} stroke={pColor} strokeWidth={1} strokeDasharray="3 2" />
          <rect
            x={x(pIndex) - bodyW / 2}
            y={y(Math.max(p.open, p.close))}
            width={bodyW}
            height={Math.max(1, Math.abs(y(p.open) - y(p.close)))}
            fill={pColor}
            fillOpacity={0.14}
            stroke={pColor}
            strokeWidth={1.25}
            strokeDasharray="3 2"
            rx={1} />
          
        </motion.g>

        {forming &&
        <g>
            <rect
            x={x(pIndex) - bodyW / 2}
            y={vTop(forming.volume)}
            width={bodyW}
            height={H - PAD_B - vTop(forming.volume)}
            fill={forming.close >= forming.open ? UP : DOWN}
            opacity={0.3} />
          
            <line x1={x(pIndex)} x2={x(pIndex)} y1={y(forming.high)} y2={y(forming.low)} stroke="rgb(var(--ink))" strokeWidth={1} />
            <rect
            x={x(pIndex) - bodyW * 0.28}
            y={y(Math.max(forming.open, forming.close))}
            width={bodyW * 0.56}
            height={Math.max(1, Math.abs(y(forming.open) - y(forming.close)))}
            fill={forming.close >= forming.open ? UP : DOWN}
            rx={1} />
          
          </g>
        }

        {tags.map(tag)}

        {hover &&
        <g pointerEvents="none">
            <line x1={x(hover.index)} x2={x(hover.index)} y1={PAD_T - 10} y2={H - PAD_B} stroke="rgb(var(--muted))" strokeWidth={1} opacity={0.5} />
            <line x1={0} x2={plotW} y1={hover.y} y2={hover.y} stroke="rgb(var(--muted))" strokeWidth={1} opacity={0.5} />
            <rect x={plotW + 4} y={hover.y - 9} width={PAD_R - 6} height={18} rx={3} fill="rgb(var(--ink))" />
            <text x={plotW + 9} y={hover.y + 4} fill="rgb(var(--canvas))" fontSize={10} fontWeight={600}>
              {formatPrice(priceAt(hover.y), decimals)}
            </text>
          </g>
        }
      </svg>

      {hover &&
      <div
        className="pointer-events-none absolute z-10 rounded-xl border border-line bg-canvas/95 p-3 text-xs shadow-[0_12px_32px_-12px_rgba(0,0,0,0.9)]"
        style={{ left: tipLeft, top: PAD_T, width: TIP_W }}>
        
          {hover.index < candles.length ?
        <CandleTip candle={candles[hover.index]} minutes={minutes} decimals={decimals} entry={marks.get(candles[hover.index].time)} /> :

        <PredictedTip prediction={prediction} forming={forming} minutes={minutes} decimals={decimals} />
        }
        </div>
      }
    </>);

}

function TipRow({ label, value, tone = 'text-ink' }: {label: string;value: string;tone?: string;}) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-muted">{label}</span>
      <span className={tone}>{value}</span>
    </div>);

}

function CandleTip({ candle: c, minutes, decimals, entry }: {candle: Candle;minutes: number;decimals: number;entry?: HistoryEntry;}) {
  const up = c.close >= c.open;
  return (
    <div className="space-y-1">
      <p className="mb-1.5 text-ink">
        {minutes >= 1440 ? formatCandleTime(c.time, minutes) : <>{formatClock(c.time)}–{formatClock(c.time + minutes * 60_000)}</>}
      </p>
      <TipRow label="open" value={formatPrice(c.open, decimals)} />
      <TipRow label="high" value={formatPrice(c.high, decimals)} />
      <TipRow label="low" value={formatPrice(c.low, decimals)} />
      <TipRow label="close" value={formatPrice(c.close, decimals)} tone={up ? 'text-up' : 'text-down'} />
      <TipRow label="change" value={formatPct((c.close - c.open) / c.open * 100)} tone={up ? 'text-up' : 'text-down'} />
      <TipRow label="volume" value={formatVolume(c.volume)} />
      {entry &&
      <p className={`mt-1.5 border-t border-line pt-1.5 ${entry.hit === null ? 'text-muted' : entry.hit ? 'text-up' : 'text-down'}`}>
          Model said {entry.predicted.toUpperCase()} {entry.probability}% · {entry.hit === null ? 'no move' : entry.hit ? 'right' : 'wrong'}
        </p>
      }
    </div>);

}

function PredictedTip({ prediction, forming, minutes, decimals }: {prediction: Prediction;forming: Candle | null;minutes: number;decimals: number;}) {
  const up = prediction.direction === 'up';
  return (
    <div className="space-y-1">
      <p className={`mb-1.5 font-semibold ${up ? 'text-up' : 'text-down'}`}>
        Predicted {up ? 'UP' : 'DOWN'} {prediction.probability}%
      </p>
      <TipRow label="target" value={formatPrice(prediction.candle.close, decimals)} tone={up ? 'text-up' : 'text-down'} />
      <TipRow label="high" value={formatPrice(prediction.candle.high, decimals)} />
      <TipRow label="low" value={formatPrice(prediction.candle.low, decimals)} />
      <TipRow label="stop loss" value={formatPrice(prediction.stopLoss, decimals)} tone="text-down" />
      {forming &&
      <div className="mt-1.5 space-y-1 border-t border-line pt-1.5">
          <p className="text-ink">Live {shortTimeframe(minutes)} candle</p>
          <TipRow label="open" value={formatPrice(forming.open, decimals)} />
          <TipRow label="now" value={formatPrice(forming.close, decimals)} tone={forming.close >= forming.open ? 'text-up' : 'text-down'} />
          <TipRow label="volume" value={formatVolume(forming.volume)} />
        </div>
      }
    </div>);

}