import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Backend origin for the dev-server proxy; in Docker the same path is proxied by nginx.
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'

// File-system events do not cross Docker bind mounts from Windows/macOS hosts;
// docker-compose.dev.yml sets this flag so HMR works there via polling.
const watchPolling = process.env.VITE_WATCH_POLLING === 'true'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    watch: watchPolling ? { usePolling: true, interval: 500 } : undefined,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
})
