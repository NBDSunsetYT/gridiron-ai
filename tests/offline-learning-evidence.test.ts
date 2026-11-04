import {describe, expect, it} from 'vitest';
import {offlineExperimentEvidence} from '../lib/learning/offline-evidence';

// SYNTHETIC boundary fixture only; these are not published accuracy results.
const report = {
 version: 'synthetic-boundary', generatedAt: '2026-01-01T00:00:00Z', uniqueGames: 3,
 forecastVersions: 4, completeSimulatedGames: 40000, strictPregameQualifiedGames: 0,
 productionPromotions: 0, productionChampion: null, finalTestComplete: true,
 researchSelectedModels: {NFL: 'reference', CFB: 'reference', NBA: 'reference'},
 diagnosticFinalists: {NFL: 'candidate', CFB: 'candidate', NBA: 'reference'},
 finalTest: {NFL: {games: 1}, CFB: {games: 1}, NBA: {games: 1}},
 stoppingConditions: {NFL: 'plateau', CFB: 'plateau', NBA: 'plateau'},
 iterations: [{sport: 'NFL', iteration: 1, challenger: 'candidate', incumbent: 'reference', gate: {passed: false}}],
 limitations: ['Synthetic fixture; no accuracy claim.'],
};
describe('Stored model experiment retrieval', () => {
 it('preserves actual source time, rejection and production qualification', () => {
  const result = offlineExperimentEvidence(report, {});
  expect(result.sourceTimestamp).toBe(report.generatedAt);
  expect(result.productionChampion).toBeNull();
  expect(result.productionPromotions).toBe(0);
  expect(result.decisions[0].gate).toEqual({passed: false});
  expect(result.interpretation).toContain('not historical betting lines');
 });
 it('filters by league without joining football and basketball measurements', () => {
  const result = offlineExperimentEvidence(report, {sport: 'NBA'});
  expect(Object.keys(result.untouchedPeriodEvaluation)).toEqual(['NBA']);
  expect(result.decisions).toEqual([]);
 });
 it('rejects private record selectors and unsupported sports', () => {
  expect(() => offlineExperimentEvidence(report, {userId: 'someone-else'})).toThrow();
  expect(() => offlineExperimentEvidence(report, {sport: 'soccer'})).toThrow();
 });
});
