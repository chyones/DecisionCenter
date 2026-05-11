import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Phase 1I bootstrap: foundation toolchain only. No dev proxy, no API base URL,
// no environment-driven backend wiring (see docs/design/PHASE_1I_UI_CONTRACT.md §G).
export default defineConfig({
  plugins: [react(), tailwindcss()],
});
