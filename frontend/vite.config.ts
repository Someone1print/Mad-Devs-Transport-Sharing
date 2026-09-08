import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Backend origin for the dev-server proxy; in Docker the same path is proxied by nginx.
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
})
