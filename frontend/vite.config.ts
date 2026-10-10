import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In dev, /api is proxied to the FastAPI backend running on the host.
// Inside a container, set VITE_API_PROXY=http://host.docker.internal:8000.
const apiTarget = process.env.VITE_API_PROXY ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // File events don't cross Windows/macOS bind mounts into a container.
    watch: process.env.VITE_USE_POLLING ? { usePolling: true, interval: 300 } : undefined,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: false, xfwd: true },
    },
  },
  build: {
    chunkSizeWarningLimit: 4000,
    rollupOptions: {
      output: {
        manualChunks: { monaco: ['monaco-editor/esm/vs/editor/editor.api'] },
      },
    },
  },
});
