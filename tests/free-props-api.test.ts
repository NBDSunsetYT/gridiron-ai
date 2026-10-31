import{describe,it,expect,vi,beforeEach}from'vitest';
import {ApiError} from '../lib/auth';
const m=vi.hoisted(()=>({feed:vi.fn(),context:vi.fn(),save:vi.fn(),records:vi.fn(),rate:vi.fn()}));
vi.mock('../lib/free-props-service',()=>({freeProps:m.feed}));
vi.mock('../lib/cloud/context',()=>({ACCESS_COOKIE:'gridiron_access',REFRESH_COOKIE:'gridiron_refresh',cloudContext:m.context,requireCloudUser:(ctx:any)=>{if(!ctx.user)throw new ApiError('Sign in.',401);return ctx.user;},finishCloud:(_ctx:any,response:Response)=>response}));
vi.mock('../lib/cloud/store',()=>({saveRecord:m.save,records:m.records}));vi.mock('../lib/public-nfl/store',()=>({publicRateLimit:m.rate}));
import{GET}from'../app/api/nfl/free-props/route';
beforeEach(()=>{vi.clearAllMocks();m.context.mockResolvedValue({user:null});m.feed.mockResolvedValue({sport:'NFL',items:[],totalResults:0});});
describe('PropLine public/private access boundary',()=>{
 it('allows public market discovery without an app identity',async()=>{const response=await GET(new Request('http://localhost:3000/api/nfl/free-props?sport=NFL'));expect(response.status).toBe(200);expect(m.context).not.toHaveBeenCalled();expect(m.save).not.toHaveBeenCalled();expect(response.headers.get('cache-control')).toBe('no-store');});
 it('rejects guest history before querying private records',async()=>{const response=await GET(new Request('http://localhost:3000/api/nfl/free-props?history=1'));expect(response.status).toBe(401);expect(m.records).not.toHaveBeenCalled();expect(m.feed).not.toHaveBeenCalled();});
 it('cannot select another user in a history query',async()=>{const ctx={user:{id:'SYNTHETIC-OWNER'}};m.context.mockResolvedValue(ctx);m.records.mockResolvedValue([{data:{sport:'CFB',id:'SYNTHETIC-OWNED'}}]);const response=await GET(new Request('http://localhost:3000/api/nfl/free-props?history=1&userId=SYNTHETIC-OTHER'));expect(response.status).toBe(200);expect(m.records).toHaveBeenCalledWith(ctx,'research_records/propline_snapshot',{limit:5,entityKey:'NFL'});});
 it('rejects unsupported sport/page without provider requests',async()=>{for(const query of['sport=NBA','cursor=-1','cursor=1.2'])expect((await GET(new Request('http://localhost:3000/api/nfl/free-props?'+query))).status).toBe(400);expect(m.feed).not.toHaveBeenCalled();});
});
