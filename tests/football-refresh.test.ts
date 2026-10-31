import {beforeEach,describe,it,expect,vi} from 'vitest';
const cfb=vi.hoisted(()=>({refreshCollegeResearch:vi.fn()}));
const nfl=vi.hoisted(()=>({refreshNflSportsbookReference:vi.fn()}));
vi.mock('../lib/college-football/service',()=>cfb);
vi.mock('../lib/sportsbook-reference/service',()=>nfl);
import {refreshAdditionalFootballResearch} from '../lib/football-refresh';
beforeEach(()=>{vi.clearAllMocks();cfb.refreshCollegeResearch.mockResolvedValue({status:'available',games:[{id:'SYNTHETIC source object not retained'}],raw:'SYNTHETIC-RAW-PAYLOAD'});nfl.refreshNflSportsbookReference.mockResolvedValue({status:'render_backend_required',offers:[{price:'SYNTHETIC-PRICE-NOT-PERSISTED'}]});});
describe('Bounded multi-sport background source updates',()=>{
 it('refreshes independent source families without placing quotes in the unguarded status cache',async()=>{
  const result=await refreshAdditionalFootballResearch();expect(cfb.refreshCollegeResearch).toHaveBeenCalledOnce();expect(nfl.refreshNflSportsbookReference).toHaveBeenCalledOnce();expect(result).toMatchObject([{sport:'CFB',status:'available'},{sport:'NFL',status:'render_backend_required'}]);expect(JSON.stringify(result)).not.toMatch(/SYNTHETIC|offers|games|raw|price/);
 });
 it('keeps a source failure distinct and never echoes upstream exception bodies or credentials',async()=>{
  cfb.refreshCollegeResearch.mockRejectedValue(Error('SYNTHETIC-PRIVATE-UPSTREAM-DETAIL'));const result=await refreshAdditionalFootballResearch();expect(result[0]).toMatchObject({sport:'CFB',status:'failed'});expect(result[1]).toMatchObject({sport:'NFL',status:'render_backend_required'});expect(JSON.stringify(result)).not.toContain('PRIVATE-UPSTREAM');
 });
});
