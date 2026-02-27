import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    // Load .env from the repo root (one level above this frontend/ folder)
    const env = loadEnv(mode, path.resolve(__dirname, '..'), '');
    const backendPort = env.BACKEND_PORT || '6802';
    return {
      server: {
        port: parseInt(env.FRONTEND_PORT) || 7802,
        host: '0.0.0.0',
        proxy: {
          '/api': {
            target: `http://127.0.0.1:${backendPort}`,
            changeOrigin: true,
          },
        },
      },
      plugins: [react()],
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        },
      },
    };
});
