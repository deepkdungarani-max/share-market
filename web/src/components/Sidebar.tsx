import React, { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  CandlestickChartIcon,
  CompassIcon,
  DatabaseIcon,
  EyeIcon,
  FlaskConicalIcon,
  GlobeIcon,
  GraduationCapIcon,
  KeyRoundIcon,
  LayoutGridIcon,
  LineChartIcon,
  MenuIcon,
  NewspaperIcon,
  ScaleIcon,
  WorkflowIcon,
  XIcon,
  type LucideIcon } from
'lucide-react';
import { useMarket } from '../contexts/MarketContext';

const LINKS: {to: string;label: string;icon: LucideIcon;}[] = [
{ to: '/', label: 'Overview', icon: LayoutGridIcon },
{ to: '/trikal', label: 'Trikal', icon: EyeIcon },
{ to: '/news', label: 'News', icon: NewspaperIcon },
{ to: '/chart', label: 'Chart', icon: LineChartIcon },
{ to: '/world', label: 'World', icon: GlobeIcon },
{ to: '/scores', label: 'Scores', icon: ScaleIcon },
{ to: '/backtest', label: 'Backtest', icon: FlaskConicalIcon },
{ to: '/teacher', label: 'Teacher', icon: GraduationCapIcon },
{ to: '/krishna', label: 'Krishna', icon: CompassIcon },
{ to: '/data', label: 'Data', icon: DatabaseIcon },
{ to: '/keys', label: 'API keys', icon: KeyRoundIcon },
{ to: '/how', label: 'How it works', icon: WorkflowIcon }];


/** The app's navigation: a fixed column on the left on wide screens, a menu that slides in on small ones. */
export function Sidebar() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setOpen(false), [pathname]);

  return (
    <>
      <div className="sticky top-0 z-40 flex items-center justify-between border-b border-line bg-canvas/90 px-4 py-3 backdrop-blur lg:hidden">
        <Brand />
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open menu"
          className="rounded-md p-2 text-muted hover:bg-raised hover:text-ink">

          <MenuIcon className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>

      {open && <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={() => setOpen(false)} aria-hidden="true" />}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-60 flex-col border-r border-line bg-surface transition-transform lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:translate-x-0 ${
        open ? 'translate-x-0' : '-translate-x-full'}`
        }
        aria-label="Main">

        <div className="flex items-center justify-between px-4 py-4">
          <Brand />
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close menu"
            className="rounded-md p-1.5 text-muted hover:bg-raised hover:text-ink lg:hidden">

            <XIcon className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-3">
          {LINKS.map(({ to, label, icon: Icon }) =>
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-raised text-ink' : 'text-muted hover:bg-raised/60 hover:text-ink'}`
            }>

              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              {label}
            </NavLink>
          )}
        </nav>

        <MarketStatus />
      </aside>
    </>);

}

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15 text-accent" aria-hidden="true">
        <CandlestickChartIcon className="h-[18px] w-[18px]" />
      </span>
      <span className="text-base font-semibold tracking-tight text-ink">candlecast</span>
      <span className="rounded-md bg-raised px-2 py-0.5 text-xs font-medium text-muted">NSE</span>
    </div>);

}

function MarketStatus() {
  const { status } = useMarket();
  return (
    <div className="border-t border-line px-4 py-3">
      <p className={`flex items-center gap-2 text-[13px] font-medium ${status.open ? 'text-up' : 'text-muted'}`}>
        <span className={`h-2 w-2 rounded-full ${status.open ? 'animate-pulse bg-up' : 'bg-muted'}`} aria-hidden="true" />
        {status.open ? 'Market open' : 'Market closed'}
      </p>
      <p className="mt-0.5 text-xs text-muted">{status.detail}</p>
    </div>);

}
