import {afterEach,describe,it,expect,vi} from 'vitest';
import {computeAllowed,assertComputeAllowed,deferWorker,finishDeferred} from '../lib/compute/policy';
afterEach(()=>vi.unstubAllEnvs());
describe('Hosting computation boundary',()=>{
 it('cannot be overridden on Vercel by worker flags',async()=>{vi.stubEnv('VERCEL','1');vi.stubEnv('GRIDIRON_COMPUTE_ROLE','worker');expect(computeAllowed()).toBe(false);expect(assertComputeAllowed).toThrow('controlled research worker');const work=vi.fn();deferWorker(work);await finishDeferred();expect(work).not.toHaveBeenCalled();});
 it('requires an explicit worker role in cloud-only mode',()=>{vi.stubEnv('VERCEL','');vi.stubEnv('GRIDIRON_CLOUD_ONLY','1');vi.stubEnv('GRIDIRON_COMPUTE_ROLE','web');expect(computeAllowed()).toBe(false);vi.stubEnv('GRIDIRON_COMPUTE_ROLE','worker');expect(computeAllowed()).toBe(true);});
 it('finishes locally deferred work without a Next request lifecycle',async()=>{vi.stubEnv('VERCEL','');vi.stubEnv('GRIDIRON_COMPUTE_ROLE','worker');const work=vi.fn(async()=>{});deferWorker(work);await finishDeferred();expect(work).toHaveBeenCalledTimes(1);});
});
