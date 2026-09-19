import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// The API and the attest engine share one server on :8090; proxying keeps the app same-origin.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 9100,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8090',
      '/v1': 'http://127.0.0.1:8090',
    },
  },
})
