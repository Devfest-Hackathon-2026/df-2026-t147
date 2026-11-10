import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 開発時は /api をバックエンド(8000)へ中継
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
