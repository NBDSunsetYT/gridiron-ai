import {describe,it,expect,vi,afterEach} from 'vitest';
import {automaticEvidenceMemo,attachAutomaticEvidence} from '../lib/probability/automatic-props';
import * as quality from '../lib/probability/simulation-quality';
afterEach(()=>{vi.restoreAllMocks();vi.useRealTimers();});
const row={sport:'CFB',espnEventId:'123456789',eventId:'provider-event',player:{id:'espn:17'},kickoff:'2030-01-01T12:00:00Z',americanOdds:-110,statistic:'receivingYards',side:'Over',threshold:'40.5'};
function badEvidence(){return{sport:'CFB',espnEventId:row.espnEventId,eventStart:row.kickoff,research:{playerCatalog:[{id:'cfb:espn:17',name:'SYNTHETIC player'}]},result:{players:{'cfb:espn:17':{passingYards:{mean:0},receivingYards:{mean:10},completions:{mean:0},receptions:{mean:1}}}}};}
describe('Request-scoped game integrity audit reuse',()=>{
 it('keeps every failed accounting decision identical while auditing a shared game once',()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2029-12-01T12:00:00Z'));const evidence=badEvidence(),injuries:any[]=[],job={id:'synthetic',status:'queued'},audit=vi.spyOn(quality,'footballSimulationQuality');
  const expected=attachAutomaticEvidence(row,evidence,job,injuries);audit.mockClear();const memo=automaticEvidenceMemo(injuries);
  for(let i=0;i<500;i++)expect(attachAutomaticEvidence(row,evidence,job,injuries,memo)).toEqual(expected);
  expect(audit).toHaveBeenCalledTimes(1);expect(expected.state).toBe('simulation_failed');expect(expected.modelProbability).toBeNull();
 });
 it('does not reuse a decision for new evidence or a changed injury snapshot',()=>{
  const injuries:any[]=[],memo=automaticEvidenceMemo(injuries),evidence=badEvidence(),audit=vi.spyOn(quality,'footballSimulationQuality');
  attachAutomaticEvidence(row,evidence,{},injuries,memo);attachAutomaticEvidence(row,badEvidence(),{},injuries,memo);attachAutomaticEvidence(row,evidence,{},[],memo);
  expect(audit).toHaveBeenCalledTimes(3);
 });
 it('describes queued work without claiming that a worker is running',()=>{const result=attachAutomaticEvidence(row,null,{status:'queued'},[]);expect(result.state).toBe('preparing_simulation');expect(result.reason).toContain('waiting for the controlled worker');expect(result.rawProbability).toBeNull();});
 it('preserves raw hit probability, Monte Carlo error and interval for a usable distribution',()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2029-12-01T12:00:00Z'));const injuries:any[]=[],evidence={sport:'CFB',espnEventId:row.espnEventId,eventStart:row.kickoff,triggerHash:'fixed',method:'full_game_simulation',checkedAt:new Date().toISOString(),playerCatalog:[{id:'cfb:espn:17'}],result:{simulations:10000,modelVersion:'SYNTHETIC',players:{'cfb:espn:17':{receivingYards:{histogram:[{value:0,count:4000},{value:60,count:6000}]}}}}},job={status:'ready',input_hash:'fixed',due_at:row.kickoff};
  const before=attachAutomaticEvidence(row,evidence,job,injuries),after=attachAutomaticEvidence(row,evidence,job,injuries,automaticEvidenceMemo(injuries));expect(after).toEqual(before);expect(after.rawProbability).toBe(.6);expect(after.monteCarloStandardError).toBeCloseTo(Math.sqrt(.24/10000),12);expect(after.calibratedProbability).toBeNull();
 });
});
