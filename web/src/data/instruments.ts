import type { Instrument, Market } from '../types/market';

export const stocks: Instrument[] = [
{ symbol: 'NIFTY 50', name: 'Nifty 50 Index', price: 24830.4, changePct: 0.42, volatility: 0.0018, decimals: 2 },
{ symbol: 'RELIANCE', name: 'Reliance Industries', price: 2945.6, changePct: 1.12, volatility: 0.003, decimals: 2 },
{ symbol: 'TCS', name: 'Tata Consultancy Services', price: 4120.25, changePct: -0.38, volatility: 0.0026, decimals: 2 },
{ symbol: 'HDFCBANK', name: 'HDFC Bank', price: 1687.9, changePct: 0.65, volatility: 0.0028, decimals: 2 },
{ symbol: 'INFY', name: 'Infosys', price: 1872.35, changePct: -0.91, volatility: 0.003, decimals: 2 },
{ symbol: 'ICICIBANK', name: 'ICICI Bank', price: 1254.1, changePct: 0.84, volatility: 0.0029, decimals: 2 },
{ symbol: 'SBIN', name: 'State Bank of India', price: 812.45, changePct: 1.48, volatility: 0.0034, decimals: 2 },
{ symbol: 'AXISBANK', name: 'Axis Bank', price: 1148.3, changePct: 0.37, volatility: 0.0031, decimals: 2 },
{ symbol: 'KOTAKBANK', name: 'Kotak Mahindra Bank', price: 1789.6, changePct: -0.24, volatility: 0.0027, decimals: 2 },
{ symbol: 'LT', name: 'Larsen & Toubro', price: 3612.8, changePct: 0.92, volatility: 0.0029, decimals: 2 },
{ symbol: 'ITC', name: 'ITC Ltd', price: 478.15, changePct: 0.18, volatility: 0.0022, decimals: 2 },
{ symbol: 'BHARTIARTL', name: 'Bharti Airtel', price: 1702.4, changePct: 1.05, volatility: 0.0028, decimals: 2 },
{ symbol: 'MARUTI', name: 'Maruti Suzuki', price: 12480.0, changePct: -0.66, volatility: 0.0026, decimals: 2 },
{ symbol: 'SUNPHARMA', name: 'Sun Pharma', price: 1836.2, changePct: 0.51, volatility: 0.0025, decimals: 2 },
{ symbol: 'BAJFINANCE', name: 'Bajaj Finance', price: 6942.5, changePct: -1.14, volatility: 0.0036, decimals: 2 }];


/** Rupee pairs: the forex an Indian resident may trade (NSE/BSE currency derivatives). Prices are replaced by
 *  the live ones from the backend. */
export const forexPairs: Instrument[] = [
{ symbol: 'USDINR', name: 'US Dollar / Indian Rupee', price: 95.21, changePct: 0, volatility: 0.0004, decimals: 4 },
{ symbol: 'EURINR', name: 'Euro / Indian Rupee', price: 106.31, changePct: 0, volatility: 0.0005, decimals: 4 },
{ symbol: 'GBPINR', name: 'British Pound / Indian Rupee', price: 127.2, changePct: 0, volatility: 0.0005, decimals: 4 },
{ symbol: 'JPYINR', name: 'Japanese Yen / Indian Rupee', price: 0.6027, changePct: 0, volatility: 0.0006, decimals: 4 }];


export const instrumentsByMarket: Record<Market, Instrument[]> = {
  stocks,
  forex: forexPairs
};

export const maxMinutesByMarket: Record<Market, number> = {
  stocks: 375,
  forex: 1440
};