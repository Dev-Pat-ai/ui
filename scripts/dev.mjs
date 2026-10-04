import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const isWindows = process.platform === "win32";
const environments = [
  process.env.VIRTUAL_ENV,
  resolve(projectRoot, ".venv"),
  resolve(projectRoot, "venv")
].filter(Boolean);
const python = environments
  .map((directory) => resolve(directory, isWindows ? "Scripts/python.exe" : "bin/python"))
  .find((executable) => existsSync(executable)) ?? (isWindows ? "python" : "python3");

const server = spawn(python, ["-u", "-X", "utf8", resolve(projectRoot, "backend", "app.py")], {
  cwd: projectRoot,
  stdio: "inherit",
  windowsHide: true,
  env: {
    ...process.env,
    DENGUESENSE_PROTOTYPE_ONLY: process.env.DENGUESENSE_PROTOTYPE_ONLY ?? "1",
    DENGUESENSE_SERVE_BUILD: "0"
  }
});

server.on("error", (error) => {
  console.error(`Unable to start Flask: ${error.message}`);
  console.error("Activate your Python environment and run: python -m pip install -r requirements.txt");
  process.exitCode = 1;
});

server.on("exit", (code, signal) => {
  process.exitCode = code ?? (signal === "SIGINT" ? 130 : signal === "SIGTERM" ? 143 : 1);
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    if (!server.killed) server.kill(signal);
  });
}
