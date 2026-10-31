import {describe,it,expect} from 'vitest';
import {collegeHistoricalPilot} from '../lib/college-football/validation';
describe('Retained college-football audit integrity',()=>{
 it('reports the actual weak retrospective pilot without relabeling it prospective, calibrated or promoted',()=>{
  const result=collegeHistoricalPilot();expect(result).toMatchObject({sport:'CFB',status:'retrospective_not_promoted',sampleSize:4,promoted:false,calibrated:false,publicationAvailabilityVerified:false,marketBenchmark:null});expect(result.brierScore).toBeCloseTo(0.3913260825,10);expect(result.logLoss).toBeCloseTo(1.0894075175,10);expect(result.message).toContain('weak');expect(result.sourceSha256).toMatch(/^[a-f0-9]{64}$/);
 });
});
