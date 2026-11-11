import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

// In dev, Vite serves the app and forwards API and email-file requests to the Bun server.
const api = "http://127.0.0.1:3001";

export default defineConfig({
  plugins: [svelte()],
  server: { port: 5173, proxy: { "/api": api, "/raw": api } },
  build: { outDir: "dist", emptyOutDir: true },
});
