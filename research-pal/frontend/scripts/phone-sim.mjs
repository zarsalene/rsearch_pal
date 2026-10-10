// A phone simulator for your PC: it opens the app in a window that has the size, the touch and the density of a Redmi Note 13 Pro+.
// Run:  npm run phone            (the real server and the Supabase login from your .env)
//       npm run phone -- --dark  (dark mode)      npm run phone -- --url=http://localhost:5173
// It starts the dev server itself, if no server runs yet. Close the window to stop.
import { chromium } from "@playwright/test";
import { spawn } from "node:child_process";

const arg = (name) => process.argv.find((a) => a.startsWith(`--${name}=`))?.split("=")[1];
const URL = arg("url") || "http://localhost:5173";
const dark = process.argv.includes("--dark");

const up = () => fetch(URL).then((r) => r.ok).catch(() => false);
let server = null;
if (!(await up())) {
  console.log("Starting the dev server...");
  server = spawn("npm", ["run", "dev", "--", "--port", new globalThis.URL(URL).port || "5173", "--strictPort"], { shell: true, stdio: "ignore" });
  for (let i = 0; i < 60 && !(await up()); i++) await new Promise((r) => setTimeout(r, 1000));
}

const browser = await chromium.launch({ headless: false, args: ["--window-size=460,960"] });
const context = await browser.newContext({
  viewport: { width: 393, height: 786 },
  deviceScaleFactor: 2.75,
  isMobile: true,
  hasTouch: true,
  colorScheme: dark ? "dark" : "light",
  userAgent: "Mozilla/5.0 (Linux; Android 14; 23090RA98G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36",
});
const page = await context.newPage();
await page.goto(URL);
console.log(`Phone simulator open: ${URL}  (393 x 786 px, touch, ${dark ? "dark" : "light"} mode). Close the window to stop.`);
await new Promise((resolve) => browser.on("disconnected", resolve));
server?.kill();
process.exit(0);
