// Starts Electron without ELECTRON_RUN_AS_NODE. VS Code sets that variable in its terminals.
// With it, Electron runs as plain Node, `app` is undefined and main.js crashes.
const { spawn } = require("child_process");

const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE;
spawn(require("electron"), ["."], { stdio: "inherit", env, cwd: __dirname }).on("exit", (code) => process.exit(code ?? 0));
