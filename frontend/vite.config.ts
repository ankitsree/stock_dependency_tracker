/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // Scoped to src/ — without this, Vitest's default glob also picks up
    // e2e/*.spec.ts (Playwright tests), which fail hard when run under
    // Vitest's runner instead of Playwright's.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
