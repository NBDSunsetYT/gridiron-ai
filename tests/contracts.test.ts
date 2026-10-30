import {describe,it,expect} from 'vitest';
import {valueContract,validateQuote,performanceHistory,injuryChanges,validateSimulationSettlement} from '../lib/contracts';
const terms={yesAskCents:'63.25',noAskCents:'38.50',entryFeeCents:'0.35',winFeeCents:'1.25',entryFeeRounding:'none' as const};
describe('binary contract cents valuation',()=>{
  it('keeps exact penny/subpenny fees and hypothetical profit distinct from sportsbook odds',()=>{
    const v=valueContract(terms,.7,'YES',10);
    expect(v.costCents).toBe('636');expect(v.entryFeeCents).toBe('3.5');expect(v.winFeeCents).toBe('12.5');
    expect(v.winNetProfitCents).toBe('351.5');expect(v.lossNetProfitCents).toBe('-636');expect(v.expectedProfitCents).toBe('55.25000000');
    expect(v.breakEvenProbability).toBeCloseTo(636/987.5);
  });
  it('prices NO separately and uses complementary outcome probability',()=>{
    const v=valueContract(terms,.7,'NO',1);
    expect(v.askCents).toBe('38.5');expect(v.probability).toBeCloseTo(.3);expect(Number(v.expectedProfitCents)).toBeLessThan(0);
  });
  it('supports explicitly specified aggregate fee rounding',()=>{
    const v=valueContract({...terms,entryFeeCents:'0.125',entryFeeRounding:'up_to_cent'},.5,'YES',3);
    expect(v.entryFeeCents).toBe('1');expect(v.costCents).toBe('190.75');
  });
  it('rejects probabilities at unbounded certainty and invalid quantities',()=>{
    expect(()=>valueContract(terms,1,'YES',1)).toThrow();expect(()=>valueContract(terms,.5,'YES',1.5)).toThrow();
  });
});
const quote=(id:string,time:string,ask='60')=>({id,contractId:'exact-contract',eventId:'event',event:'Away @ Home',question:'Player over 64.5 yards?',threshold:64.5,operator:'gt' as const,eventStart:'2025-01-02T12:00:00Z',settlementRule:'Strictly greater than 64.5 official receiving yards.',rulesUrl:'https://example.com/rules',yesAskCents:ask,noAskCents:'42',liquidityContracts:null,quotedAt:time,sourceUrl:'https://example.com/contract',verified:true as const,entryFeeCents:'1',winFeeCents:'0',feeSource:'Manual verified schedule',entryFeeRounding:'none' as const,source:'manual_verified' as const,createdAt:time});
describe('prospective history and look-ahead control',()=>{
  const early=quote('q1','2025-01-01T12:00:00Z'),close=quote('q2','2025-01-02T11:59:00Z','65'),post=quote('q3','2025-01-02T12:01:00Z','99');
  const p={id:'p1',kind:'binary_contract',contractId:'exact-contract',quoteId:'q1',yesProbability:.7,side:'YES',modelVersion:'test',auditStatus:'prospective',stale:false,createdAt:'2025-01-01T12:00:30Z'};
  it('scores first unique prospective prediction and excludes post-event closing quotes',()=>{
    const out=performanceHistory([early,close,post],[p,{...p,id:'p2',yesProbability:.99,createdAt:'2025-01-01T13:00:00Z'}],[{contractId:'exact-contract',outcome:1}]);
    expect(out.n).toBe(1);expect(out.brier).toBeCloseTo(.09);expect(out.clv).toBe(5);expect(out.sampleWarning).toMatch(/Insufficient/);
  });
  it('excludes retrospective imports and stale-at-placement predictions',()=>{
    expect(performanceHistory([early],[{...p,auditStatus:'retrospective_import'}],[{contractId:'exact-contract',outcome:1}]).n).toBe(0);
    expect(performanceHistory([early],[{...p,stale:true}],[{contractId:'exact-contract',outcome:1}]).brier).toBeNull();
  });
  it('does not accept future quotes or American odds as contract cents',()=>{
    expect(()=>validateQuote({...early,quotedAt:'2099-01-01T00:00:00Z'},new Date('2026-01-01'))).toThrow();
    expect(()=>validateQuote({...early,yesAskCents:'-110'})).toThrow();
  });
  it('invalidates changed injury facts while retaining immutable prior snapshot versions',()=>{
    const versions=[{entityKey:'player-one',factsHash:'old'}];
    const records=[{id:'a',entityKey:'player-one',factsHash:'old',createdAt:'2026-01-01T00:00:00Z'},{id:'b',entityKey:'player-one',factsHash:'new',createdAt:'2026-01-02T00:00:00Z'}];
    expect(injuryChanges(versions,records).map(r=>r.id)).toEqual(['b']);expect(versions[0].factsHash).toBe('old');
    expect(injuryChanges(versions,[records[0]])).toEqual([]);
  });
});
describe('generated forecast participant and market matching',()=>{
  const definition={kind:'player' as const,home:'HOME',away:'AWAY',playerId:'player-one',stat:'receivingYards' as const,threshold:64.5,direction:'over' as const,equality:'no' as const};
  const q={...quote('quoted','2025-01-01T12:00:00Z'),settlementDefinition:definition};
  const contract={id:q.contractId,pushProbability:0,settlement:{id:q.contractId,...definition}};
  it('accepts only the same exact player, statistic, market kind and matchup',()=>{
    expect(()=>validateSimulationSettlement(q,contract,{home:'HOME',away:'AWAY'})).not.toThrow();
    expect(()=>validateSimulationSettlement(q,{...contract,settlement:{...contract.settlement,playerId:'different-player'}},{home:'HOME',away:'AWAY'})).toThrow(/does not match/);
    expect(()=>validateSimulationSettlement(q,{...contract,settlement:{...contract.settlement,kind:'total'}},{home:'HOME',away:'AWAY'})).toThrow(/does not match/);
    expect(()=>validateSimulationSettlement(q,{...contract,settlement:{...contract.settlement,stat:'passingYards'}},{home:'HOME',away:'AWAY'})).toThrow(/does not match/);
    expect(()=>validateSimulationSettlement(q,contract,{home:'OTHER',away:'AWAY'})).toThrow(/does not match/);
  });
  it('blocks legacy unstructured quotes from claiming generated attachment',()=>{
    expect(()=>validateSimulationSettlement(quote('legacy','2025-01-01T12:00:00Z'),contract,{home:'HOME',away:'AWAY'})).toThrow(/structured settlementDefinition/);
  });
});
