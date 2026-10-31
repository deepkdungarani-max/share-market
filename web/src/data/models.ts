import type { ModelInfo } from '../types/market';

// Shown only until /api/models answers (or if no model has been trained yet).
export const modelInfo: ModelInfo = { name: 'Your model', accuracy: 0, lookback: 'loading model info…' };
