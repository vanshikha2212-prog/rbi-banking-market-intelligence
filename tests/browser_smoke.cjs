/* Optional browser integration check. Requires Playwright and a Chromium binary.
 * node tests/browser_smoke.cjs
 * PLAYWRIGHT_MODULE and RBI_CHROMIUM_EXECUTABLE may point to installed runtimes.
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

async function main() {
  const root = path.resolve(__dirname, '..');
  const output = path.join(root, 'outputs', 'dashboard.html');
  const launch = {headless: true};
  if (process.env.RBI_CHROMIUM_EXECUTABLE) {
    launch.executablePath = process.env.RBI_CHROMIUM_EXECUTABLE;
    launch.args = ['--no-sandbox', '--disable-dev-shm-usage', '--no-zygote'];
  }
  const browser = await chromium.launch(launch);
  const errors = [], networkRequests = [], checks = [];
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1050}, acceptDownloads: true});
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', async route => {
      if (/^https?:/.test(route.request().url())) {
        networkRequests.push(route.request().url());
        await route.abort();
      } else await route.continue();
    });
    await page.goto(pathToFileURL(output).href);
    const payload = await page.locator('#research-data').evaluate(node => JSON.parse(node.textContent));
    const text = id => page.locator('#' + id).innerText();
    assert.equal(await text('kpiEvents'), '18');
    assert.equal(await text('kpiBanks'), '6');
    assert.match(await text('recordCount'), /108/);
    const primary = payload.results.filter(r => r.benchmark === '^NSEI' && r.window === '[-1,+1]');
    const expected = (100 * primary.reduce((a, r) => a + r.car, 0) / primary.length).toFixed(2) + '%';
    assert.equal((await text('kpiCar')).replace(/^\+/, ''), expected);
    checks.push('Default counts and percentage conversion agree with embedded numerical results');
    assert.equal(await page.locator('#eventRows tr').count(), 18);
    const august = payload.events.find(e => e.event_date === '2025-08-06');
    assert.ok(august, 'Corrected August announcement is present');
    assert.ok(!payload.events.some(e => e.event_date === '2025-08-07'));
    checks.push('All 18 announcement rows render and the August 2025 date is corrected');
    await page.selectOption('#decision', 'Cut');
    assert.equal(await text('kpiEvents'), '4');
    assert.match(await text('recordCount'), /24/);
    await page.selectOption('#bankType', 'Public');
    assert.equal(await text('kpiBanks'), '3');
    assert.match(await text('recordCount'), /12/);
    checks.push('Policy and bank-group filters maintain distinct-event and bank-row counts');
    await page.selectOption('#event', String(august.event_id));
    assert.equal(await text('kpiEvents'), '0');
    assert.match(await page.locator('#eventRows').innerText(), /No announcements/);
    await page.click('#reset');
    await page.selectOption('#event', String(august.event_id));
    assert.equal(await text('kpiEvents'), '1');
    assert.match(await page.locator('#eventRows').innerText(), /06 Aug 2025/);
    checks.push('Contradictory filters render an empty state; reset and single-event selection recover');
    await page.click('#reset');
    await page.selectOption('#benchmark', '^NSEBANK');
    await page.selectOption('#window', '[0,+1]');
    assert.equal(await text('kpiEvents'), '18');
    assert.match(await text('windowDescription'), /0/);
    checks.push('Alternative benchmark and future prediction window render correctly');
    await page.click('#reset');
    const downloadPromise = page.waitForEvent('download');
    await page.click('#download');
    const download = await downloadPromise;
    const csv = fs.readFileSync(await download.path(), 'utf8');
    assert.equal(csv.trim().split(/\r?\n/).length, 109);
    assert.match(csv.split(/\r?\n/)[0], /absolute_car/);
    checks.push('Offline CSV download contains 108 records plus a header');
    assert.equal(await page.locator('#chartEvents svg').count(), 1);
    assert.equal(await page.locator('#chartBanks svg').count(), 1);
    assert.equal(await page.locator('#chartRisk svg').count(), 1);
    const assets = path.join(root, 'test-results');
    fs.mkdirSync(assets, {recursive: true});
    await page.screenshot({path: path.join(assets, 'dashboard.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Mobile page must not overflow horizontally');
    await page.selectOption('#decision', 'Hike');
    assert.equal(await text('kpiEvents'), '1');
    assert.match(await text('sampleWarning'), /one|single|1/i);
    checks.push('Mobile layout fits a 390px viewport and single-hike warning remains visible');
    await page.click('#reset');
    const temporary = path.join(root, 'test-results');
    fs.mkdirSync(temporary, {recursive: true});
    await page.screenshot({path: path.join(temporary, 'dashboard-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    assert.deepEqual(networkRequests, []);
    checks.push('No JavaScript page errors or external HTTP(S) requests');
    const result = {status: 'passed', browser: browser.version(), checked_at_utc: new Date().toISOString(),
                    dashboard_sha256: require('node:crypto').createHash('sha256').update(fs.readFileSync(output)).digest('hex'),
                    desktop_viewport: [1440, 1050], mobile_viewport: [390, 844], checks};
    const verification = path.join(root, 'docs', 'verification');
    fs.mkdirSync(verification, {recursive: true});
    fs.writeFileSync(path.join(verification, 'browser_smoke.json'), JSON.stringify(result, null, 2) + '\n');
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch(error => {console.error(error); process.exitCode = 1;});
