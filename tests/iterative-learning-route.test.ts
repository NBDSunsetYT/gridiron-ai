import {describe, expect, it} from 'vitest';
import {GET} from '../app/api/engine/route';
import report from '../docs/reports/v16-iterative-learning.json';
import protocol from '../docs/reports/v16-protocol.json';
describe('Public frozen experiment reports', () => {
 it('serves actual completed evidence to guests without starting jobs', async () => {
  const response = await GET(new Request('https://gridiron.test/api/engine?view=iterations'));
  expect(response.status).toBe(200);
  expect(response.headers.get('cache-control')).toContain('public');
  expect(response.headers.get('cdn-cache-control')).toContain('s-maxage=300');
  const data = await response.json();
  expect(data.protocolSha256).toBe(protocol.sha256);
  expect(data.forecastVersions).toBe(report.forecastVersions);
  expect(data.completeSimulatedGames).toBe(data.forecastVersions * 10000);
  expect(data.finalTestComplete).toBe(true);
  expect(data.productionPromotions).toBe(0);
 });
 it('exposes separate paired diagnostics and predeclared chronological periods', async () => {
  const paired = await (await GET(new Request('https://gridiron.test/api/engine?view=paired'))).json();
  expect(paired.finalTestDidNotSelectModels).toBe(true);
  for (const sport of ['NFL', 'CFB', 'NBA']) {
   const coverage = protocol.coverage.filter(row => row.sport === sport);
   expect(coverage.filter(row => row.phase === 'validation')).toHaveLength(3);
   const test = coverage.find(row => row.phase === 'test')!;
   expect(coverage.filter(row => row.phase === 'validation').every(row => row.end <= test.start)).toBe(true);
  }
 });
 it('does not allow arbitrary report paths or prototype property selection', async () => {
  for (const view of ['toString', '__proto__', '../../.env.local']) {
   expect((await GET(new Request('https://gridiron.test/api/engine?view=' + encodeURIComponent(view)))).status).toBe(400);
  }
 });
});
