import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
export default defineConfig({
  plugins: [
    react(),
    // The app can be installed from the browser, and it opens fast because the files are cached.
    // The calls to the server (/api) are never cached, so a paper is always fresh.
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.png", "apple-touch-icon.png"],
      manifest: {
        name: "Research Pal",
        short_name: "Research Pal",
        description: "Read less. Know where every claim comes from.",
        theme_color: "#0E1230",
        background_color: "#0B0B0E",
        display: "standalone",
        orientation: "portrait",
        start_url: "/",
        icons: [
          { src: "/logo.png", sizes: "512x512", type: "image/png", purpose: "any" },
          { src: "/logo.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: { navigateFallbackDenylist: [/^\/api/], globPatterns: ["**/*.{js,css,html,png,woff2}"] },
    }),
  ],
  // npm test: unit tests of the components. The end-to-end tests are in e2e/ and run with npm run e2e.
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.js"], include: ["src/**/*.test.{js,jsx}"], css: false },
});
