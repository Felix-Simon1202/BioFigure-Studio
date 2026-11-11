import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
const localApi = process.env.BFS_LOCAL_API_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', proxy: { '/api': localApi } },
  preview: { host: '127.0.0.1', proxy: { '/api': localApi } },
})
