import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Any request starting with /api will be forwarded to FastAPI
      // This means React can call /api/query instead of http://localhost:8000/api/query
      '/api': 'http://localhost:8000'
    }
  }
})


