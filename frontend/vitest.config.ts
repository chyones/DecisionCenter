import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Test-only config. Kept separate from vite.config.ts so the Tailwind build
// plugin is not loaded in the jsdom test environment.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
