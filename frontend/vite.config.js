import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Backend runs under a different host in Docker (service name) than in
      // local dev (localhost), so make the target configurable.
      '/chat': process.env.BACKEND_URL || 'http://localhost:8000'
    }
  }
})
