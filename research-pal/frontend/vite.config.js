import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  // npm test: unit tests of the components. The end-to-end tests are in e2e/ and run with npm run e2e.
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.js"], include: ["src/**/*.test.{js,jsx}"], css: false },
});
