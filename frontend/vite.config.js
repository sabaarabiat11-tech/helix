import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],

  resolve: {
    // React three fiber pulls in its own dependency subtree that can end up
    // resolving a second, undeduped copy of react/react-dom under Vite's
    // dep pre-bundling — the textbook cause of "Invalid hook call" with R3F.
    // Forcing dedupe on these keeps exactly one instance of each.
    dedupe: ['react', 'react-dom', 'three', '@react-three/fiber'],
  },

  optimizeDeps: {
    include: ['react', 'react-dom', 'three', '@react-three/fiber', '@react-three/drei'],
  },

  build: {
    // Source maps ship to Vercel but aren't referenced by the bundle, so
    // production stack traces stay readable without exposing source to users.
    sourcemap: 'hidden',
    // Chunking is left to the bundler on purpose.
    //
    // An earlier version forced `three`, `recharts` and `lottie` into named
    // groups. That actively hurt: a forced group becomes a single chunk, and
    // as soon as any module in it is reachable from the entry the whole chunk
    // is preloaded — which put 871KB of three.js on the login page even
    // though the 3D scene is behind React.lazy. Letting rolldown derive
    // chunks from the real dynamic-import boundaries keeps heavy dependencies
    // in the async chunks that actually use them.
    chunkSizeWarningLimit: 700,
  },

  server: {
    port: 5173,
    proxy: {
      // Development only. In production the frontend is served by Vercel and
      // talks to the API cross-origin via VITE_API_URL, so no proxy exists —
      // which is why every request must go through src/api/client.js rather
      // than hardcoding a relative "/api" path anywhere else.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
