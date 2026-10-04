import { spawn } from 'node:child_process';
import { access, mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';

if (typeof WebSocket !== 'function') {
  throw new Error('Browser layout checks require Node.js 22 or later (built-in WebSocket).');
}
const baseUrl = process.env.FRONTEND_TEST_URL || process.env.BASE_URL || 'http://127.0.0.1:5000';
const output = resolve('output/frontend-layout');
const browserCandidates = process.env.CHROME_PATH ? [process.env.CHROME_PATH] : [
  ...[process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA]
    .filter(Boolean).map(folder => join(folder, 'Google/Chrome/Application/chrome.exe')),
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser',
];
let chromePath;
for (const candidate of browserCandidates) {
  try { await access(candidate); chromePath = candidate; break; } catch { /* Try the next installed browser. */ }
}
if (!chromePath) throw new Error('Chrome/Chromium was not found. Set CHROME_PATH to its executable.');
await mkdir(output, { recursive: true });
const profile = await mkdtemp(resolve(output, 'mobile-chrome-'));
const browser = spawn(chromePath, [
  '--headless', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
  '--no-first-run', '--no-default-browser-check', '--disable-background-networking', 'about:blank',
], { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] });
const results = [], errors = [], pending = new Map();
let socket, sequence = 0, sessionId;
const pause = ms => new Promise(r => setTimeout(r, ms));
const report = (name, ok, data = {}) => results.push({ name, ok, ...data });
const shutdown = () => { socket?.close(); if (browser.exitCode === null) browser.kill(); };
process.once('SIGINT', () => { shutdown(); process.exit(130); });
process.once('SIGTERM', () => { shutdown(); process.exit(143); });
try {
  const endpoint = await new Promise((resolveEndpoint, reject) => {
    let stderr = '';
    const timeout = setTimeout(() => reject(new Error(`Chrome startup timed out: ${stderr.slice(-1200)}`)), 20000);
    browser.once('error', reject);
    browser.once('exit', code => { clearTimeout(timeout); reject(new Error(`Chrome exited ${code}`)); });
    browser.stderr.on('data', chunk => {
      stderr += chunk.toString();
      const match = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) { clearTimeout(timeout); resolveEndpoint(match[1]); }
    });
  });
  socket = new WebSocket(endpoint);
  await new Promise((r, j) => { socket.addEventListener('open', r, { once: true }); socket.addEventListener('error', j, { once: true }); });
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails);
    const request = pending.get(message.id);
    if (request) { pending.delete(message.id); clearTimeout(request.timeout); message.error ? request.reject(new Error(JSON.stringify(message.error))) : request.resolve(message.result); }
  });
  const send = (method, params = {}, scoped = true) => new Promise((resolveRequest, reject) => {
    const id = ++sequence;
    const timeout = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 20000);
    pending.set(id, { resolve: resolveRequest, reject, timeout });
    socket.send(JSON.stringify({ id, method, params, ...(scoped && sessionId ? { sessionId } : {}) }));
  });
  const target = await send('Target.createTarget', { url: 'about:blank' }, false);
  ({ sessionId } = await send('Target.attachToTarget', { targetId: target.targetId, flatten: true }, false));
  await send('Page.enable'); await send('Runtime.enable');
  await send('Page.bringToFront');
  const evaluate = async expression => {
    const value = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (value.exceptionDetails) throw new Error(JSON.stringify(value.exceptionDetails));
    return value.result.value;
  };
  const until = async (expression, description) => {
    // Flask can initialize the research model lazily on the first dashboard request.
    for (let i = 0; i < 300; i++) { if (await evaluate(expression)) return; await pause(200); }
    throw new Error(`Timed out: ${description}`);
  };
  const inspect = () => evaluate(`(() => {
    const width = innerWidth, intended = '.table-wrap,.facilities-tabs-container,.map-canvas';
    const overflow = [...document.querySelectorAll('body *')].filter(e => {
      if (!(e instanceof HTMLElement) || !e.getClientRects().length || e.parentElement?.closest(intended)) return false;
      const s = getComputedStyle(e); if (s.visibility === 'hidden' || s.opacity === '0') return false;
      let r = e.getBoundingClientRect(), left = r.left, right = r.right;
      if (!r.width || !r.height) return false;
      for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {
        const ps = getComputedStyle(p); if (ps.visibility === 'hidden' || ps.opacity === '0') return false;
        if (/(hidden|clip|auto|scroll)/.test(ps.overflowX)) { const pr = p.getBoundingClientRect(); left = Math.max(left, pr.left); right = Math.min(right, pr.right); }
      }
      return right > left && (left < -1 || right > width + 1);
    }).map(e => { const r = e.getBoundingClientRect(); return { tag:e.tagName, id:e.id, class:e.className, left:r.left, right:r.right }; });
    const box = selector => { const e=document.querySelector(selector); if (!e || !e.getClientRects().length) return null; const r=e.getBoundingClientRect(); return {top:r.top,bottom:r.bottom,width:r.width,height:r.height}; };
    return {width, documentWidth:document.documentElement.scrollWidth, scrollY, height:innerHeight, activePage:document.querySelector('.page.active')?.id,
      overflow, panel:box('#forecast-panel'), districtSelect:box('#forecast-district'), toggle:box('#toggle-forecast-btn'), nav:box('.mobile-bottom-nav'),
      expanded:document.querySelector('#toggle-forecast-btn')?.getAttribute('aria-expanded'), focused:document.activeElement?.id};
  })()`);
  const capture = async (width, page) => {
    if (![320, 390, 430].includes(width) && !(width === 1440 && page === 'dashboard')) return;
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    await writeFile(resolve(output, `mobile-${width}-${page}.png`), Buffer.from(shot.data, 'base64'));
  };
  const measure = async (width, page) => {
    await pause(450);
    // Freeze finite CSS transitions at their endpoint for deterministic layout measurements.
    await evaluate(`document.getAnimations().filter(a => Number.isFinite(a.effect.getComputedTiming().endTime)).forEach(a => a.finish())`);
    const metrics = await inspect();
    report(`${width}/${page}/layout`, metrics.overflow.length === 0 && metrics.documentWidth <= metrics.width + 1, metrics);
    await capture(width, page);
    return metrics;
  };
  const navigate = async page => {
    await evaluate(`(() => { const buttons=[...document.querySelectorAll('[data-page="${page}"]')]; const button=buttons.find(e=>e.getClientRects().length); if(button) button.click(); else showPage('${page}'); })()`);
    await until(`document.querySelector('#page-${page}').classList.contains('active')`, `navigate ${page}`);
  };
  for (const width of [320, 390, 430, 600, 768, 820, 1440]) {
    console.log(`Checking ${width}px`);
    await send('Emulation.setDeviceMetricsOverride', { width, height: 844, deviceScaleFactor: 1, mobile: width < 1440 });
    await send('Emulation.setTouchEmulationEnabled', { enabled: width < 1440 });
    await send('Page.navigate', { url: baseUrl });
    await until(`document.readyState==='complete' && document.querySelectorAll('.dashboard-district-card').length===6`, 'dashboard ready');
    await evaluate('document.fonts.ready');
    await evaluate('localStorage.clear()');
    await measure(width, 'dashboard');
    await navigate('history');
    report(`${width}/history/empty`, await evaluate(`document.querySelector('#history-content').textContent.includes('No forecasts yet.')`));
    await navigate('dashboard');
    await evaluate(`document.querySelector('#toggle-forecast-btn').click()`);
    await pause(700);
    const opened = await measure(width, 'forecast');
    report(`${width}/forecast/open`, opened.expanded === 'true' && !!opened.panel && opened.panel.top < opened.height && opened.panel.bottom > 0 && !!opened.districtSelect && opened.districtSelect.top < opened.height, { panel: opened.panel, districtSelect: opened.districtSelect });
    await evaluate(`document.querySelector('#get-forecast-btn').click()`);
    await until(`document.querySelectorAll('.forecast-week').length === 3`, 'forecast result');
    report(`${width}/forecast/selected-values`, await evaluate(`(() => {
      const value = id => document.getElementById(id).textContent;
      return value('kpi-total-forecast') === '8' && value('kpi-high-risk') === 'BELOW'
        && [...document.querySelectorAll('.forecast-cell')].every(cell => cell.textContent === (cell.dataset.districtId === 'I' ? '8' : '--'))
        && [...document.querySelectorAll('.dashboard-district-card')].every(card => card.querySelector('.risk-pill').textContent === (card.dataset.districtId === 'I' ? 'BELOW' : 'NOT FORECASTED'));
    })()`));
    await evaluate(`(() => { const select = document.querySelector('#forecast-district'); select.value = 'II'; select.dispatchEvent(new Event('change')); })()`);
    report(`${width}/forecast/change-clears`, await evaluate(`document.querySelector('#kpi-total-forecast').textContent === '--' && document.querySelectorAll('.forecast-week').length === 0 && getForecastHistory().length === 1`));
    await evaluate(`document.querySelector('#get-forecast-btn').click()`);
    await until(`document.querySelectorAll('.forecast-week').length === 3`, 'second district result');
    report(`${width}/forecast/new-selection`, await evaluate(`document.querySelector('#kpi-total-forecast').textContent === '10' && document.querySelector('#kpi-total-forecast').parentElement.querySelector('.kpi-note').textContent === 'District II'`));
    await evaluate(`document.querySelector('#short-term-forecast-container').scrollIntoView({behavior:'instant',block:'start'})`);
    await measure(width, 'forecast-result');
    await evaluate(`document.querySelector('#close-forecast-btn').click()`);
    await pause(700);
    const closed = await inspect();
    report(`${width}/forecast/close`, closed.expanded === 'false' && !closed.panel && closed.toggle?.top >= -1 && closed.toggle?.bottom <= closed.height, { toggle: closed.toggle, focused: closed.focused });
    await navigate('districts'); await until(`document.querySelectorAll('.dist-card').length===6`, 'districts ready');
    await measure(width, 'districts');
    await evaluate(`window.showDistrictDetail('I')`); await pause(700); await measure(width, 'district-detail');
    report(`${width}/district/detail`, await evaluate(`!document.querySelector('#district-detail-card').hidden && document.querySelector('#det-name').textContent.includes('I')`));
    await evaluate(`document.querySelector('#btn-view-district-facilities').click()`);
    report(`${width}/district/facilities-link`, await evaluate(`document.querySelector('#page-facilities').classList.contains('active')`));
    await navigate('history'); await measure(width, 'history');
    report(`${width}/history/recorded`, await evaluate(`document.querySelectorAll('.hist-table tbody tr').length === 2 && document.querySelector('.hist-trend').textContent.includes('increasing') && document.querySelector('.hist-trend path').getAttribute('d') === TREND_ICONS.increasing.arrow`));
    await evaluate(`renderLSTMResult({prediction_scope:'Bagong Silangan', predictions:[{predicted_cases:6},{predicted_cases:7}]})`);
    report(`${width}/history/lstm-area`, await evaluate(`(() => { const row = document.querySelector('.hist-table tbody tr'); return row.cells[2].textContent === 'District II' && row.cells[3].textContent === 'Bagong Silangan' && document.querySelector('#kpi-total-forecast').textContent === '10'; })()`));
    await measure(width, 'history-with-lstm');
    await navigate('dashboard');
    await evaluate(`revealDistrictForecast('V', {next_week_forecast:85, risk_level:'high'})`);
    await measure(width, 'dashboard-high-risk');
    await navigate('facilities');
    await until(`document.querySelector('#facility-active-img').complete && document.querySelector('#facility-active-img').naturalWidth>0`, 'facility image');
    await measure(width, 'facilities');
    report(`${width}/facilities/image`, true, await evaluate(`({naturalWidth:document.querySelector('#facility-active-img').naturalWidth,src:document.querySelector('#facility-active-img').getAttribute('src')})`));
    if (width < 1440) {
      const fit = await evaluate(`(() => { const image=document.querySelector('#facility-active-img'), viewport=document.querySelector('#facilities-viewport'), i=image.getBoundingClientRect(), v=viewport.getBoundingClientRect(); return { imageWidth:i.width, imageHeight:i.height, viewWidth:v.width, viewHeight:v.height, zoom:facilityZoom, mobile:matchMedia('(max-width:900px)').matches, offsetWidth:image.offsetWidth, offsetHeight:image.offsetHeight, clientWidth:viewport.clientWidth, clientHeight:viewport.clientHeight }; })()`);
      report(`${width}/facilities/fits`, fit.imageWidth <= fit.viewWidth + 1 && fit.imageHeight <= fit.viewHeight + 1, fit);
    }
    await navigate('about'); await measure(width, 'about');
  }
  report('runtime/errors', errors.length === 0, { errors });
  console.log(JSON.stringify({ checks: results.length, failures: results.filter(r => !r.ok), screenshots: output }, null, 2));
  if (results.some(r => !r.ok)) process.exitCode = 1;
} catch (error) {
  report('harness/error', false, { message: error.stack }); console.error(error.stack); process.exitCode = 1;
} finally {
  await writeFile(resolve(output, 'mobile-ui-metrics.json'), JSON.stringify({ results, errors }, null, 2));
  shutdown();
  for (const request of pending.values()) clearTimeout(request.timeout);
}
