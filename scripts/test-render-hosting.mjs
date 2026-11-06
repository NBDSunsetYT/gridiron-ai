import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {prepareStandalone,standalonePaths} from './prepare-standalone.mjs';
import {webEnvironment} from './start-web.mjs';
test('Render web boot requires durable auth and never inherits worker execution',()=>{
 assert.throws(()=>webEnvironment({RENDER:'true'}),/SUPABASE_URL/);
 const v=webEnvironment({RENDER:'true',SUPABASE_URL:'https://example.supabase.co',SUPABASE_PUBLISHABLE_KEY:'public-fixture',RENDER_EXTERNAL_URL:'https://example.onrender.com',PORT:'10000',GRIDIRON_COMPUTE_ROLE:'worker',GRIDIRON_CLOUD_ONLY:'0'});
 assert.equal(v.GRIDIRON_COMPUTE_ROLE,'web');assert.equal(v.GRIDIRON_CLOUD_ONLY,'1');assert.equal(v.DATA_BACKEND,'supabase');assert.equal(v.GRIDIRON_WORKER_REQUEST_LIFETIME,'0');assert.equal(v.HOSTNAME,'0.0.0.0');assert.equal(v.PORT,'10000');assert.equal(v.APP_URL,'https://example.onrender.com');
 assert.throws(()=>webEnvironment({...v,APP_URL:'http://localhost:3000'}),/HTTPS/);
 assert.throws(()=>webEnvironment({PORT:'-1'}),/PORT/);
});
test('Standalone staging preserves static/PWA paths without copying local data',()=>{
 const root=mkdtempSync(join(tmpdir(),'gridiron-host-'));
 try{
  for(const p of ['.next-test/standalone','.next-test/static/chunks','public','data'])mkdirSync(join(root,p),{recursive:true});
  writeFileSync(join(root,'.next-test/standalone/server.js'),'server');writeFileSync(join(root,'.next-test/required-server-files.json'),JSON.stringify({config:{output:'standalone',distDir:'.next-test'}}));writeFileSync(join(root,'.next-test/static/chunks/app.js'),'asset');writeFileSync(join(root,'public/sw.js'),'service-worker');writeFileSync(join(root,'data/private.db'),'never copy');
  const p=prepareStandalone(root,'.next-test');assert.equal(readFileSync(join(p.bundle,'.next-test/static/chunks/app.js'),'utf8'),'asset');assert.equal(readFileSync(join(p.bundle,'public/sw.js'),'utf8'),'service-worker');assert.throws(()=>readFileSync(join(p.bundle,'data/private.db')));assert.throws(()=>standalonePaths(root,'../private'));
 }finally{rmSync(root,{recursive:true,force:true});}
});
