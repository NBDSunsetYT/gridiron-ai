import {describe,it,expect,vi} from 'vitest';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

function harness(){
 const listeners:Record<string,(event:any)=>void>={},stored=new Map<string,any>();
 const cache={addAll:vi.fn(async(paths:string[])=>{for(const path of paths)stored.set(path,{publicAsset:true});}),match:vi.fn(async(request:any)=>stored.get(typeof request==='string'?request:request.url)),put:vi.fn(async(request:any,response:any)=>{stored.set(request.url,response);})};
 const caches={open:vi.fn(async()=>cache),match:vi.fn(async(path:string)=>stored.get(path)),keys:vi.fn(async()=>['gridiron-interface-v2','gridiron-interface-v3','gridiron-interface-v5','gridiron-interface-v6','another-application']),delete:vi.fn(async()=>true)};
 const fetch=vi.fn(async(_request?:any,_options?:any)=>({ok:true,type:'basic',headers:new Headers({'Content-Type':'application/javascript','Cache-Control':'public, max-age=31536000, immutable'}),clone(){return this;}}));
 const self={location:{origin:'https://gridiron.example'},addEventListener:(name:string,fn:(event:any)=>void)=>listeners[name]=fn,skipWaiting:vi.fn(async()=>{}),clients:{claim:vi.fn(async()=>{})}};
 runInNewContext(readFileSync('public/sw.js','utf8'),{self,caches,fetch,URL,Response});
 const dispatch=(name:string,event:any={})=>{let result:Promise<any>|undefined;listeners[name]({...event,waitUntil:(promise:Promise<any>)=>result=promise,respondWith:(promise:Promise<any>)=>result=promise});return result;};
 const request=(path:string,options:Record<string,any>={})=>({url:new URL(path,'https://gridiron.example').toString(),method:'GET',mode:'cors',...options});
 return{cache,caches,fetch,self,stored,dispatch,request};
}

describe('Installable PWA and private-account cache boundary',()=>{
 it('provides correctly sized PNGs and a scoped standalone manifest',()=>{
  const manifest=JSON.parse(readFileSync('public/manifest.webmanifest','utf8'));expect(manifest).toMatchObject({display:'standalone',start_url:'/',scope:'/',id:'/'});
  for(const [file,size]of [['icon-192.png',192],['icon-512.png',512],['apple-touch-icon.png',180]] as const){const png=readFileSync('public/'+file);expect(png.subarray(1,4).toString()).toBe('PNG');expect(png.readUInt32BE(16)).toBe(size);expect(png.readUInt32BE(20)).toBe(size);}
 });
 it('precaches public installation/offline assets and removes only this app’s older caches',async()=>{
  const h=harness();await h.dispatch('install');const paths=h.cache.addAll.mock.calls[0][0];expect(paths).toContain('/apple-touch-icon.png');expect(paths).toContain('/offline.html');expect(paths).not.toContain('/');expect(paths.some(path=>path.startsWith('/api/'))).toBe(false);
  await h.dispatch('activate');expect(h.caches.delete).toHaveBeenCalledWith('gridiron-interface-v2');expect(h.caches.delete).not.toHaveBeenCalledWith('another-application');expect(h.caches.delete).toHaveBeenCalledWith('gridiron-interface-v3');expect(h.caches.delete).toHaveBeenCalledWith('gridiron-interface-v5');expect(h.caches.delete).not.toHaveBeenCalledWith('gridiron-interface-v6');
 });
 it('never intercepts private APIs, account mutations, cross-origin responses or sign-in pages',()=>{
  const h=harness();for(const request of [h.request('/api/ledger'),h.request('/api/cloud/conversations'),h.request('/signin'),h.request('/signout'),h.request('/icon.svg',{method:'POST'}),h.request('https://other.example/icon.svg')])expect(h.dispatch('fetch',{request})).toBeUndefined();expect(h.fetch).not.toHaveBeenCalled();expect(h.cache.put).not.toHaveBeenCalled();
 });
 it('uses the public offline shell on navigation failure without caching authenticated HTML',async()=>{
  const h=harness(),offline=new Response('PUBLIC OFFLINE INTERFACE');h.stored.set('/offline.html',offline);h.fetch.mockRejectedValueOnce(new TypeError('Offline'));
  expect(await h.dispatch('fetch',{request:h.request('/account-page',{mode:'navigate'})})).toBe(offline);expect(h.cache.put).not.toHaveBeenCalled();expect(h.fetch.mock.calls[0][1]).toMatchObject({cache:'no-store'});
 });
 it('caches public hashed scripts but rejects accidental HTML/private/no-store asset responses',async()=>{
  const h=harness();await h.dispatch('fetch',{request:h.request('/_next/static/public.js')});expect(h.cache.put).toHaveBeenCalledOnce();
  for(const headers of [{'Content-Type':'text/html'},{'Cache-Control':'private, max-age=60'},{'Cache-Control':'no-store'}] as Record<string,string>[]){h.fetch.mockResolvedValueOnce({ok:true,type:'basic',headers:new Headers(headers),clone(){return this;}});await h.dispatch('fetch',{request:h.request('/_next/static/not-public-'+Math.random()+'.js')});}
  expect(h.cache.put).toHaveBeenCalledOnce();
 });
 it('keeps successful online assets usable when device cache storage is full',async()=>{
  const h=harness();h.cache.put.mockRejectedValueOnce(new Error('QuotaExceededError'));const response=await h.dispatch('fetch',{request:h.request('/_next/static/online.js')});expect(response.ok).toBe(true);expect(h.fetch).toHaveBeenCalledOnce();
 });
});
