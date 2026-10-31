import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';

export function AppLayout() {
  return (
    <div className="flex min-h-full w-full flex-col bg-canvas font-sans text-ink lg:flex-row">
      <Sidebar />
      <main className="mx-auto flex w-full min-w-0 max-w-[1280px] flex-1 flex-col px-4 py-6 lg:px-8 lg:py-8">
        <Outlet />
        <footer className="mt-10 border-t border-line pt-5 text-[13px] leading-relaxed text-muted">
          Predictions are probability estimates, not guarantees. Not investment advice. Always use a stop loss.
        </footer>
      </main>
    </div>);

}
