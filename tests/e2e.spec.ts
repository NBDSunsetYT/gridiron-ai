import { expect, test } from '@playwright/test';

const credentials = () => ({ email: `qa-${Date.now()}-${Math.random().toString(36).slice(2)}@example.com`, password: 'Gridiron-test-password-1948' });

test('private records require authentication', async ({ request }) => {
  const result = await request.get('/api/ledger');
  expect(result.status()).toBe(401);
});

test('ledger persists exact cash movements and settlements without double counting', async ({ request }) => {
  const account = credentials();
  const register = await request.post('/api/auth', { data: { action: 'register', ...account } });
  expect(register.ok()).toBeTruthy();
  for (const transaction of [
    { type: 'deposit', amount: '1000.00' },
    { type: 'withdrawal', amount: '150.00' },
  ]) {
    const response = await request.post('/api/ledger', { data: { ...transaction, sportsbook: 'DraftKings' } });
    expect(response.ok()).toBeTruthy();
  }
  const placed = await request.post('/api/bets', { data: { action: 'place', sportsbook: 'DraftKings', event: 'QA imported event', market: 'moneyline', selection: 'QA selection', odds: -110, stake: '100.00' } });
  expect(placed.ok()).toBeTruthy();
  const betBody = await placed.json();
  const id = betBody.id || betBody.bet?.id;
  expect(id).toBeTruthy();
  const pending = await (await request.get('/api/ledger')).json();
  expect(pending.summary.pendingExposureCents).toBe(10000);
  expect(pending.summary.availableBalanceCents).toBe(75000);
  const settlement = await request.post('/api/bets', { data: { action: 'settle', id, result: 'won', payout: '175.00' } });
  expect(settlement.ok()).toBeTruthy();
  const report = await (await request.get('/api/ledger')).json();
  expect(report.summary.cashBalanceCents).toBe(92500);
  expect(report.summary.availableBalanceCents).toBe(92500);
  expect(report.summary.realizedPlCents).toBe(7500);
  expect(report.summary.totalDepositsCents).toBe(100000);
  expect(report.summary.totalWithdrawalsCents).toBe(15000);
  expect(report.summary.pendingExposureCents).toBe(0);
  const repeated = await request.post('/api/bets', { data: { action: 'settle', id, result: 'won', payout: '175.00' } });
  expect(repeated.ok()).toBeFalsy();
  const afterRetry = await (await request.get('/api/ledger')).json();
  expect(afterRetry.summary.cashBalanceCents).toBe(92500);
  await request.post('/api/auth', { data: { action: 'logout' } });
  const login = await request.post('/api/auth', { data: { action: 'login', ...account } });
  expect(login.ok()).toBeTruthy();
  const persisted = await (await request.get('/api/ledger')).json();
  expect(persisted.summary.realizedPlCents).toBe(7500);
  const backup = await request.post('/api/ledger/backup', { data: { password: 'Recovery-password-1738' } });
  expect(backup.ok()).toBeTruthy();
  const encrypted = await backup.json();
  expect(encrypted.format).toBe('gridiron-encrypted-backup-v1');
  expect(JSON.stringify(encrypted).includes(account.email)).toBe(false);

});

test('responsive application has no horizontal overflow and exposes installation assets', async ({ page, request }) => {
  await page.goto('/');
  await expect(page.getByText('GRIDIRON', { exact: false }).first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  const manifestResponse = await request.get('/manifest.webmanifest');
  expect(manifestResponse.ok()).toBeTruthy();
  const manifest = await manifestResponse.json();
  expect(manifest.display).toBe('standalone');
  expect(manifest.start_url).toBe('/');
  for (const icon of manifest.icons) expect((await request.get(icon.src)).ok()).toBeTruthy();
  const sw = await request.get('/sw.js');
  expect(sw.ok()).toBeTruthy();
  expect((await sw.text()).includes("url.pathname.startsWith('/api/')")).toBe(true);
  await page.screenshot({ path: `test-results/${test.info().project.name}-dashboard.png`, fullPage: true });
});

test('service worker serves offline interface without exposing cached private APIs', async ({ page, context }) => {
  await page.goto('/');
  await page.evaluate(async () => {
    await navigator.serviceWorker.register('/sw.js');
    await navigator.serviceWorker.ready;
  });
  await page.waitForTimeout(500);
  await context.setOffline(true);
  await page.goto('/offline-verification', { waitUntil: 'domcontentloaded' });
  await expect(page.getByText('Your research will be here when you reconnect.')).toBeVisible();
  const cacheUrls = await page.evaluate(async () => {
    const all = await Promise.all((await caches.keys()).map(async key => (await (await caches.open(key)).keys()).map(request => request.url)));
    return all.flat();
  });
  expect(cacheUrls.some(url => new URL(url).pathname.startsWith('/api/'))).toBe(false);
  await context.setOffline(false);
});
