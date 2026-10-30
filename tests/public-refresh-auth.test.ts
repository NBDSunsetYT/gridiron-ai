import {afterEach,beforeEach,describe,it,expect,vi} from 'vitest';
import {createHmac} from 'node:crypto';
const state=vi.hoisted(()=>({used:new Set<string>()}));
vi.mock('../lib/public-nfl/store',()=>({sharedWrite:vi.fn(async(p:any)=>{if(state.used.has(p.key))return{allowed:false};state.used.add(p.key);return{allowed:true};})}));
import {signedRefreshAuthorized} from '../lib/public-nfl/refresh-auth';
import {sharedWrite} from '../lib/public-nfl/store';
const secret='SYNTHETIC-SIGNED-REFRESH-SECRET-01234567890123456789',nonce='10000000-0000-4000-8000-000000000001';
function signed(options:{timestamp?:string;signature?:string;nonce?:string;method?:string;signMethod?:string}={}){const timestamp=options.timestamp||String(Date.now()),id=options.nonce||nonce,signature=options.signature??createHmac('sha256',secret).update(`GRIDIRON-REFRESH-V1\n${timestamp}\n${id}\n${options.signMethod||'POST'}\n/api/nfl/refresh`).digest('hex');return new Request('https://app.example/api/nfl/refresh',{method:options.method||'POST',headers:{'X-Gridiron-Timestamp':timestamp,'X-Gridiron-Nonce':id,'X-Gridiron-Signature':signature}});}
beforeEach(()=>{vi.useFakeTimers({toFake:['Date']});vi.setSystemTime(new Date('2026-10-30T20:00:00Z'));vi.stubEnv('GRIDIRON_PUBLIC_INGEST_TOKEN',secret);state.used.clear();vi.clearAllMocks();});
afterEach(()=>{vi.useRealTimers();vi.unstubAllEnvs();});
describe('Credential-free queued refresh authentication',()=>{
 it('accepts a current request MAC once and records only a hashed one-use nonce',async()=>{const request=signed();expect(await signedRefreshAuthorized(request)).toBe(true);expect(await signedRefreshAuthorized(request)).toBe(false);const payload=vi.mocked(sharedWrite).mock.calls[0][0];expect(payload).toMatchObject({action:'rate_limit',limit:1,windowMs:120000});expect(JSON.stringify(payload)).not.toContain(secret);expect(JSON.stringify(payload)).not.toContain(nonce);});
 it('rejects expired/future requests and tampered signatures before any replay-table operation',async()=>{for(const timestamp of [String(Date.now()-60001),String(Date.now()+60001)])expect(await signedRefreshAuthorized(signed({timestamp}))).toBe(false);expect(await signedRefreshAuthorized(signed({signature:'0'.repeat(64)}))).toBe(false);expect(sharedWrite).not.toHaveBeenCalled();});
 it('binds the MAC to POST and the exact refresh endpoint contract',async()=>{expect(await signedRefreshAuthorized(signed({signMethod:'GET'}))).toBe(false);expect(await signedRefreshAuthorized(signed({method:'GET'}))).toBe(false);expect(sharedWrite).not.toHaveBeenCalled();});
 it('rejects malformed nonces, signatures and missing configuration',async()=>{expect(await signedRefreshAuthorized(signed({nonce:'not-a-uuid'}))).toBe(false);expect(await signedRefreshAuthorized(signed({signature:'not-hex'}))).toBe(false);vi.stubEnv('GRIDIRON_PUBLIC_INGEST_TOKEN','');expect(await signedRefreshAuthorized(signed())).toBe(false);expect(sharedWrite).not.toHaveBeenCalled();});
});
