const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const vm = require("node:vm");

const forecastData = JSON.parse(fs.readFileSync("data/sample/forecast.json", "utf8"));
const bnResult = { map_label: "High", probabilities: { High: 0.8 }, evidence_count: 1, feature_count: 4, prediction_scope: "Quezon City experimental model" };
const lstmResult = { prediction_scope: "Bagong Silangan", predictions: [{ predicted_cases: 6 }, { predicted_cases: 7 }] };
const response = data => ({ ok: true, json: async () => data });
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

function element(value = "") {
  const classes = new Set();
  const listeners = new Map();
  return {
    value, textContent: "--", innerHTML: "", dataset: {}, disabled: false,
    classList: {
      contains: name => classes.has(name),
      add: name => classes.add(name),
      remove: name => classes.delete(name),
      toggle(name, force) {
        if (force ?? !classes.has(name)) classes.add(name);
        else classes.delete(name);
      },
    },
    addEventListener(type, handler) {
      listeners.set(type, [...(listeners.get(type) || []), handler]);
    },
    dispatch(type) {
      for (const handler of listeners.get(type) || []) handler({ target: this });
    },
  };
}

function kpi() {
  const children = Object.fromEntries([".kpi-label", ".kpi-note", ".kpi-trend"].map(selector => [selector, element()]));
  return { ...element(), children, parentElement: { querySelector: selector => children[selector] } };
}

function createContext() {
  const ids = ["I", "II", "III"];
  const cards = ids.map(id => ({
    ...element(), dataset: { districtId: id }, metric: element(), risk: element(),
    querySelector(selector) {
      return selector === ".district-card-metric" ? this.metric : selector === ".risk-pill" ? this.risk : null;
    },
  }));
  const selectors = { ".dashboard-district-card": cards };
  for (const selector of [".forecast-cell", ".summary-cases", ".summary-risk", ".district-indicator"]) {
    selectors[selector] = ids.map(id => ({ ...element(), dataset: { districtId: id } }));
  }
  const elements = Object.fromEntries([
    "short-term-forecast-container", "get-forecast-btn", "result-panel", "run-btn", "loading-bar",
    "lstm-result", "lstm-btn", "lstm-loading", "history-content", "hist-filter-district",
    "det-situation-banner", "det-cases", "det-pill", "sample-alerts-container",
    "ev-rain-now", "ev-city-now", "ev-rain-lag4", "ev-bgy-lag4",
  ].map(id => [id, element()]));
  for (const id of ["kpi-sample-cases", "kpi-total-forecast", "kpi-high-risk", "kpi-districts"]) elements[id] = kpi();
  elements["forecast-district"] = element("I");
  elements["lstm-area"] = { ...element("bagong silangan"), options: [{ textContent: "Bagong Silangan" }], selectedIndex: 0 };
  elements["lstm-weeks"] = element("4");
  const storage = new Map();
  const context = {
    console,
    document: {
      addEventListener() {},
      getElementById: id => elements[id] || null,
      querySelectorAll: selector => selectors[selector] || [],
    },
    window: { location: { protocol: "http:", origin: "http://localhost" } },
    localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) },
  };
  vm.createContext(context);
  for (const path of ["frontend/js/cpdd-data.js", "frontend/js/app.js"]) vm.runInContext(fs.readFileSync(path, "utf8"), context);
  const districts = ids.map((id, index) => ({
    district: `District ${id}`, sampleCases: [10, 24, 9][index], prevCases: 8, forecast: null, risk: "high",
  }));
  context.renderDashboard({ districts, alerts: [{ type: "health", title: "City-wide alert" }] }, false);
  context.bindForecastControls();
  const selectDistrict = id => {
    elements["forecast-district"].value = id;
    elements["forecast-district"].dispatch("change");
  };
  return { context, elements, cards, selectors, districts, selectDistrict };
}

test("one district forecast only reveals that district's returned cases and risk", () => {
  const { context, elements, cards, selectors } = createContext();
  context.revealDistrictForecast("II", { next_week_forecast: 30, risk_level: "low" });
  assert.equal(elements["kpi-sample-cases"].textContent, 24);
  assert.equal(elements["kpi-total-forecast"].textContent, 30);
  assert.equal(elements["kpi-total-forecast"].children[".kpi-note"].textContent, "District II");
  assert.equal(elements["kpi-high-risk"].textContent, "BELOW");
  assert.deepEqual(cards.map(card => card.metric.textContent), ["-- cases", "24 current · 30 forecast", "-- cases"]);
  assert.deepEqual(cards.map(card => card.risk.textContent), ["NOT FORECASTED", "BELOW", "NOT FORECASTED"]);
  assert.deepEqual(selectors[".forecast-cell"].map(cell => cell.textContent), ["--", 30, "--"]);
  assert.deepEqual(selectors[".summary-cases"].map(cell => cell.textContent), ["--", 24, "--"]);
  assert.equal(cards[1].classList.contains("forecast-selected"), true);
  assert.doesNotMatch(elements["sample-alerts-container"].innerHTML, /City-wide alert/);
});

test("a district change clears the result and KPIs but preserves the accepted history", async () => {
  const { context, elements, selectDistrict } = createContext();
  context.fetch = async () => response(forecastData);
  await context.loadShortTermForecast("I", []);
  assert.equal(elements["kpi-total-forecast"].textContent, 8);
  assert.match(elements["short-term-forecast-container"].innerHTML, /8 cases/);
  selectDistrict("II");
  for (const id of ["kpi-sample-cases", "kpi-total-forecast", "kpi-high-risk"]) assert.equal(elements[id].textContent, "--");
  assert.doesNotMatch(elements["short-term-forecast-container"].innerHTML, /8 cases/);
  assert.equal(context.getForecastHistory().length, 1);
});

test("late dashboard data preserves a valid zero-case forecast", () => {
  const { context, elements, districts } = createContext();
  context.revealDistrictForecast("I", { next_week_forecast: 0, risk_level: "low" });
  context.renderDashboard({ districts }, false);
  assert.equal(elements["kpi-total-forecast"].textContent, 0);
  assert.equal(elements["kpi-sample-cases"].textContent, 10);
});

test("switching districts and back discards a pending forecast", async () => {
  const { context, elements, selectDistrict } = createContext();
  const pending = deferred();
  context.fetch = () => pending.promise;
  const request = context.loadShortTermForecast("I", []);
  selectDistrict("II");
  selectDistrict("I");
  pending.resolve(response(forecastData));
  await request;
  assert.equal(elements["kpi-total-forecast"].textContent, "--");
  assert.equal(context.getForecastHistory().length, 0);
  assert.equal(elements["get-forecast-btn"].disabled, false);
});

test("a delayed first response cannot overwrite a newer district forecast", async () => {
  const { context, elements, selectDistrict } = createContext();
  const pending = deferred();
  context.fetch = () => pending.promise;
  const first = context.loadShortTermForecast("I", []);
  selectDistrict("II");
  context.fetch = async () => response(forecastData);
  await context.loadShortTermForecast("II", []);
  pending.resolve(response(forecastData));
  await first;
  assert.equal(elements["kpi-total-forecast"].textContent, 10);
  assert.equal(elements["kpi-total-forecast"].children[".kpi-note"].textContent, "District II");
  assert.equal(context.getForecastHistory().length, 1);
});

test("BN and LSTM results neither reveal nor replace district dashboard forecasts", () => {
  const { context, elements } = createContext();
  context.renderBNResult(bnResult);
  context.renderLSTMResult(lstmResult);
  assert.equal(elements["kpi-total-forecast"].textContent, "--");
  context.revealDistrictForecast("I", { next_week_forecast: 8, risk_level: "low" });
  context.renderBNResult(bnResult);
  context.renderLSTMResult(lstmResult);
  assert.equal(elements["kpi-total-forecast"].textContent, 8);
  assert.equal(elements["kpi-high-risk"].textContent, "BELOW");
});

test("district detail only reveals the district with an accepted forecast", () => {
  const { context, elements } = createContext();
  context.window.__lastDistrictDetail = { districtId: "II", cases: 24 };
  context.revealDistrictForecast("I", { next_week_forecast: 8, risk_level: "low" });
  assert.equal(elements["det-pill"].textContent, "--");
  context.window.__lastDistrictDetail = { districtId: "I", cases: 10 };
  context.renderDistrictDetailSituation();
  assert.equal(elements["det-pill"].textContent, "BELOW (Forecast)");
  context.clearSelectedDistrictForecast();
  assert.equal(elements["det-pill"].textContent, "--");
});

for (const control of ["forecast-district", "ev-rain-now"]) {
  test(`a pending inference is discarded after changing ${control}`, async () => {
    const { context, elements } = createContext();
    const pending = deferred();
    context.fetch = () => pending.promise;
    const request = context.runInference();
    elements[control].value = control === "forecast-district" ? "II" : "high";
    elements[control].dispatch("change");
    pending.resolve(response(bnResult));
    await request;
    assert.doesNotMatch(elements["result-panel"].innerHTML, /EPIDEMIC/);
    assert.equal(context.getForecastHistory().length, 0);
    assert.equal(elements["run-btn"].disabled, false);
  });
}

for (const control of ["lstm-area", "lstm-weeks"]) {
  test(`a pending LSTM result is discarded after changing ${control}`, async () => {
    const { context, elements } = createContext();
    const pending = deferred();
    context.fetch = () => pending.promise;
    const request = context.runLSTMForecast();
    elements[control].value = control === "lstm-area" ? "alicia" : "8";
    elements[control].dispatch("change");
    pending.resolve(response(lstmResult));
    await request;
    assert.doesNotMatch(elements["lstm-result"].innerHTML, /6\.0 cases/);
    assert.equal(context.getForecastHistory().length, 0);
    assert.equal(elements["lstm-btn"].disabled, false);
  });
}

test("LSTM history uses the returned barangay and its actual district", () => {
  const { context } = createContext();
  context.renderLSTMResult(lstmResult, { areaLabel: "Alicia" });
  const entry = context.getForecastHistory()[0];
  assert.equal(entry.districtName, "District II");
  assert.deepEqual(Array.from(entry.barangays), ["Bagong Silangan"]);
  assert.equal(entry.scope, "barangay");
  assert.match(context.formatBarangayCell(entry.barangays, entry), /Bagong Silangan/);
  assert.doesNotMatch(context.formatBarangayCell(entry.barangays, entry), /All barangays/);
});

test("legacy LSTM history filters by the corrected district without rewriting storage", () => {
  const { context, elements } = createContext();
  context.saveForecastHistory([{ method: "lstm", districtName: "Bagong Silangan", barangays: [], timestamp: "2026-09-23T12:00:00Z", summary: "W1: 6 cases" }]);
  elements["hist-filter-district"].value = "District II";
  context.renderHistoricalTable();
  assert.match(elements["history-content"].innerHTML, /Bagong Silangan/);
  assert.match(elements["history-content"].innerHTML, /District II/);
  assert.doesNotMatch(elements["history-content"].innerHTML, /All barangays|No logged forecasts/);
  assert.equal(context.getForecastHistory()[0].districtName, "Bagong Silangan");
});

test("city, model, and whole-district history have distinct coverage labels", () => {
  const { context } = createContext();
  const city = context.getLSTMHistoryScope("Quezon City (All)");
  assert.equal(city.scope, "city");
  assert.match(context.formatBarangayCell([], city), /City-wide/);
  assert.match(context.formatBarangayCell([], { method: "bn_inference" }), /Not barangay-specific/);
  assert.match(context.formatBarangayCell([], { method: "short_term" }), /All barangays/);
});

test("rising and falling use the correct arrows; unknown trends never imply stability", () => {
  const { context } = createContext();
  const render = trend => context.formatResultCell({ trend });
  assert.equal(render("rising"), render("increasing"));
  assert.equal(render("falling"), render("decreasing"));
  assert.match(render("rising"), /var\(--red\)/);
  assert.match(render("falling"), /var\(--green\)/);
  assert.doesNotMatch(render("rising"), /M4 12h16/);
  assert.match(render("stable"), /M4 12h16/);
  assert.doesNotMatch(render("unknown"), /<svg/);
});

test("LSTM dataset aliases retain their canonical barangay and district in history", () => {
  const { context } = createContext();
  const aliases = [
    ["Aurora", "Do\u00f1a Aurora", "IV"],
    ["Balong Bato", "Balon-Bato", "VI"],
    ["Claro", "Claro (Quirino 3-B)", "III"],
    ["Dona Imelda", "Do\u00f1a Imelda", "IV"],
    ["Dona Josefa", "Do\u00f1a Josefa", "IV"],
    ["Duyan-duyan", "Duyan Duyan", "III"],
    ["N.S. Amoranto (Gintong Silahis)", "N. S. Amoranto (Gintong Silahis)", "I"],
    ["New Era (Constitution Hills)", "New Era", "VI"],
    ["Pasong Putik Proper (Pasong Putik)", "Pasong Putik Proper", "V"],
    ["Santo Domingo (Matalahib)", "Sto. Domingo (Matalahib)", "I"],
    ["Santo Nino", "Santo Ni\u00f1o", "IV"],
    ["U.P. Campus", "U. P. Campus", "IV"],
    ["U.P. Village", "U. P. Village", "IV"],
  ];
  for (const [area, barangay, district] of aliases) {
    context.renderLSTMResult({ ...lstmResult, prediction_scope: area });
    const entry = context.getForecastHistory()[0];
    assert.equal(entry.districtName, `District ${district}`, area);
    assert.deepEqual(Array.from(entry.barangays), [barangay], area);
    assert.equal(entry.predictionScope, barangay, area);
  }
});

test("legacy aliased LSTM areas appear in the correct district filter", () => {
  const { context, elements } = createContext();
  context.saveForecastHistory([{ method: "lstm", districtName: "U.P. Campus", barangays: [], timestamp: "2026-09-23T12:00:00Z", summary: "W1: 6 cases" }]);
  elements["hist-filter-district"].value = "District IV";
  context.renderHistoricalTable();
  assert.match(elements["history-content"].innerHTML, /U\. P\. Campus/);
  assert.match(elements["history-content"].innerHTML, /District IV/);
  assert.doesNotMatch(elements["history-content"].innerHTML, /No logged forecasts/);
  assert.equal(context.getForecastHistory()[0].districtName, "U.P. Campus");
});
