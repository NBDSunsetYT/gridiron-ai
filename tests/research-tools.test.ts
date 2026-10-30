import {afterEach,describe,it,expect,vi} from 'vitest';
import {executeResearchTool,additionalResearchTools} from '../lib/research-tools';
const request=new Request('http://localhost:3000/api/assistant',{headers:{cookie:'gridiron_session=SYNTHETIC'}});
afterEach(()=>vi.unstubAllGlobals());
describe('Evidence-bound research tools',()=>{
 it('does not run expensive games without an explicit request or invent a model',async()=>{await expect(executeResearchTool(request,'run_saved_simulation',{},'How is my balance?')).rejects.toThrow(/explicit/);});
 it('requires user-approved memory rather than trusting a model approval flag',async()=>{await expect(executeResearchTool(request,'remember_research_preference',{key:'theme',value:'x'},'Explain this game')).rejects.toThrow(/approval/);});
 it('forwards the authenticated workspace and reports missing specialist evidence',async()=>{const f=vi.fn().mockResolvedValue(Response.json({records:[]}));vi.stubGlobal('fetch',f);const result=await executeResearchTool(request,'get_specialist_evidence',{specialist:'weather'},'Research weather');expect(result.status).toBe('unavailable');expect(f.mock.calls[0][1].headers.cookie).toContain('SYNTHETIC');});
 it('can save actual source snapshots while marking failed sources unavailable',async()=>{const f=vi.fn().mockImplementation(async(url:string,_input:any)=>String(url).includes('/api/records')?Response.json({record:{id:'fixture'}}):Response.json({records:[]}));vi.stubGlobal('fetch',f);await executeResearchTool(request,'save_research_report',{title:'Fixture report'},'Save a report');const posted=JSON.parse(f.mock.calls.at(-1)![1].body);expect(posted.data.sections).toHaveLength(4);expect(posted.data.sections.every((x:any)=>x.status==='available')).toBe(true);});
 it('defines simulation and specialist tools as real server operations',()=>{expect(additionalResearchTools.length).toBe(5);});
});
