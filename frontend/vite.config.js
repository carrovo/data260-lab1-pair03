import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 9031,
    proxy: {
      "/api": {
        target: "http://localhost:9030",
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 9031,
    proxy: {
      "/api": {
        target: "http://localhost:9030",
        changeOrigin: true,
      },
    },
  },
});
