import{afterEach,beforeEach,describe,expect,it,vi}from'vitest';
const m=vi.hoisted(()=>({ctx:vi.fn(),rpc:vi.fn(),rate:vi.fn()}));
vi.mock('../lib/cloud/context',async()=>({...await vi.importActual<any>('../lib/cloud/context'),cloudContext:m.ctx}));vi.mock('../lib/public-nfl/store',()=>({publicRateLimit:m.rate}));
import{POST}from'../app/api/nfl/workspaces/route';import{blankWorkspace}from'../lib/workspaces/schema';
const p={id:'20000000-0000-4000-8000-000000000001',mutationId:'30000000-0000-4000-8000-000000000001',expectedRevision:0,kind:'combination',sport:'NFL',data:blankWorkspace()};
const request=(body:unknown,origin='https://example.invalid')=>new Request('https://example.invalid/api/nfl/workspaces',{method:'POST',headers:{Origin:origin,'Content-Type':'application/json'},body:JSON.stringify(body)});
beforeEach(()=>{vi.clearAllMocks();vi.stubEnv('APP_URL','https://example.invalid');m.ctx.mockResolvedValue({user:{id:'SYNTHETIC-OWNER'},client:{rpc:m.rpc},cookies:[]});m.rpc.mockResolvedValue({data:{id:p.id,revision:1,updated_at:new Date().toISOString()},error:null});});afterEach(()=>vi.unstubAllEnvs());
describe('Authenticated versioned workspace HTTP boundary',()=>{
 it('requires app identity before any persistence call',async()=>{m.ctx.mockResolvedValue({user:null,cookies:[]});const r=await POST(request(p));expect(r.status).toBe(401);expect(m.rpc).not.toHaveBeenCalled();});
 it('rejects cross-origin writes and caller-supplied ownership',async()=>{expect((await POST(request(p,'https://other.example.invalid'))).status).toBe(403);expect((await POST(request({...p,user_id:'SYNTHETIC-OTHER'}))).status).toBe(400);expect(m.rpc).not.toHaveBeenCalled();});
 it('maps real revision conflicts to409 without claiming a save',async()=>{m.rpc.mockResolvedValue({data:null,error:{code:'40001'}});const r=await POST(request(p));expect(r.status).toBe(409);expect(await r.json()).not.toHaveProperty('record');});
 it('returns a backend-confirmed receipt with private no-store caching',async()=>{const r=await POST(request(p));expect(r.status).toBe(200);expect(r.headers.get('Cache-Control')).toBe('private, no-store');expect(m.rpc).toHaveBeenCalledWith('gridiron_save_workspace',{p});expect((await r.json()).record.revision).toBe(1);});
});
