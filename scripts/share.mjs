import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { createConnection } from "node:net";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const sessionDirectory = resolve(projectRoot, "output", "public-share");
const sessionFile = resolve(sessionDirectory, "session.json");
const urlFile = resolve(sessionDirectory, "url.txt");
const isWindows = process.platform === "win32";
let localServer;
let tunnel;
let controlServer;
let state;
let closing = false;
let cleanup;
let stateWrites = Promise.resolve();

function saveSession() {
  stateWrites = stateWrites.then(async () => {
    if (closing) return;
    const temporary = `${sessionFile}.${state.token}.tmp`;
    await writeFile(temporary, JSON.stringify(state, null, 2), { mode: 0o600 });
    if (closing) await rm(temporary, { force: true });
    else await rename(temporary, sessionFile);
  });
  return stateWrites;
}

async function readSession() {
  let contents;
  try {
    contents = await readFile(sessionFile, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
  const saved = JSON.parse(contents);
  if (!Number.isInteger(saved.pid) || saved.pid < 1 || !Number.isInteger(saved.controlPort)
      || saved.controlPort < 1 || saved.controlPort > 65535
      || typeof saved.token !== "string" || !/^[a-f0-9]{64}$/.test(saved.token)) {
    throw new Error(`Cannot verify the sharing session recorded in ${sessionFile}.`);
  }
  return saved;
}

function isRunning(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    if (error.code === "ESRCH") return false;
    if (error.code === "EPERM") return true;
    throw error;
  }
}

async function clearSession(token) {
  const saved = await readSession();
  if (saved?.token !== token) return;
  await rm(sessionFile, { force: true });
  await rm(urlFile, { force: true });
}

async function requestControl(saved, path, method = "GET") {
  const response = await fetch(`http://127.0.0.1:${saved.controlPort}${path}`, {
    method,
    headers: { Authorization: `Bearer ${saved.token}` },
    signal: AbortSignal.timeout(5000)
  });
  if (!response.ok) throw new Error(`Sharing control returned HTTP ${response.status}.`);
  const result = await response.json();
  if (result.pid !== saved.pid || result.projectRoot !== projectRoot) {
    throw new Error("The recorded control address does not belong to this sharing session.");
  }
  return result;
}

async function stopSession() {
  const saved = await readSession();
  if (!saved) {
    console.log("No public sharing session is running.");
    return;
  }
  if (!isRunning(saved.pid)) {
    await clearSession(saved.token);
    console.log("Removed the record for a sharing session that has already stopped.");
    return;
  }
  try {
    await requestControl(saved, "/stop", "POST");
    console.log("Stopping the public tunnel and its demo server.");
  } catch (error) {
    throw new Error(`Could not reach the recorded sharing session: ${error.message} No processes were killed. Stop it from its original terminal with Ctrl+C.`);
  }
}

async function stopChild(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  await new Promise((done) => {
    let forceTimer;
    let finishTimer;
    const finish = () => {
      clearTimeout(forceTimer);
      clearTimeout(finishTimer);
      done();
    };
    child.once("close", finish);
    forceTimer = setTimeout(() => {
      try { child.kill("SIGKILL"); } catch {}
      finishTimer = setTimeout(finish, 2000);
    }, 5000);
    try { child.kill("SIGTERM"); } catch { finish(); }
  });
}

function shutdown(code = 0, message) {
  if (cleanup) return cleanup;
  closing = true;
  cleanup = (async () => {
    if (message) console.error(message);
    await Promise.all([stopChild(tunnel), stopChild(localServer)]);
    if (controlServer?.listening) {
      await new Promise((done) => {
        controlServer.close(done);
        controlServer.closeIdleConnections();
      });
    }
    await stateWrites.catch(() => {});
    if (state) await clearSession(state.token);
    process.exitCode = code;
  })();
  return cleanup;
}

function watchChild(child, label) {
  child.once("error", (error) => {
    void shutdown(1, `Unable to start ${label}: ${error.message}`).catch(console.error);
  });
  child.once("exit", (code, signal) => {
    if (!closing) {
      void shutdown(1, `${label} exited (${signal ?? code}). Public sharing has stopped.`).catch(console.error);
    }
  });
}

async function waitForHealth(origin) {
  const deadline = Date.now() + 60000;
  while (!closing && Date.now() < deadline) {
    try {
      const response = await fetch(`${origin}/health`, { signal: AbortSignal.timeout(2000) });
      const health = await response.json();
      if (response.ok && health.status === "ok" && ["demo", "public-demo", "public_demo"].includes(health.mode)) {
        return;
      }
    } catch {}
    await new Promise((done) => setTimeout(done, 500));
  }
  throw new Error(closing ? "Sharing startup was stopped." : "The public demo server did not become ready within 60 seconds.");
}

function waitForTunnelUrl(child) {
  return new Promise((done, reject) => {
    let recentOutput = "";
    const timeout = setTimeout(() => finish(new Error("Cloudflare did not provide a public URL within 90 seconds.")), 90000);
    const onError = (error) => finish(error);
    const onExit = () => finish(new Error("Cloudflare exited before creating a public URL."));
    const onOutput = (chunk) => {
      recentOutput = (recentOutput + chunk.toString()).slice(-8192);
      const match = recentOutput.match(/https:\/\/(?!api\.)[a-z0-9-]+\.trycloudflare\.com\b/i);
      if (match) finish(null, match[0]);
    };
    function finish(error, url) {
      clearTimeout(timeout);
      child.removeListener("error", onError);
      child.removeListener("exit", onExit);
      child.stdout.removeListener("data", onOutput);
      child.stderr.removeListener("data", onOutput);
      if (error) reject(error);
      else done(url);
    }
    child.once("error", onError);
    child.once("exit", onExit);
    child.stdout.on("data", onOutput);
    child.stderr.on("data", onOutput);
  });
}

async function startSession() {
  await mkdir(sessionDirectory, { recursive: true });
  const previous = await readSession();
  if (previous && isRunning(previous.pid)) {
    let existing;
    try { existing = await requestControl(previous, "/status"); }
    catch {
      throw new Error("The recorded sharing process is still running, but its control server is unavailable. Stop that session from its original terminal before starting another.");
    }
    console.log(existing.url ? `Public sharing is already running: ${existing.url}` : "Public sharing is already starting.");
    return;
  }
  if (previous) await clearSession(previous.token);

  const port = Number(process.env.PORT ?? 5001);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("PORT must be an integer between 1 and 65535.");
  const origin = `http://127.0.0.1:${port}`;
  const occupied = await new Promise((done) => {
    const socket = createConnection({ host: "127.0.0.1", port });
    const finish = (value) => { socket.destroy(); done(value); };
    socket.once("connect", () => finish(true));
    socket.once("error", () => finish(false));
    socket.setTimeout(1000, () => finish(true));
  });
  if (occupied) throw new Error(`Port ${port} is already in use. Stop that server or set a different PORT before sharing.`);

  const token = randomBytes(32).toString("hex");
  controlServer = createServer((request, response) => {
    response.setHeader("Content-Type", "application/json");
    response.setHeader("Cache-Control", "no-store");
    if (request.headers.authorization !== `Bearer ${token}`) {
      response.writeHead(401).end(JSON.stringify({ error: "Unauthorized" }));
      return;
    }
    if ((request.url === "/status" && request.method === "GET")
        || (request.url === "/stop" && request.method === "POST")) {
      response.end(JSON.stringify({ status: closing ? "stopping" : "running", pid: process.pid, projectRoot, url: state?.url ?? null }));
      if (request.url === "/stop") setImmediate(() => { void shutdown().catch(console.error); });
    } else response.writeHead(404).end(JSON.stringify({ error: "Not found" }));
  });
  await new Promise((done, reject) => {
    controlServer.once("error", reject);
    controlServer.listen(0, "127.0.0.1", done);
  });
  state = { pid: process.pid, controlPort: controlServer.address().port, token, projectRoot, startedAt: new Date().toISOString(), url: null };
  try {
    await writeFile(sessionFile, JSON.stringify(state, null, 2), { flag: "wx", mode: 0o600 });
  } catch (error) {
    state = undefined;
    throw error;
  }
  for (const signal of ["SIGINT", "SIGTERM"]) {
    process.once(signal, () => { void shutdown().catch(console.error); });
  }

  const environments = [process.env.VIRTUAL_ENV, resolve(projectRoot, ".venv"), resolve(projectRoot, "venv")].filter(Boolean);
  const python = environments.map((directory) => resolve(directory, isWindows ? "Scripts/python.exe" : "bin/python"))
    .find((executable) => existsSync(executable)) ?? (isWindows ? "python" : "python3");
  localServer = spawn(python, ["-u", "-X", "utf8", resolve(projectRoot, "backend", "public_demo.py")], {
    cwd: projectRoot,
    stdio: ["ignore", "inherit", "inherit"],
    windowsHide: true,
    env: { ...process.env, PORT: String(port), DENGUESENSE_PROTOTYPE_ONLY: "1", SKIP_TRAINING: "1", DATABASE_URL: "sqlite:///:memory:" }
  });
  state.serverPid = localServer.pid;
  watchChild(localServer, "Public demo server");
  await saveSession();
  console.log(`Starting the public demo at ${origin}...`);
  await waitForHealth(origin);
  if (closing) return;

  const bundledCloudflared = resolve(projectRoot, isWindows ? "cloudflared.exe" : "cloudflared");
  const cloudflared = existsSync(bundledCloudflared) ? bundledCloudflared : "cloudflared";
  tunnel = spawn(cloudflared, ["tunnel", "--url", origin, "--no-autoupdate", "--protocol", "http2"], {
    cwd: projectRoot, windowsHide: true, stdio: ["ignore", "pipe", "pipe"]
  });
  state.tunnelPid = tunnel.pid;
  watchChild(tunnel, "Cloudflare tunnel");
  const urlReady = waitForTunnelUrl(tunnel);
  tunnel.stdout.pipe(process.stdout, { end: false });
  tunnel.stderr.pipe(process.stderr, { end: false });
  const [url] = await Promise.all([urlReady, saveSession()]);
  state.url = url;
  if (closing) return;
  await writeFile(urlFile, `${state.url}\n`);
  await saveSession();
  console.log(`\nShare this public URL: ${state.url}`);
  console.log(`Saved to ${urlFile}`);
  console.log("Keep this process and computer running. Stop with Ctrl+C or npm run share:stop.");
}

try {
  if (process.argv.includes("--stop")) await stopSession();
  else await startSession();
} catch (error) {
  await shutdown(1, error.message);
}
