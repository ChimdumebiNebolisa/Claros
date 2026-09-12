import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { spawn, spawnSync } from "node:child_process";

const root = resolve(import.meta.dirname, "..");
const isWindows = process.platform === "win32";
const npmCommand = isWindows ? "npm.cmd" : "npm";

function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: root,
    env: process.env,
    stdio: "inherit",
    shell: isWindows && /\.(?:cmd|bat)$/iu.test(command),
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

function runNpm(args) {
  if (process.env.npm_execpath) {
    run(process.execPath, [process.env.npm_execpath, ...args]);
    return;
  }
  run(npmCommand, args);
}

function resolveQpdf() {
  if (process.env.CLAROS_OPENPDF_QPDF_PATH) {
    return process.env.CLAROS_OPENPDF_QPDF_PATH;
  }
  if (!isWindows) return "qpdf";
  const result = spawnSync(
    "powershell.exe",
    [
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      resolve(root, "scripts", "bootstrap-qpdf.ps1"),
    ],
    { cwd: root, env: process.env, encoding: "utf8" },
  );
  if (result.error) throw result.error;
  if (result.status !== 0) {
    process.stderr.write(result.stderr || "qpdf bootstrap failed.\n");
    process.exit(result.status ?? 1);
  }
  const qpdfPath = result.stdout.trim().split(/\r?\n/u).at(-1);
  if (!qpdfPath) throw new Error("qpdf bootstrap returned no executable path");
  return qpdfPath;
}

runNpm(["run", "build"]);
runNpm(["run", "build:openpdf"]);

const bundledPython = resolve(
  root,
  ".venv",
  isWindows ? "Scripts/python.exe" : "bin/python",
);
const pythonCommand = existsSync(bundledPython) ? bundledPython : "python";
const child = spawn(
  pythonCommand,
  [
    "-m",
    "uvicorn",
    "backend.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    "8080",
  ],
  {
    cwd: root,
    stdio: "inherit",
    env: {
      ...process.env,
      CLAROS_SEMANTIC_ENGINE: "openai",
      CLAROS_REALTIME_ENGINE: "openai",
      CLAROS_PDF_ENGINE: "openpdf",
      CLAROS_OPENPDF_QPDF_PATH: resolveQpdf(),
      CLAROS_PUBLIC_ORIGIN: "http://127.0.0.1:8080",
      CLAROS_LOCAL_STORAGE_PATH:
        process.env.CLAROS_LOCAL_STORAGE_PATH ?? ".local/claros-v2",
    },
  },
);

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal));
}

child.on("error", (error) => {
  console.error(error);
  process.exitCode = 1;
});
child.on("exit", (code, signal) => {
  process.exitCode = signal ? 1 : (code ?? 1);
});
