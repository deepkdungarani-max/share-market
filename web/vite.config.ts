import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // `npm run dev` talks to the Python backend started by start.bat
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
