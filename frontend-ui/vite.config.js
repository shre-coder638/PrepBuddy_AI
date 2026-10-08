import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/static/react/",
  build: {
    outDir: "../static/react",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "app.js",
        assetFileNames: (assetInfo) => {
          const extension = assetInfo.name?.split(".").pop();
          return extension === "css" ? "styles.css" : "assets/[name][extname]";
        },
        chunkFileNames: "assets/[name].js",
      },
    },
  },
});
