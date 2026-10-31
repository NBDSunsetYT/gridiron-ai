import {beforeEach,afterEach,describe,it,expect,vi} from 'vitest';
const memory=vi.hoisted(()=>({rows:new Map<string,any>()}));
vi.mock('../lib/cloud/store',async()=>{const{decodeCloudData}=await import('../lib/cloud/codec');const{ApiError}=await import('../lib/auth');return{
 saveRecord:vi.fn(async(ctx:any,kind:string,data:any,options:any)=>{const row={id:options.id,user_id:ctx.user.id,kind,data:structuredClone(data),created_at:new Date().toISOString()};memory.rows.set(row.id,row);return row;}),
 record:vi.fn(async(ctx:any,id:string,kind:string)=>{const row=memory.rows.get(id);if(!row||row.user_id!==ctx.user.id||row.kind!==kind)throw new ApiError('Not found',404);return{...row,data:decodeCloudData(row.data)};}),
 records:vi.fn(async(ctx:any,kind:string)=>Array.from(memory.rows.values()).filter(r=>r.user_id===ctx.user.id&&r.kind===kind).map(r=>({...r,data:decodeCloudData(r.data)}))),
 unwrap:(rows:any[])=>rows.map(r=>r.data),
};});
const game:any={id:'cfb:espn:401999999',sport:'CFB',startTime:'2099-11-07T17:00:00Z',home:{id:'cfb:espn:254',name:'SYNTHETIC HOME'},away:{id:'cfb:espn:252',name:'SYNTHETIC AWAY'}};
const analysis:any={id:'SYNTHETIC-PUBLIC-ID',gameId:game.id,sport:'CFB',status:'completed',simulations:10000,modelVersion:'cfb-SYNTHETIC',inputVersion:'SYNTHETIC-INPUT',createdAt:'2026-10-31T00:00:00Z',updatedAt:'2026-10-31T00:00:00Z',result:{sport:'CFB',homeWinProbability:.5},research:{playerCatalog:[{id:'cfb:espn:1',name:'SYNTHETIC PLAYER'}]},stale:false};
const owner=(id:string)=>({user:{id}} as any);
beforeEach(()=>{memory.rows.clear();vi.stubEnv('SIMULATION_SERVICE_TOKEN','SYNTHETIC-CFB-ATTESTATION-TOKEN-FOR-LOCAL-UNIT-TESTS-ONLY');});
afterEach(()=>vi.unstubAllEnvs());
describe('Owned college result provenance',()=>{
 it('persists distinct owned identifiers for the same real result and verifies the entire source context',async()=>{const store=await import('../lib/college-football/store'),a=await store.saveCollegeAnalysis(owner('SYNTHETIC-A'),analysis,game),b=await store.saveCollegeAnalysis(owner('SYNTHETIC-B'),analysis,game);expect(a.id).not.toBe(b.id);expect(((await store.collegeOwnedAnalysis(owner('SYNTHETIC-A'),a.id)).analysis as any).research.playerCatalog[0].name).toBe('SYNTHETIC PLAYER');expect((await store.collegeSavedAnalyses(owner('SYNTHETIC-A')))).toHaveLength(1);await expect(store.collegeOwnedAnalysis(owner('SYNTHETIC-B'),a.id)).rejects.toThrow('Not found');});
 it('withholds numeric edits and player/source identity edits without changing the original record',async()=>{const store=await import('../lib/college-football/store'),ctx=owner('SYNTHETIC-A'),saved=await store.saveCollegeAnalysis(ctx,analysis,game),row=memory.rows.get(saved.id);row.data.research.playerCatalog[0].name='SYNTHETIC ALTERED NAME';await expect(store.collegeSavedAnalyses(ctx)).rejects.toThrow('authenticated');expect(memory.rows.has(saved.id)).toBe(true);});
 it('makes repeated saves idempotent and refuses unverified imported evidence',async()=>{const store=await import('../lib/college-football/store'),ctx=owner('SYNTHETIC-A'),saved=await store.saveCollegeAnalysis(ctx,analysis,game);expect((await store.saveCollegeAnalysis(ctx,analysis,game)).duplicate).toBe(true);expect(memory.rows.size).toBe(2);const row=memory.rows.get(saved.id);delete row.data.evidenceProof;await expect(store.collegeOwnedAnalysis(ctx,saved.id)).rejects.toThrow('server attestation');});
});
