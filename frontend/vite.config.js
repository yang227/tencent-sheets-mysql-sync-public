import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const frontendPort = Number(process.env.FRONTEND_PORT || '5173')
const frontendHost = process.env.FRONTEND_HOST || '127.0.0.1'
const backendTarget = process.env.FRONTEND_BACKEND_URL || 'http://127.0.0.1:8083'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: frontendHost,
    port: frontendPort,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/health': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
})
