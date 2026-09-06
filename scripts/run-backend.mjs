#!/usr/bin/env node
// Convenience launcher: `npm run dev:backend` from the repo root starts the FastAPI
// backend using the venv created by scripts/setup.mjs, without needing to remember
// the venv's OS-specific python path or `cd` into backend/ first.

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { platform } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const backendDir = path.join(root, "backend");
const isWindows = platform() === "win32";

const python = isWindows
  ? path.join(backendDir, "venv", "Scripts", "python.exe")
  : path.join(backendDir, "venv", "bin", "python");

if (!existsSync(python)) {
  console.error(
    "backend/venv not found — run `npm install` (or `npm run setup`) from the repo root first."
  );
  process.exit(1);
}

const result = spawnSync(
  python,
  ["-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
  { cwd: backendDir, stdio: "inherit" }
);
process.exit(result.status ?? 1);
