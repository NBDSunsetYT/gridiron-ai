import {afterEach,describe,expect,it,vi} from 'vitest';
import {cloudInjuryPayload,simulationService} from '../lib/cloud/simulations';
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
describe('Cloud simulation evidence and statistical transport',()=>{
 it('replays a saved injury mixture without forwarding its old recipe or accepting an arbitrary submitted mixture',async()=>{
  const input={action:'simulate',home:'SYNTH-A',injuryMixture:{playerId:'synthetic',scenarios:[{status:'active',weight:.6},{status:'inactive',weight:.4}]}};
  const payload=cloudInjuryPayload(input,'synthetic','inactive');expect(payload).not.toHaveProperty('injuryMixture');expect(payload.scenario).toEqual({playerId:'synthetic',status:'inactive'});expect(input.injuryMixture.scenarios).toHaveLength(2);
  expect(()=>cloudInjuryPayload({...input,injuryMixture:{...input.injuryMixture,scenarios:[{status:'active',weight:.8}]}},'synthetic','active')).toThrow(/recipe is invalid/);
  vi.stubEnv('SIMULATION_SERVICE_URL','http://private.test:8000');vi.stubEnv('SIMULATION_SERVICE_TOKEN','SYNTHETIC-PRIVATE-SERVICE-KEY-0123456789');const transport=vi.fn();vi.stubGlobal('fetch',transport);await expect(simulationService('simulate',input)).rejects.toThrow(/replay metadata/);expect(transport).not.toHaveBeenCalled();
 });
 it('keeps replay reproducible while using distinct deterministic random streams for availability strata',()=>{
  const input={action:'simulate',seed:2026,injuryEntityKeys:['synthetic-player'],model:{sha256:'synthetic-historical-version'},home:'DAL',away:'SEA'};
  const scenarios=['active','limited','inactive'].map(status=>cloudInjuryPayload(input,'synthetic-player',status));
  expect(new Set(scenarios.map(s=>s.seed)).size).toBe(3);expect(scenarios.every(s=>Number.isSafeInteger(s.seed)&&s.seed>=0&&s.seed<2**48)).toBe(true);
  expect(cloudInjuryPayload(input,'synthetic-player','active')).toEqual(scenarios[0]);expect(input.seed).toBe(2026);expect(input.injuryEntityKeys).toEqual(['synthetic-player']);
  expect(scenarios[0]).toMatchObject({home:'DAL',away:'SEA',scenario:{playerId:'synthetic-player',status:'active'}});expect(scenarios[0]).not.toHaveProperty('injuryEntityKeys');expect(scenarios[0]).not.toHaveProperty('action');
 });
 it('excludes application-only injury references from all private engine requests while keeping statistical assumptions',async()=>{
  vi.stubEnv('SIMULATION_SERVICE_URL','http://private.test:8000');vi.stubEnv('SIMULATION_SERVICE_TOKEN','SYNTHETIC-PRIVATE-SERVICE-KEY-0123456789');
  const transport=vi.fn(async(_url:any,init:any)=>{const value=JSON.parse(init.body);expect(value).not.toHaveProperty('injuryEntityKeys');expect(value).toMatchObject({simulations:10000,scenario:{playerId:'synthetic',status:'inactive'}});return Response.json({simulations:10000});});vi.stubGlobal('fetch',transport);
  expect(await simulationService('simulate',{simulations:10000,injuryEntityKeys:[],scenario:{playerId:'synthetic',status:'inactive'}})).toEqual({simulations:10000});expect(transport).toHaveBeenCalledOnce();
 });
 it('rejects malformed audit references before calling the statistical service',async()=>{
  vi.stubEnv('SIMULATION_SERVICE_URL','http://private.test:8000');vi.stubEnv('SIMULATION_SERVICE_TOKEN','SYNTHETIC-PRIVATE-SERVICE-KEY-0123456789');const transport=vi.fn();vi.stubGlobal('fetch',transport);
  await expect(simulationService('simulate',{simulations:10000,injuryEntityKeys:[{forged:'object'}]})).rejects.toThrow(/Injury references/);expect(transport).not.toHaveBeenCalled();
 });
});
