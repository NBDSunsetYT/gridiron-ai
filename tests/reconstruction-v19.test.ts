import {describe,it,expect} from 'vitest';
import {GET} from '@/app/api/engine/route';
import {executeOfflineLearningTool} from '@/lib/learning/assistant';
describe('Measured structural research is read-only public evidence',()=>{
 it('serves cacheable raw research with source corrections and no promoted models',async()=>{
  const response=await GET(new Request('https://example.test/api/engine?view=reconstruction'));
  expect(response.status).toBe(200);expect(response.headers.get('Cache-Control')).toContain('s-maxage=300');
  const evidence=await response.json();expect(evidence.promoted).toEqual([]);expect(evidence.finalTestEvaluated).toBe(false);expect(evidence.dataCoverage.CFB.completeLineups).toBe(0);
  for(const league of Object.values(evidence.leagues) as any[])for(const candidate of Object.values(league.candidates) as any[]){expect(candidate.brier).toBeGreaterThanOrEqual(0);expect(candidate.brier).toBeLessThanOrEqual(1);}
  expect(evidence.resources.hostedSimulationRequests).toBe(0);expect(evidence.legacyTouchdownNotice.scope).toContain('only');
 });
 it('exposes an explicit source-scoped invalidation without claiming actual touchdowns were zero',async()=>{
  const response=await GET(new Request('https://example.test/api/engine?view=dataQuality'));const evidence=await response.json();expect(evidence.preserveOriginalArtifacts).toBe(true);expect(evidence.affectedStatistics).toContain('passingTouchdowns');expect(evidence.affectedSourceHashes).toHaveLength(2);
 });
 it('AI retrieves measured outcomes and limitations instead of running a new experiment',()=>{
  const evidence=executeOfflineLearningTool({sport:'CFB'});expect(evidence.structuralReconstruction.promoted).toEqual([]);expect(evidence.structuralReconstruction.status).toBe('research_only_no_promotion');expect(()=>executeOfflineLearningTool({sport:'unknown'})).toThrow();
 });
});
