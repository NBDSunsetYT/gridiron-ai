import {describe,it,expect} from 'vitest';
import {availabilityScenario,authoritativeUrl} from '../lib/injuries';
describe('verified injury evidence',()=>{
  it('does not invent questionable or doubtful availability weights',()=>{
    expect(availabilityScenario({status:'questionable'})).toBeNull();expect(availabilityScenario({status:'doubtful'})).toBeNull();expect(availabilityScenario({status:'limited'})).toBeNull();
  });
  it('derives scenario weights only from provided historical comparable counts',()=>{
    const c={active:12,limited:6,out:2,sourceUrl:'https://example.com/cohort',description:'Documented comparable game status records',asOf:'2026-01-01T00:00:00Z'};
    const r=availabilityScenario({status:'questionable',cohorts:c})!;
    expect(r.active).toBe(.6);expect(r.limited).toBe(.3);expect(r.out).toBe(.1);expect(r.sampleSize).toBe(20);
    expect(r.uncertainty!.active[0]).toBeLessThan(.6);expect(r.uncertainty!.active[1]).toBeGreaterThan(.6);
  });
  it('separates confirmed out designation from uncertain practice participation',()=>{
    expect(availabilityScenario({status:'out'})?.out).toBe(1);expect(availabilityScenario({status:'full'})).toBeNull();
  });
  it('checks official source hostname boundaries and HTTPS',()=>{
    expect(authoritativeUrl('https://www.nfl.com/injuries')).toBe(true);expect(authoritativeUrl('https://www.chiefs.com/news/report')).toBe(true);
    expect(authoritativeUrl('https://nfl.com.attacker.example/injuries')).toBe(false);expect(authoritativeUrl('http://nfl.com/injuries')).toBe(false);
  });
});
