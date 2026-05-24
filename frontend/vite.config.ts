import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Phase 1I bootstrap: foundation toolchain only.
// Phase 2D Slice 1: base is '/' for root-level static serving in production.
// The backend API is served from the same origin via Caddy reverse proxy.
export default defineConfig({
  base: '/',
  plugins: [react(), tailwindcss()],
});
