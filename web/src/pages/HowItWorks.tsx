import React from 'react';
import { WorkflowIcon } from 'lucide-react';
import { PageTitle, Panel } from '../components/Bits';

type Kind = '' | 'help' | 'accent' | 'judge';

const STROKE: Record<Kind, string> = { '': 'stroke-muted', help: 'stroke-amber-400', accent: 'stroke-accent', judge: 'stroke-muted' };
const TEXT: Record<Kind, string> = { '': 'fill-muted', help: 'fill-amber-400', accent: 'fill-accent', judge: 'fill-muted' };

const NODES: {name: string;role: string;x: number;y: number;kind: Kind;}[] = [
{ name: 'Narad', role: 'news reader', x: 416, y: 65, kind: '' },
{ name: 'Sanjay', role: 'price + chart', x: 676, y: 178, kind: '' },
{ name: 'Chanakya', role: 'world markets', x: 156, y: 178, kind: '' },
{ name: 'Drona', role: 'teacher + help', x: 676, y: 402, kind: 'help' },
{ name: 'Trikal', role: 'main prediction', x: 416, y: 515, kind: 'accent' },
{ name: 'Chitragupta', role: 'judge', x: 66, y: 490, kind: 'judge' },
{ name: 'Krishna', role: 'guide', x: 766, y: 490, kind: 'judge' }];

// Each model's line into the shared memory, labelled with the table it writes
const SPOKES: {x1: number;y1: number;x2: number;y2: number;kind: Kind;label: string;cx: number;cy: number;w: number;}[] = [
{ x1: 500, y1: 125, x2: 500, y2: 225, kind: '', label: 'news_notes', cx: 500, cy: 176, w: 84 },
{ x1: 690, y1: 238, x2: 605, y2: 275, kind: '', label: 'signals', cx: 648, cy: 257, w: 64 },
{ x1: 310, y1: 238, x2: 395, y2: 275, kind: '', label: 'signals', cx: 352, cy: 257, w: 64 },
{ x1: 690, y1: 402, x2: 605, y2: 365, kind: 'help', label: 'help', cx: 648, cy: 384, w: 46 },
{ x1: 500, y1: 515, x2: 500, y2: 415, kind: 'accent', label: 'signals', cx: 500, cy: 465, w: 64 },
{ x1: 202, y1: 490, x2: 395, y2: 380, kind: 'judge', label: 'scores', cx: 299, cy: 435, w: 58 }];


const MODELS = [
{ name: 'Narad', deva: 'नारद', role: 'News reader', why: 'Narad Muni carried news between all the worlds.',
  does: 'Every 15 minutes it pulls 16 publisher and RBI feeds, NSE\'s live filings and Google News for each tracked company, then reads them 30 at a time with Gemini on your Google AI Pro accounts and GPT on ChatGPT Pro (and any API keys you add): companies, kind of news, good and bad facts, sentiment and confidence. It skips the same story from a second outlet.' },
{ name: 'Sanjay', deva: 'संजय', role: 'Price and chart', why: 'Sanjaya watched the Mahabharata war from afar and narrated it live.',
  does: 'LightGBM models on candles, RSI, MACD, EMA and volume, retrained every hour: one set for NSE stocks, one for the rupee pairs (USD, EUR, GBP and JPY against INR). After each 4 PM close it saves every tracked stock\'s chance of closing up next session, and each morning each pair\'s.' },
{ name: 'Chanakya', deva: 'चाणक्य', role: 'World markets', why: 'Chanakya wrote the Arthashastra, on economics and statecraft.',
  does: 'From 06:00 IST it reads the overnight S&P 500, Nasdaq, Brent, dollar-rupee, US 10-year yield, gold, dollar index and India VIX, and calls every tracked stock and rupee pair with a model per market retrained on every earlier session.' },
{ name: 'Drona', deva: 'द्रोण', role: 'Teacher and helper', why: 'Dronacharya taught both the Kauravas and the Pandavas.',
  does: 'Studies a beginner-to-expert syllabus from the books traders and quants learn from, topic by topic with web search through Antigravity on your Google AI Pro quota, answers your questions and Narad\'s help requests, and every weekday morning makes its own call on every symbol: the chart, the world, the news and the other models\' calls, weighed with the lessons that fit. Wrong calls on big moves become its study topics.' },
{ name: 'Trikal', deva: 'त्रिकाल', role: 'Main prediction', why: 'A trikaldarshi sees the past, the present and the future.',
  does: 'Takes Drona\'s call first, since Drona has already weighed everything with what it learned. Without it, or if after 150 scored calls Drona does worse than the plain average of Sanjay and Chanakya, it uses that average (which beat every learned combination on 2022–2026 days no model had seen).' },
{ name: 'Chitragupta', deva: 'चित्रगुप्त', role: 'Judge', why: 'Chitragupta keeps the record of every being\'s deeds.',
  does: 'After each close it scores every call against what the stock did: news calls on the move beyond Nifty, the others on plain up or down. Only prices decide; it stays outside the circle.' },
{ name: 'Krishna', deva: 'कृष्ण', role: 'Guide', why: 'Krishna was Arjuna\'s charioteer, who saw the whole battlefield and guided him in the Gita.',
  does: 'Every 10 minutes it checks every model: threads, schedules, AI plans, news keys, disk and scores. It fixes what is safe on its own (restarts a stopped model, retries failed topics and news, rests a failing AI plan) and lists the rest for you. Each evening it reviews the whole team with your best AI plan and queues study topics for Drona where the models are weakest.' }];


const DAY = [
{ when: 'All day', what: 'Narad collects and reads the news. Mixed or unsure notes, and kinds of news it has a poor record on, go to Drona.' },
{ when: 'All day', what: 'Drona answers help requests ten at a time, using its matching lessons and Sanjay\'s and Chanakya\'s calls with their records, then keeps studying.' },
{ when: 'Every 10 min', what: 'Krishna checks every model and fixes what is safe to fix; the rest it lists on its page.' },
{ when: '4 PM onwards', what: 'Chitragupta scores every call whose session has closed. Sanjay retrains and makes its call for the next session.' },
{ when: 'Overnight', what: 'Drona turns wrong calls on 3%+ moves into study topics, and help answers the market proved right into lessons.' },
{ when: '19:00 IST', what: 'Krishna reviews the whole team with your best AI plan and sets Drona\'s study where the models are weakest.' },
{ when: '19:00 IST', what: 'The data keeper downloads the day into market.db: NSE\'s bhavcopy, and 1-minute, 15-minute, hourly and daily bars of every listed company, the indices and the rupee pairs. A day missed while the laptop was off is fetched as soon as it is back, while Yahoo still has it (1-minute bars: about 30 days).' },
{ when: '06:00 IST', what: 'Once the US session and the rupee\'s day have closed, Chanakya reads the world and calls every tracked stock and rupee pair. Sanjay calls the pairs too.' },
{ when: '06:00–06:30', what: 'Drona reads each symbol\'s chart, the overnight world, the news and Sanjay\'s and Chanakya\'s calls with the lessons that fit, and makes its call with its reasons.' },
{ when: '06:00–09:15', what: 'Trikal takes Drona\'s call first (the models\' average where Drona has none) and records the news, refreshing every hour. At the 09:15 open the call freezes.' }];


export function HowItWorks() {
  return (
    <div className="flex flex-col gap-6">
      <PageTitle icon={WorkflowIcon} title="How it works">
        Seven models share one memory on the E: drive. Each does one job, they help each other, every call is scored, and
        Krishna watches over all of them. They call NSE stocks and the rupee pairs (forex) alike.
      </PageTitle>

      <Panel id="circle-title" title="The circle">
        <div className="mt-3 overflow-x-auto">
          <Diagram />
        </div>
        <p className="mt-2 text-[13px] leading-relaxed text-muted">
          Each line is labelled with the table that model writes to; any model can read the whole memory. Chitragupta stands
          outside the circle because it scores only against the actual market, never another model's opinion. Krishna stands
          outside too: it watches every model, fixes what stops, and guides them.
        </p>
      </Panel>

      <section aria-labelledby="models-title">
        <h2 id="models-title" className="text-[15px] font-semibold text-ink">The seven models</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {MODELS.map((m) =>
          <article key={m.name} className="flex flex-col gap-2 rounded-xl border border-line bg-surface p-4">
              <div className="flex items-baseline gap-2">
                <h3 className="text-lg font-semibold text-ink">{m.name}</h3>
                <span className="text-muted" lang="hi">{m.deva}</span>
              </div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">{m.role}</p>
              <p className="text-[13px] text-muted">{m.why}</p>
              <p className="text-sm leading-relaxed text-ink/90">{m.does}</p>
            </article>
          )}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel id="day-title" title="A day in the circle">
          <ol className="mt-3 flex flex-col gap-3">
            {DAY.map((d, i) =>
            <li key={i} className="grid grid-cols-[96px_minmax(0,1fr)] gap-3 text-sm">
                <span className="font-medium text-accent">{d.when}</span>
                <span className="leading-relaxed text-ink/90">{d.what}</span>
              </li>
            )}
          </ol>
        </Panel>

        <Panel id="rules-title" title="Three rules that keep it honest">
          <ul className="mt-3 flex flex-col gap-3 text-sm leading-relaxed text-muted">
            <li>
              <strong className="font-semibold text-ink">One round of help.</strong> Drona answers; nobody passes the question on,
              so no model asks another in circles.
            </li>
            <li>
              <strong className="font-semibold text-ink">Chitragupta stays outside.</strong> If the judge trusted the models'
              opinions, they could all be wrong together and nobody would notice.
            </li>
            <li>
              <strong className="font-semibold text-ink">No future data.</strong> Every call uses only what was known before its
              session opened, and every test trains only on days before the ones it predicts. The Backtest page does this
              at full size: trained on every NSE session before a cutoff, it calls every company, every day of the year after,
              and it can train a fresh model every quarter or month of that year, as the live model keeps learning.
            </li>
          </ul>
        </Panel>
      </div>
    </div>);

}

function Diagram() {
  return (
    <svg
      viewBox="0 0 1000 640"
      role="img"
      aria-label="Narad, Sanjay, Chanakya, Drona and Trikal in a circle around the shared memory; Chitragupta outside it, scoring against the actual market result, and Krishna outside it, watching every model."
      className="block h-auto w-full min-w-[820px]">

      <defs>
        <marker id="how-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto">
          <path className="fill-muted" d="M0 1 L9 5 L0 9 Z" />
        </marker>
        <marker id="how-arrow-accent" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto">
          <path className="fill-accent" d="M0 1 L9 5 L0 9 Z" />
        </marker>
      </defs>

      <ellipse cx={500} cy={320} rx={300} ry={225} className="fill-none stroke-line" strokeWidth={2} />
      <text x={356} y={118} textAnchor="end" fontSize={11.5} className="fill-muted">help circle</text>

      {SPOKES.map((s, i) =>
      <line key={i} x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} strokeWidth={1.5} strokeDasharray={s.kind === 'judge' ? '6 5' : undefined} className={STROKE[s.kind]} />
      )}

      <rect x={395} y={225} width={210} height={190} rx={12} strokeWidth={1.5} className="fill-canvas stroke-line" />
      <text x={500} y={252} textAnchor="middle" fontSize={15} fontWeight={600} className="fill-ink">Shared memory</text>
      <text x={500} y={270} textAnchor="middle" fontSize={11.5} className="fill-muted">E:\candlecast-data</text>
      <line x1={415} y1={283} x2={585} y2={283} strokeWidth={1} className="stroke-line" />
      {['news_notes', 'signals', 'help_requests', 'lessons', 'scores'].map((t, i) =>
      <text key={t} x={500} y={306 + i * 20} textAnchor="middle" fontSize={12.5} className={t === 'help_requests' ? 'fill-amber-400' : 'fill-ink'}>{t}</text>
      )}

      {SPOKES.map((s, i) =>
      <g key={i}>
          <rect x={s.cx - s.w / 2} y={s.cy - 11} width={s.w} height={22} rx={11} strokeWidth={1} className={`fill-surface ${s.kind === 'help' ? 'stroke-amber-400' : s.kind === 'accent' ? 'stroke-accent' : 'stroke-line'}`} />
          <text x={s.cx} y={s.cy + 4} textAnchor="middle" fontSize={12} className={TEXT[s.kind]}>{s.label}</text>
        </g>
      )}

      {NODES.map((n) =>
      <g key={n.name}>
          <rect
          x={n.x} y={n.y} width={168} height={60} rx={10} strokeWidth={1.5}
          strokeDasharray={n.kind === 'judge' ? '6 5' : undefined}
          className={`fill-raised ${n.kind === 'help' ? 'stroke-amber-400' : n.kind === 'accent' ? 'stroke-accent' : n.kind === 'judge' ? 'stroke-muted' : 'stroke-line'}`} />
          <text x={n.x + 84} y={n.y + 26} textAnchor="middle" fontSize={16} fontWeight={600} className="fill-ink">{n.name}</text>
          <text x={n.x + 84} y={n.y + 46} textAnchor="middle" fontSize={12} className="fill-muted">{n.role}</text>
        </g>
      )}
      <text x={66} y={476} fontSize={11.5} className="fill-muted">outside the circle</text>
      <text x={766} y={476} fontSize={11.5} className="fill-muted">watches every model</text>

      <text x={500} y={22} textAnchor="middle" fontSize={12.5} fontWeight={600} className="fill-ink">
        News <tspan fontWeight={400} className="fill-muted">· RSS, NSE filings, Google News</tspan>
      </text>
      <line x1={500} y1={31} x2={500} y2={62} strokeWidth={1.5} markerEnd="url(#how-arrow)" className="stroke-muted" />

      <line x1={898} y1={208} x2={848} y2={208} strokeWidth={1.5} markerEnd="url(#how-arrow)" className="stroke-muted" />
      <text x={906} y={204} fontSize={12.5} fontWeight={600} className="fill-ink">Candles</text>
      <text x={906} y={221} fontSize={12} className="fill-muted">Yahoo, NSE</text>

      <line x1={102} y1={208} x2={152} y2={208} strokeWidth={1.5} markerEnd="url(#how-arrow)" className="stroke-muted" />
      <text x={94} y={204} textAnchor="end" fontSize={12.5} fontWeight={600} className="fill-ink">World markets</text>
      <text x={94} y={221} textAnchor="end" fontSize={12} className="fill-muted">overnight</text>

      <line x1={150} y1={604} x2={150} y2={554} strokeWidth={1.5} markerEnd="url(#how-arrow)" className="stroke-muted" />
      <text x={150} y={626} textAnchor="middle" fontSize={12.5} fontWeight={600} className="fill-ink">Actual market result</text>

      <line x1={500} y1={577} x2={500} y2={604} strokeWidth={1.5} markerEnd="url(#how-arrow-accent)" className="stroke-accent" />
      <text x={500} y={626} textAnchor="middle" fontSize={12.5} fontWeight={600} className="fill-accent">Next session's call</text>
    </svg>);

}
