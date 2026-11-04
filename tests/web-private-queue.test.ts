import {afterEach,it,expect,vi} from 'vitest';
const store=vi.hoisted(()=>({saveRecord:vi.fn(async(..._args:any[])=>({})),updateRecord:vi.fn(),record:vi.fn(),records:vi.fn(async()=>[])}));
vi.mock('../lib/cloud/store',()=>({...store,unwrap:(rows:any[])=>rows.map(r=>r.data)}));
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();vi.clearAllMocks();});
it('preserves signed private inputs without a Vercel Python binding or any compute dispatch',async()=>{
 vi.stubEnv('VERCEL','1');vi.stubEnv('GRIDIRON_CLOUD_ONLY','1');vi.stubEnv('SIMULATION_SERVICE_URL','');vi.stubEnv('SIMULATION_SERVICE_TOKEN','SYNTHETIC-PRIVATE-SIGNING-SECRET-NEVER-PRODUCTION');
 const fetch=vi.fn();vi.stubGlobal('fetch',fetch);const ctx:any={user:{id:'00000000-0000-4000-a000-000000000001'},accessToken:'SYNTHETIC-OWNER-SESSION'};
 const {cloudRunSimulation,cloudSimulationHistory}=await import('../lib/cloud/simulations');const result=await cloudRunSimulation(ctx,{action:'fit',csv:'SYNTHETIC TRANSPORT ONLY',source:'SYNTHETIC',asOf:'2025-01-01'});
 expect(result).toMatchObject({status:'queued',pending:true,worker:{accepted:false,scheduled:false}});expect(store.saveRecord).toHaveBeenCalledTimes(2);expect(store.saveRecord.mock.calls[0][2]).toMatchObject({status:'queued',data:{execution:'background'}});expect(store.saveRecord.mock.calls[1][2]).toHaveProperty('inputProof');expect(fetch).not.toHaveBeenCalled();expect((await cloudSimulationHistory(ctx)).service).toMatchObject({configured:true,executionMode:'private_queue_only',workerExecutionVerified:false});
});
