import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/wrapped/', // Base path for production deployment
  server: {
    port: 5173,
    host: true, // Allow external connections for debugging
  },
  build: {
    // Show detailed build errors
    minify: false,
    sourcemap: true,
  },
  // Better error overlay
  clearScreen: false,
});

