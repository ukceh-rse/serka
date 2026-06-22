import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      // Override with VITE_PROXY_TARGET (e.g. http://serka:8000) when running in a container.
      '/v1': process.env.VITE_PROXY_TARGET ?? 'http://localhost:9000',
    },
  },
})
