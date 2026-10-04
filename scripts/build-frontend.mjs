import { access, cp, readdir, rm, stat } from "node:fs/promises";
import { constants } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(scriptDirectory, "..");
const sourceDirectory = resolve(projectRoot, "frontend");
const outputDirectory = resolve(projectRoot, "dist");
const cleanOnly = process.argv.includes("--clean");

function relativeToProject(path) {
  return relative(projectRoot, path).replaceAll("\\", "/");
}

async function requireFile(path) {
  try {
    await access(path, constants.R_OK);
  } catch {
    throw new Error(`Required frontend file is missing: ${relativeToProject(path)}`);
  }
}

async function countFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const counts = await Promise.all(entries.map(async (entry) => {
    const entryPath = resolve(directory, entry.name);
    if (entry.isDirectory()) return countFiles(entryPath);
    return entry.isFile() ? 1 : 0;
  }));
  return counts.reduce((total, count) => total + count, 0);
}

async function main() {
  const sourceStats = await stat(sourceDirectory).catch(() => null);
  if (!sourceStats?.isDirectory()) {
    throw new Error(`Frontend directory not found: ${relativeToProject(sourceDirectory)}`);
  }

  if (!relativeToProject(outputDirectory) || relativeToProject(outputDirectory).startsWith("..")) {
    throw new Error("Refusing to remove a build output directory outside this project.");
  }

  await rm(outputDirectory, { recursive: true, force: true });
  if (cleanOnly) {
    console.log(`Removed ${relativeToProject(outputDirectory)}`);
    return;
  }

  await cp(sourceDirectory, outputDirectory, { recursive: true, force: true });
  await Promise.all([
    requireFile(resolve(outputDirectory, "index.html")),
    requireFile(resolve(outputDirectory, "css", "style.css")),
    requireFile(resolve(outputDirectory, "js", "app.js"))
  ]);

  const syntaxCheck = spawnSync(process.execPath, ["--check", resolve(outputDirectory, "js", "app.js")], {
    stdio: "inherit"
  });
  if (syntaxCheck.status !== 0) {
    process.exit(syntaxCheck.status ?? 1);
  }

  const fileCount = await countFiles(outputDirectory);
  console.log(`Built ${fileCount} frontend files to ${relativeToProject(outputDirectory)}`);
}

main().catch((error) => {
  console.error(`Frontend build failed: ${error.message}`);
  process.exitCode = 1;
});
