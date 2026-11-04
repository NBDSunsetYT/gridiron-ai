import {afterEach,describe,it,expect} from 'vitest';
import {NextRequest} from 'next/server';
import {middleware} from '../middleware';
const original=process.env.GRIDIRON_CLOUD_ONLY;
afterEach(()=>{if(original===undefined)delete process.env.GRIDIRON_CLOUD_ONLY;else process.env.GRIDIRON_CLOUD_ONLY=original;});
describe('production learning route security boundary',()=>{
 it('keeps public research on its typed read-only handler in forced cloud mode',()=>{process.env.GRIDIRON_CLOUD_ONLY='1';const r=middleware(new NextRequest('https://example.com/api/learning?sport=CFB'));expect(r.headers.get('x-middleware-next')).toBe('1');expect(r.headers.has('x-middleware-rewrite')).toBe(false);});
 it('continues routing financial and conversation APIs to the authenticated owner backend',()=>{process.env.GRIDIRON_CLOUD_ONLY='1';for(const path of ['ledger','bets','conversations','preferences']){const r=middleware(new NextRequest('https://example.com/api/'+path,{headers:{cookie:'gridiron_backend=sqlite'}}));expect(new URL(r.headers.get('x-middleware-rewrite')!).pathname).toBe('/api/cloud/'+path);}});
});
