import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// Vite only exposes .env files to the client bundle, not to this config file,
// so the dev-proxy target has to be read explicitly.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiTarget = env.VITE_DEV_API_TARGET ?? 'http://127.0.0.1:8010';

  return {
    plugins: [react()],
    resolve: {
      alias: { '@': path.resolve(__dirname, './src') },
    },
    server: {
      host: true,
      port: 5173,
      strictPort: true,
      // Proxy the API so the dev server is same-origin with it, exactly as nginx
      // makes it in production. Without this the refresh cookie (HttpOnly +
      // SameSite=Lax) would be treated as cross-site and never sent, and sessions
      // would not survive a page reload in development.
        proxy: {
          '/api': { target: apiTarget, changeOrigin: false },
          '/media': { target: apiTarget, changeOrigin: false },
        },
    },
    preview: { port: 4173 },
    build: {
      outDir: 'dist',
      // Source maps are not shipped: they would expose the full frontend source
      // to anyone who opens devtools on the production site.
      sourcemap: false,
      target: 'es2020',
      rollupOptions: {
        output: {
          // Keep the vendor bundle separate so app updates do not invalidate it.
          manualChunks: {
            react: ['react', 'react-dom', 'react-router-dom'],
            forms: ['react-hook-form', 'zod', '@hookform/resolvers/zod'],
          },
        },
      },
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: false,
    },
  };
});
