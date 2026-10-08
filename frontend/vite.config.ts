import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Requests to /api/... are forwarded to the FastAPI backend, so the browser
// talks to one address and we avoid CORS problems during development.
const apiTarget = process.env.VITE_API_PROXY ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
