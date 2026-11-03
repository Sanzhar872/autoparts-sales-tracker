import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Локально API проксируется на FastAPI, в проде то же делает vercel.json.
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": backend,
      "/health": backend,
    },
  },
});
