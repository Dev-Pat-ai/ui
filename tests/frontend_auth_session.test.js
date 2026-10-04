const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "frontend/index.html"), "utf8");
const authScript = Array.from(html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi))
  .map(match => match[1]).find(script => script.includes("function home_enterApp"));
assert.ok(authScript, "The homepage authentication script must be present.");
const appScript = fs.readFileSync(path.join(root, "frontend/js/app.js"), "utf8");
const USER_KEY = "denguesense_current_user";
const PROFILE_KEY = "denguesenseqc_profile_v1";
const backendUser = { id: 7, email: "member@example.com", role: "user", name: "Member" };

function storage(map, blocked = false) {
  function checkAccess() {
    if (blocked) throw new Error("Storage access denied");
  }
  return {
    getItem(key) { checkAccess(); return map.get(key) ?? null; },
    setItem(key, value) { checkAccess(); map.set(key, String(value)); },
    removeItem(key) { checkAccess(); map.delete(key); },
  };
}

function element() {
  const classes = new Set();
  const listeners = new Map();
  return {
    value: "", checked: false, hidden: false, disabled: false,
    textContent: "", style: {}, type: "password",
    classList: {
      add: name => classes.add(name), remove: name => classes.delete(name),
      contains: name => classes.has(name),
    },
    setAttribute() {}, focus() {},
    addEventListener(type, handler) {
      listeners.set(type, [...(listeners.get(type) || []), handler]);
    },
    dispatch(type) {
      for (const handler of listeners.get(type) || []) {
        handler.call(this, { target: this, preventDefault() {} });
      }
    },
  };
}

function createPage({
  localMap = new Map(), sessionMap = new Map(), localBlocked = false,
  sessionBlocked = false, fetchImpl = async () => { throw new Error("Offline"); },
  confirmed = true,
} = {}) {
  const elements = Object.fromEntries(Array.from(html.matchAll(/\bid="([^"]+)"/g))
    .map(match => [match[1], element()]));
  elements["home-login-remember"].checked = true;
  const timers = new Map();
  let timerId = 0;
  const context = {
    console, AbortController, localStorage: storage(localMap, localBlocked),
    sessionStorage: storage(sessionMap, sessionBlocked), fetch: fetchImpl,
    location: { protocol: "http:", origin: "http://127.0.0.1:5000" },
    confirm: () => confirmed,
    setTimeout(callback) { timers.set(++timerId, callback); return timerId; },
    clearTimeout(id) { timers.delete(id); },
    document: {
      body: { style: { overflow: "hidden" } }, documentElement: { style: {} },
      getElementById: id => elements[id] || null,
      addEventListener() {}, querySelectorAll: () => [],
    },
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(authScript, context, { filename: "index.html:auth" });
  vm.runInContext(appScript, context, { filename: "app.js" });
  // Navigation and editor rendering are separate from the logout session contract.
  context.showPage = () => {};
  context.exitProfileEditMode = () => {};
  return { context, elements, timers, localMap, sessionMap };
}

async function submitLogin(page, { remember = true } = {}) {
  page.elements["home-login-email"].value = backendUser.email;
  page.elements["home-login-password"].value = "test-password";
  page.elements["home-login-remember"].checked = remember;
  page.elements["home-login-form"].dispatch("submit");
  // Flush the real promise chain before running UI handoff timers. Request timeout
  // timers should have been cancelled by home_authenticate's finally callback.
  await new Promise(setImmediate);
  for (const [id, callback] of [...page.timers]) {
    page.timers.delete(id);
    callback();
  }
  await new Promise(setImmediate);
}

function assertEntered(page) {
  assert.equal(page.elements["home-landing"].style.display, "none");
  assert.equal(page.context.document.body.style.overflow, "");
  assert.equal(page.context.document.documentElement.style.overflow, "");
}

function assertLanding(page) {
  assert.notEqual(page.elements["home-landing"].style.display, "none");
}

for (const user of [backendUser, { email: "demo@example.com", role: "user" }]) {
  test(`saved ${user.id ? "backend" : "demo/signup"} identity enters the app on reload`, () => {
    const localMap = new Map([[USER_KEY, JSON.stringify(user)]]);
    const page = createPage({ localMap });
    assertEntered(page);
    assert.equal(page.context.getCurrentUser().email, user.email);
    assertEntered(createPage({ localMap }));
  });
}

test("profile data alone never restores a signed-in view", () => {
  const page = createPage({ localMap: new Map([[PROFILE_KEY, JSON.stringify(backendUser)]]) });
  assertLanding(page);
  assert.equal(page.context.getCurrentUser(), null);
});

test("malformed and invalid saved identities stay on the landing page", () => {
  for (const raw of ["{", "null", "7", '"member@example.com"', "[]",
    JSON.stringify([backendUser]), "{}", '{"email":12}', '{"email":"invalid"}']) {
    const page = createPage({ localMap: new Map([[USER_KEY, raw]]) });
    assertLanding(page);
    assert.equal(page.context.getCurrentUser(), null, raw);
  }
});

test("session identity takes precedence and an invalid session falls back to local storage", () => {
  const localMap = new Map([[USER_KEY, JSON.stringify(backendUser)]]);
  const sessionMap = new Map([[USER_KEY, JSON.stringify({ email: "tab@example.com", role: "user" })]]);
  const page = createPage({ localMap, sessionMap });
  assertEntered(page);
  assert.equal(page.context.getCurrentUser().email, "tab@example.com");
  sessionMap.set(USER_KEY, "{");
  assert.equal(page.context.getCurrentUser().email, backendUser.email);
});

for (const remember of [true, false]) {
  test(`successful login persists across reload with Remember Me ${remember ? "checked" : "unchecked"}`, async () => {
    const calls = [];
    const localMap = new Map([[USER_KEY, JSON.stringify({ email: "previous@example.com" })]]);
    const sessionMap = new Map([[USER_KEY, JSON.stringify({ email: "old-tab@example.com" })]]);
    const page = createPage({ localMap, sessionMap, fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return { ok: true, status: 200, json: async () => ({ user: backendUser }) };
    } });
    page.context.home_showLanding();
    await submitLogin(page, { remember });
    assertEntered(page);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "/api/login");
    assert.equal(calls[0].options.method, "POST");
    const saved = remember ? localMap : sessionMap;
    const other = remember ? sessionMap : localMap;
    assert.deepEqual(JSON.parse(saved.get(USER_KEY)), backendUser);
    assert.equal(other.has(USER_KEY), false, "A previous identity must not survive in the other store.");
    assert.equal(saved.get(USER_KEY).includes("test-password"), false);
    assert.equal(page.elements["home-login-submit-btn"].disabled, false);
    const reload = createPage({ localMap, sessionMap });
    assertEntered(reload);
    assert.equal(reload.context.getCurrentUser().email, backendUser.email);
    const closedTab = createPage({ localMap, sessionMap: new Map() });
    if (remember) assertEntered(closedTab);
    else assertLanding(closedTab);
  });
}

for (const status of [401, 403]) {
  test(`HTTP ${status} keeps invalid credentials out of saved state`, async () => {
    const page = createPage({ fetchImpl: async () => ({ ok: false, status }) });
    await submitLogin(page);
    assertLanding(page);
    assert.equal(page.localMap.has(USER_KEY), false);
    assert.equal(page.sessionMap.has(USER_KEY), false);
    assert.match(page.elements["home-login-banner"].textContent, /Invalid email or password/);
    assert.equal(page.elements["home-login-submit-btn"].disabled, false);
    assertLanding(createPage({ localMap: page.localMap, sessionMap: page.sessionMap }));
  });
}

for (const failure of ["network", "unavailable route"]) {
  test(`existing demo handoff persists after ${failure} failure`, async () => {
    const page = createPage({ fetchImpl: async () => {
      if (failure === "network") throw new Error("Network unavailable");
      return { ok: false, status: 404 };
    } });
    await submitLogin(page, { remember: false });
    assertEntered(page);
    const saved = JSON.parse(page.sessionMap.get(USER_KEY));
    assert.equal(saved.email, backendUser.email);
    assert.equal(saved.role, "user");
    assert.equal(page.localMap.has(USER_KEY), false);
    assertEntered(createPage({ localMap: page.localMap, sessionMap: page.sessionMap }));
  });
}

test("confirmed logout clears both identities and the profile cache before refresh", () => {
  const localMap = new Map([[USER_KEY, JSON.stringify(backendUser)], [PROFILE_KEY, "{}"]]);
  const sessionMap = new Map([[USER_KEY, JSON.stringify(backendUser)]]);
  const page = createPage({ localMap, sessionMap });
  page.context.logoutProfile();
  assert.equal(localMap.has(USER_KEY), false);
  assert.equal(sessionMap.has(USER_KEY), false);
  assert.equal(localMap.has(PROFILE_KEY), false);
  assert.equal(page.context.getCurrentUser(), null);
  assertLanding(page);
  assertLanding(createPage({ localMap, sessionMap }));
});

test("cancelling logout preserves the signed-in view and refresh continuity", () => {
  const localMap = new Map([[USER_KEY, JSON.stringify(backendUser)], [PROFILE_KEY, "{}"]]);
  const page = createPage({ localMap, confirmed: false });
  page.context.logoutProfile();
  assertEntered(page);
  assert.equal(localMap.has(USER_KEY), true);
  assert.equal(localMap.has(PROFILE_KEY), true);
  assertEntered(createPage({ localMap }));
});

test("blocked storage does not crash startup, login, or logout", async () => {
  const page = createPage({ localBlocked: true, sessionBlocked: true,
    fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({ user: backendUser }) }) });
  assertLanding(page);
  assert.equal(page.context.getCurrentUser(), null);
  await submitLogin(page);
  assertEntered(page);
  assert.doesNotThrow(() => page.context.logoutProfile());
  assertLanding(page);
});

test("blocked session storage still permits local restore and local cleanup", () => {
  const localMap = new Map([[USER_KEY, JSON.stringify(backendUser)]]);
  const page = createPage({ localMap, sessionBlocked: true });
  assertEntered(page);
  assert.equal(page.context.getCurrentUser().email, backendUser.email);
  page.context.logoutProfile();
  assert.equal(localMap.has(USER_KEY), false);
});

test("blocked local storage still permits session restore and session cleanup", () => {
  const sessionMap = new Map([[USER_KEY, JSON.stringify(backendUser)]]);
  const page = createPage({ sessionMap, localBlocked: true });
  assertEntered(page);
  assert.equal(page.context.getCurrentUser().email, backendUser.email);
  page.context.logoutProfile();
  assert.equal(sessionMap.has(USER_KEY), false);
});
