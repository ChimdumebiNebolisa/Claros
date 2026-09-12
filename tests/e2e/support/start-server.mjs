import { existsSync, rmSync } from "node:fs";
import { delimiter, resolve, sep } from "node:path";
import { spawn, spawnSync } from "node:child_process";
import console from "node:console";
import process from "node:process";

const repositoryRoot = resolve(import.meta.dirname, "../../..");
const outputRoot = resolve(repositoryRoot, "output", "playwright");
const storagePath = resolve(outputRoot, "e2e-runtime-storage");
const distPath = resolve(outputRoot, "e2e-dist");
const serverPath = resolve(import.meta.dirname, "fastapi_server.py");
const port = "18080";
const isWindows = process.platform === "win32";

if (!storagePath.startsWith(`${outputRoot}${sep}`)) {
  throw new Error("Refusing to clean E2E storage outside output/playwright");
}
rmSync(storagePath, { recursive: true, force: true });

function cleanupStorage() {
  rmSync(storagePath, { recursive: true, force: true });
}

const bundledPython = resolve(
  repositoryRoot,
  ".venv",
  isWindows ? "Scripts/python.exe" : "bin/python",
);
const pythonCommand = existsSync(bundledPython) ? bundledPython : "python";

function resolveQpdf() {
  if (process.env.CLAROS_TEST_QPDF_PATH) {
    return process.env.CLAROS_TEST_QPDF_PATH;
  }
  if (isWindows) {
    const result = spawnSync(
      "powershell.exe",
      [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        resolve(repositoryRoot, "scripts", "bootstrap-qpdf.ps1"),
      ],
      { cwd: repositoryRoot, env: process.env, encoding: "utf8" },
    );
    if (result.status !== 0) {
      throw new Error(result.stderr || "qpdf bootstrap failed");
    }
    const path = result.stdout.trim().split(/\r?\n/u).at(-1);
    if (!path) throw new Error("qpdf bootstrap returned no executable path");
    return path;
  }
  const result = spawnSync("sh", ["-c", "command -v qpdf"], {
    cwd: repositoryRoot,
    env: process.env,
    encoding: "utf8",
  });
  const path = result.stdout.trim();
  if (result.status !== 0 || !path) {
    throw new Error("qpdf is required for application browser acceptance");
  }
  return path;
}

const child = spawn(pythonCommand, [serverPath], {
  cwd: repositoryRoot,
  env: {
    ...process.env,
    CLAROS_E2E_PORT: port,
    CLAROS_E2E_DIST_PATH: distPath,
    CLAROS_E2E_STORAGE_PATH: storagePath,
    CLAROS_E2E_QPDF_PATH: resolveQpdf(),
    PYTHONPATH: [repositoryRoot, process.env.PYTHONPATH]
      .filter(Boolean)
      .join(delimiter),
  },
  stdio: "inherit",
  windowsHide: true,
});

let stopping = false;
function stop(signal = "SIGTERM") {
  if (stopping) return;
  stopping = true;
  if (child.exitCode === null && child.signalCode === null) child.kill(signal);
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => stop(signal));
}

child.on("error", (error) => {
  console.error(error);
  process.exitCode = 1;
});
child.on("exit", (code, signal) => {
  cleanupStorage();
  if (!stopping && code !== 0) process.exitCode = code ?? 1;
  if (signal && !stopping) process.exitCode = 1;
});
