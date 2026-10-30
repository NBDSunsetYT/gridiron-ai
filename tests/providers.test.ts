import {describe,it,expect,vi} from 'vitest';
import {TheOddsApi} from '../lib/providers';
describe('authorized odds adapter',()=>{
  it('fails explicitly when credentials are missing',async()=>{
    const fetcher=vi.fn();await expect(new TheOddsApi('',fetcher).fetchMarkets()).rejects.toThrow(/not configured/);expect(fetcher).not.toHaveBeenCalled();
  });
  it('reports rate-limit failures and does not synthesize markets',async()=>{
    const fetcher=vi.fn().mockResolvedValue(new Response('{}',{status:429}));await expect(new TheOddsApi('test',fetcher).fetchMarkets()).rejects.toThrow(/quota/);
  });
  it('rejects malformed provider payloads',async()=>{
    const fetcher=vi.fn().mockResolvedValue(Response.json({error:'wrong'}));await expect(new TheOddsApi('test',fetcher).fetchMarkets()).rejects.toThrow(/event array/);
  });
  it('maps only actual supported bookmaker observations with provenance',async()=>{
    const data=[{id:'evt',home_team:'Home',away_team:'Away',bookmakers:[{key:'draftkings',last_update:'2026-10-28T12:00:00Z',markets:[{key:'h2h',outcomes:[{name:'Home',price:-110}]}]},{key:'unrelated',markets:[{key:'h2h',outcomes:[{name:'Away',price:110}]}]}]}];
    const fetcher=vi.fn().mockResolvedValue(Response.json(data));const markets=await new TheOddsApi('test',fetcher).fetchMarkets();
    expect(markets).toHaveLength(1);expect(markets[0]).toMatchObject({odds:-110,source:'feed',sportsbook:'DraftKings',sampleSize:0});expect(markets[0].model).toBeUndefined();
    expect(markets[0].observedAt).toBe('2026-10-28T12:00:00.000Z');
  });
});
