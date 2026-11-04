import {test, expect} from '@playwright/test';

test('public measured experiment report survives reload without starting simulations', async ({page}) => {
  const expensiveRequests: string[] = [];
  page.on('request', request => {
    if (request.method() === 'POST' && /(?:analy[sz]e|prepare|simulation|scan)/i.test(request.url())) expensiveRequests.push(request.url());
  });
  await page.goto('/#engine');
  const section = page.getByRole('region', {name: 'Iterative model research'});
  await expect(section.getByRole('heading', {name: 'What the model experiments showed'})).toBeVisible();
  const evidence = await page.evaluate(async () => {
    const response = await fetch('/api/engine?view=iterations');
    return {status: response.status, headers: response.headers.get('cdn-cache-control'), report: await response.json()};
  });
  expect(evidence.status).toBe(200);
  expect(evidence.headers).toContain('public');
  expect(evidence.report.uniqueGames).toBeGreaterThan(0);
  expect(evidence.report.completeSimulatedGames).toBe(evidence.report.forecastVersions * 10000);
  expect(evidence.report.productionPromotions).toBe(0);
  await expect(section.locator('.reality-score').filter({hasText: 'Games in this experiment'}).locator('strong')).toHaveText(String(evidence.report.uniqueGames));
  await page.reload();
  await expect(section.locator('.reality-score').filter({hasText: 'Games in this experiment'}).locator('strong')).toHaveText(String(evidence.report.uniqueGames));
  expect(expensiveRequests).toEqual([]);
});

test('sport filtering and player-category evidence remain readable on mobile', async ({page}) => {
  await page.goto('/#engine');
  await expect(page.getByRole('heading', {name: 'What the model experiments showed'})).toBeVisible();
  await page.getByRole('combobox', {name: 'Validation sport', exact: true}).selectOption('CFB');
  const section = page.getByRole('region', {name: 'Iterative model research'});
  await expect(section.getByRole('heading', {name: 'CFB · untouched final period'})).toBeVisible();
  await expect(section.getByRole('heading', {name: 'NBA · untouched final period'})).toHaveCount(0);
  await section.getByText('Challenger decisions', {exact: true}).click();
  await expect(section.getByRole('heading', {name: /Iteration 1/})).toBeVisible();
  await section.getByText('Player-category final errors', {exact: true}).click();
  await expect(section.getByRole('columnheader', {name: '90% interval coverage'}).first()).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);
});
