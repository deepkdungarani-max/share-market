import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster } from 'sonner';
import { MarketProvider } from './contexts/MarketContext';
import { PreferencesProvider } from './contexts/PreferencesContext';
import { AppLayout } from './components/AppLayout';
import { ApiKeys } from './pages/ApiKeys';
import { Backtest } from './pages/Backtest';
import { Data } from './pages/Data';
import { HowItWorks } from './pages/HowItWorks';
import { Krishna } from './pages/Krishna';
import { News } from './pages/News';
import { Overview } from './pages/Overview';
import { Predict } from './pages/Predict';
import { Scores } from './pages/Scores';
import { Teacher } from './pages/Teacher';
import { Trikal } from './pages/Trikal';
import { World } from './pages/World';

export function App() {
  return (
    <BrowserRouter>
      <PreferencesProvider>
        <MarketProvider>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Overview />} />
              <Route path="/trikal" element={<Trikal />} />
              <Route path="/news" element={<News />} />
              <Route path="/chart" element={<Predict />} />
              <Route path="/world" element={<World />} />
              <Route path="/scores" element={<Scores />} />
              <Route path="/backtest" element={<Backtest />} />
              <Route path="/teacher" element={<Teacher />} />
              <Route path="/keys" element={<ApiKeys />} />
              <Route path="/krishna" element={<Krishna />} />
              <Route path="/data" element={<Data />} />
              <Route path="/how" element={<HowItWorks />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
          <Toaster theme="dark" position="bottom-right" toastOptions={{ style: { fontFamily: 'Inter, system-ui, sans-serif' } }} />
        </MarketProvider>
      </PreferencesProvider>
    </BrowserRouter>);

}
