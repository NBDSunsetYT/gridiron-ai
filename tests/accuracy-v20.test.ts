import {describe,it,expect} from 'vitest';
import report from '@/docs/reports/accuracy-first-v20.json';
import {GET} from '@/app/api/engine/route';
describe('V20 accuracy-first cached research boundary',()=>{
 it('serves real evidence without mutating or calculating forecasts',async()=>{
  const r=await GET(new Request('https://example.com/api/engine?view=accuracyFirst'));
  expect(r.status).toBe(200);expect(r.headers.get('CDN-Cache-Control')).toContain('s-maxage=300');const body=await r.json();expect(body.productionPromotions).toBe(0);expect(body.reservedFinalOpened).toBe(false);expect(body.productionWrites).toBe(0);expect(body.leagues.CFB.evidenceCoverage.games).toBe(300);expect(body.leagues.NBA.evidenceCoverage.completePointInTimeGames).toBe(0);
 });
 it('keeps expected-value, probability and interval scores separate',()=>{
  for(const l of Object.values(report.leagues)){
   expect(l.evidenceCoverage.unconditionalForecastsWithheld).toBe(l.evidenceCoverage.games);expect(l.promotionQualified).toBe(false);
   for(const p of Object.values(l.probabilityAndIntervals)){expect(p.calibratedMoneyline).toBe(null);expect(p.rawMoneyline?.n).toBe(p.games);for(const c of Object.values(p.categories) as {meanCRPS:number;coverage:Record<string,number>}[]){expect(c.meanCRPS).toBeGreaterThanOrEqual(0);expect(Object.keys(c.coverage)).toEqual(['0.5','0.8','0.9','0.95']);}}
  }
 });
 it('preserves and exposes the quarantined CFB failure',()=>{
  const q=report.quarantined.find(q=>q.eventId==='cfb:espn:401643803');expect(q?.flags).toContain('extreme_expected_team_score');expect(q?.productionPublished).toBe(false);
 });
 it('keeps the locked fresh confirmation separate and does not declare superiority',()=>{
  expect(report.forwardConfirmation.noFurtherTuning).toBe(true);expect(report.forwardConfirmation.productionPromotion).toBe(false);
  expect(report.forwardConfirmation.leagues.NBA.gradedGames).toBe(75);expect(report.forwardConfirmation.leagues.NFL.gradedGames).toBe(7);expect(report.forwardConfirmation.leagues.CFB.gradedGames).toBe(0);
  expect(report.forwardConfirmation.leagues.NBA.primary.primaryMAEDelta?.bootstrap95[1]).toBeGreaterThan(0);expect(report.forwardConfirmation.leagues.NFL.primary.primaryMAEDelta?.bootstrap95[1]).toBeGreaterThan(0);
  expect(report.forwardConfirmation.receipt.newSimulations).toBe(0);expect(report.independenceAudit.overlapWithSelectedV20Games).toEqual([]);
 });
});
