#!/usr/bin/env node
// One-command bootstrap for EchoLearn, run automatically by `npm install` at the
// repo root (via the "postinstall" script in package.json) or manually via
// `npm run setup`. Sets up the frontend's node_modules, the backend's Python
// venv + pinned dependencies, and creates .env files from their examples if
// they don't exist yet. Does NOT start any servers, run migrations, install
// system tools (Postgres/FFmpeg/Tesseract), or download the voice model — those
// steps need real values (API keys, a running database) or manual downloads,
// so they're left for the README/DEPLOYMENT docs to walk through afterward.

import { spawnSync } from "node:child_process";
import { existsSync, copyFileSync } from "node:fs";
import { platform } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const backendDir = path.join(root, "backend");
const frontendDir = path.join(root, "frontend");
const isWindows = platform() === "win32";

function log(msg) {
  console.log(`\n[setup] ${msg}`);
}

function run(command, args, cwd) {
  log(`${command} ${args.join(" ")}  (in ${path.relative(root, cwd) || "."})`);
  const result = spawnSync(command, args, { cwd, stdio: "inherit", shell: isWindows });
  if (result.status !== 0) {
    throw new Error(`Command failed: ${command} ${args.join(" ")}`);
  }
}

function findPython() {
  const candidates = isWindows ? ["py", "python", "python3"] : ["python3", "python"];
  for (const candidate of candidates) {
    const check = spawnSync(candidate, ["--version"], { shell: isWindows });
    if (check.status === 0) return candidate;
  }
  throw new Error(
    "No Python interpreter found on PATH. Install Python 3.11+ from https://python.org, then re-run `npm run setup`."
  );
}

function ensureEnvFile(dir, exampleName, targetName) {
  const examplePath = path.join(dir, exampleName);
  const targetPath = path.join(dir, targetName);
  if (existsSync(targetPath)) {
    log(`${path.relative(root, targetPath)} already exists — leaving it as is.`);
    return;
  }
  if (!existsSync(examplePath)) {
    log(`WARNING: ${exampleName} not found in ${dir}, skipping.`);
    return;
  }
  copyFileSync(examplePath, targetPath);
  log(`Created ${path.relative(root, targetPath)} from ${exampleName} — fill in real values before running the app.`);
}

function venvPython() {
  return isWindows
    ? path.join(backendDir, "venv", "Scripts", "python.exe")
    : path.join(backendDir, "venv", "bin", "python");
}

async function main() {
  log("Setting up EchoLearn (frontend + backend)...");

  // 1. Frontend dependencies.
  run(isWindows ? "npm.cmd" : "npm", ["install"], frontendDir);
  ensureEnvFile(frontendDir, ".env.example", ".env.local");

  // 2. Backend virtualenv + pinned Python dependencies.
  const python = findPython();
  const venvDir = path.join(backendDir, "venv");
  if (!existsSync(venvDir)) {
    run(python, ["-m", "venv", "venv"], backendDir);
  } else {
    log("backend/venv already exists — skipping venv creation.");
  }

  const pip = isWindows
    ? path.join(backendDir, "venv", "Scripts", "pip.exe")
    : path.join(backendDir, "venv", "bin", "pip");
  run(pip, ["install", "--upgrade", "pip"], backendDir);
  run(pip, ["install", "-r", "requirements.txt"], backendDir);
  ensureEnvFile(backendDir, ".env.example", ".env");

  log("Setup complete!");
  console.log(`
Next steps:
  1. Fill in real values in backend/.env — DATABASE_URL, JWT_SECRET, GROQ_API_KEY,
     GEMINI_API_KEY (see backend/.env.example for the full list).
  2. Make sure PostgreSQL is running and the database in DATABASE_URL exists.
  3. Run the database migrations:
       cd backend && ${isWindows ? "venv\\Scripts\\python -m alembic upgrade head" : "venv/bin/python -m alembic upgrade head"}
  4. (Optional) Download a Piper voice model for text-to-speech — see
     backend/app/voice/README.md.
  5. Start both servers:
       npm run dev:backend    (in one terminal)
       npm run dev:frontend   (in another terminal)

See README.md and DEPLOYMENT.md for full details, including FFmpeg/Tesseract
setup for document parsing.
`);
}

main().catch((err) => {
  console.error(`\n[setup] FAILED: ${err.message}`);
  process.exit(1);
});
