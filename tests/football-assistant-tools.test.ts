import {beforeEach,describe,it,expect,vi} from 'vitest';
const cfb=vi.hoisted(()=>({collegeDashboard:vi.fn(),collegeGameDetail:vi.fn(),collegePropScanner:vi.fn(),collegeSavedResearch:vi.fn(),analyzeCollegeGame:vi.fn()}));
const providers=vi.hoisted(()=>({freeProps:vi.fn()}));
const quota=vi.hoisted(()=>({publicRateLimit:vi.fn()}));
vi.mock('../lib/college-football/service',()=>cfb);
vi.mock('../lib/free-props-service',()=>providers);
vi.mock('../lib/public-nfl/store',()=>quota);
import {isFootballIntelligenceTool,executeFootballIntelligenceTool} from '../lib/college-football/assistant-tools';
const ctx:any={request:new Request('https://gridiron.example.test/api/assistant'),user:{id:'SYNTHETIC-CFB-OWNER'}};
beforeEach(()=>{vi.clearAllMocks();cfb.collegeDashboard.mockResolvedValue({sport:'CFB',games:[],coverage:'SYNTHETIC test transport'});cfb.collegeSavedResearch.mockResolvedValue({sport:'CFB',saved:[]});cfb.analyzeCollegeGame.mockResolvedValue({sport:'CFB',status:'insufficient_evidence',probability:null});providers.freeProps.mockResolvedValue({dataFamily:'sportsbook_reference',source:'PropLine',status:'render_backend_required',items:[]});});
describe('Evidence-scoped NFL/CFB research tools',()=>{
 it('reads college source evidence without starting compute or modifying personal records',async()=>{
  expect(isFootballIntelligenceTool('read_cfb_games')).toBe(true);expect(isFootballIntelligenceTool('arbitrary_sql')).toBe(false);
  expect(await executeFootballIntelligenceTool(ctx,'read_cfb_games',{date:'2026-11-07'},'Show college games.')).toMatchObject({sport:'CFB'});expect(cfb.collegeDashboard).toHaveBeenCalledWith({date:'2026-11-07'});expect(cfb.analyzeCollegeGame).not.toHaveBeenCalled();expect(quota.publicRateLimit).not.toHaveBeenCalled();
 });
 it('does not let a language-model tool call silently use a college model for NFL analysis',async()=>{
  expect(await executeFootballIntelligenceTool(ctx,'analyze_cfb_game',{gameId:'cfb:SYNTHETIC'},'Analyze the Bills game.','NFL')).toMatchObject({status:'not_requested'});
  expect(await executeFootballIntelligenceTool(ctx,'analyze_cfb_game',{gameId:'cfb:SYNTHETIC'},'Explain the existing probability.','CFB')).toMatchObject({status:'not_requested'});expect(cfb.analyzeCollegeGame).not.toHaveBeenCalled();
 });
 it('uses only supported complete-game counts after an explicit analysis instruction and enforces the quota',async()=>{
  expect(await executeFootballIntelligenceTool(ctx,'analyze_cfb_game',{gameId:'cfb:SYNTHETIC',simulations:50000},'Simulate this college game.','CFB')).toMatchObject({probability:null,status:'insufficient_evidence'});expect(cfb.analyzeCollegeGame).toHaveBeenCalledWith('cfb:SYNTHETIC',50000,ctx);expect(quota.publicRateLimit).toHaveBeenCalledOnce();
  cfb.analyzeCollegeGame.mockClear();await expect(executeFootballIntelligenceTool(ctx,'analyze_cfb_game',{gameId:'cfb:SYNTHETIC',simulations:20000},'Simulate this college game.','CFB')).rejects.toThrow();expect(cfb.analyzeCollegeGame).not.toHaveBeenCalled();
 });
 it('retrieves saved college research under the verified owner and rejects caller-selected identities',async()=>{
  await executeFootballIntelligenceTool(ctx,'read_saved_cfb_research',{},'Show my college research.','CFB');expect(cfb.collegeSavedResearch).toHaveBeenCalledWith(ctx);
  await expect(executeFootballIntelligenceTool(ctx,'read_saved_cfb_research',{userId:'OTHER'},'Show saved research.','CFB')).rejects.toThrow();
 });
 it('keeps PropLine sportsbook references distinct from exact DraftKings Predictions contracts',async()=>{
  const result:any=await executeFootballIntelligenceTool(ctx,'read_nfl_sportsbook_references',{},'Read NFL sportsbook references.');expect(result).toMatchObject({dataFamily:'sportsbook_reference',status:'render_backend_required',items:[]});expect(result).not.toHaveProperty('draftKingsEquivalent');expect(result).not.toHaveProperty('contractProbability');
 });
});
