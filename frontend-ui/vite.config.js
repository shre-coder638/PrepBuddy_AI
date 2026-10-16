
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/static/react/",

  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },

  build: {
    outDir: "../static/react",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "app.js",
        assetFileNames: (assetInfo) => {
          const extension = assetInfo.name?.split(".").pop();
          return extension === "css"
            ? "styles.css"
            : "assets/[name][extname]";
        },
        chunkFileNames: "assets/[name].js",
      },
    },
  },
});
