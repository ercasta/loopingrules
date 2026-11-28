import { defineConfig } from "vite";

// The viewer talks to `lr serve` (port 8765) through the dev server's proxy,
// so the page and the API share an origin.
export default defineConfig({
  server: {
    port: 5180,
    proxy: {
      "/api": { target: "http://127.0.0.1:8765", ws: true },
    },
  },
});
