const assert = require("node:assert/strict");
const { execFile } = require("node:child_process");
const path = require("node:path");
const { promisify } = require("node:util");
const test = require("node:test");

test("responsive pages and forecast controls work in a real browser at seven viewport widths", {
  skip: process.env.FRONTEND_TEST_URL ? false : "Set FRONTEND_TEST_URL to a running development server to enable browser checks.",
  timeout: 420000,
}, async t => {
  const root = path.resolve(__dirname, "..");
  let result;
  try {
    result = await promisify(execFile)(process.execPath, [path.join(root, "scripts/check-frontend-layout.mjs")], {
      cwd: root, env: process.env, windowsHide: true, timeout: 400000, maxBuffer: 1024 * 1024,
    });
  } catch (error) {
    assert.fail(`${error.message}\n${error.stdout || ""}\n${error.stderr || ""}`);
  }
  t.diagnostic(result.stdout.trim());
});
