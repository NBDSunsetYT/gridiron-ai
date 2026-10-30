import {test} from 'node:test';
import assert from 'node:assert/strict';
import {webEnvironment} from './start-web.mjs';
import program,{partial} from './railway.ts';
import {allowedSource,deploymentSelectors} from '../../scripts/deploy-railway.mjs';

const supplied={RAILWAY_PUBLIC_DOMAIN:'gridiron-test.up.railway.app',SUPABASE_URL:'https://synthetic.supabase.co',SUPABASE_PUBLISHABLE_KEY:'sb_publishable_SYNTHETIC_FIXTURE',SIMULATION_SERVICE_URL:'http://quant.railway.internal:8080',SIMULATION_SERVICE_TOKEN:'SYNTHETIC-TOKEN-ONLY-01234567890123456789'};
test('hosted boot derives the actual HTTPS origin and forces cloud storage even with inherited legacy configuration',()=>{
 const result=webEnvironment({...supplied,DATA_BACKEND:'sqlite',HOSTNAME:'127.0.0.1',PORT:'9274'});
 assert.equal(result.APP_URL,'https://gridiron-test.up.railway.app');assert.equal(result.DATA_BACKEND,'supabase');assert.equal(result.GRIDIRON_CLOUD_ONLY,'1');assert.equal(result.HOSTNAME,'0.0.0.0');assert.equal(result.PORT,'9274');
});
test('release boot rejects placeholders, insecure remote URLs, missing keys and absent stable engine token',()=>{
 for(const value of [{...supplied,APP_URL:'http://app.example.com'},{...supplied,APP_URL:'https://app.example.com'},{...supplied,APP_URL:'https://app.example'},{...supplied,APP_URL:'https://actual.app/a/path'},{...supplied,APP_URL:'https://localhost'},{...supplied,SUPABASE_PUBLISHABLE_KEY:'sb_secret_SYNTHETIC'},{...supplied,SUPABASE_PUBLISHABLE_KEY:''},{...supplied,SIMULATION_SERVICE_TOKEN:''},{...supplied,PORT:'99999'}])assert.throws(()=>webEnvironment(value));
 assert.throws(()=>webEnvironment({...supplied,APP_URL:undefined,RAILWAY_PUBLIC_DOMAIN:undefined}));
});
test('deployment authoring preserves secrets and unrelated services; only web has a public routing workflow',()=>{
 const config=program({projectName:'Existing owner project'});assert.equal(partial,'gridiron-pwa');assert.equal(config.name,'Existing owner project');assert.equal(config.resources.length,2);
 const [quant,web]=config.resources;assert.equal(quant.name,'quant');assert.equal(web.name,'web');assert.equal(quant.build.dockerfilePath,'deployment/railway/quant.Dockerfile');assert.equal(web.build.dockerfilePath,'deployment/railway/web.Dockerfile');assert.equal(quant.variables.SIMULATION_SERVICE_TOKEN.type,'preserve');assert.equal(web.variables.SUPABASE_PUBLISHABLE_KEY.type,'preserve');assert.equal(web.variables.GRIDIRON_CLOUD_ONLY.value,'1');assert.equal(web.deploy.healthcheckPath,'/api/health');assert.equal(quant.deploy.healthcheckPath,'/health');assert.equal(quant.networking,undefined);assert.equal(quant.volumeAttachments,undefined);
});
test('source staging excludes financial records, credentials, native signing material and runtime caches',()=>{
 for(const path of ['.env.local','data/gridiron.sqlite','deployment/railway/node_modules/railway/a.js','foo/token.p8','.next/server/index.js','ios/App/project','public/key.pem','docs/__pycache__/x.pyc'])assert.equal(allowedSource(path),false,path);
 for(const path of ['.env.example','deployment/railway/web.Dockerfile','public/ocr/eng.traineddata.gz','modeling/simulator.py'])assert.equal(allowedSource(path),true,path);
});
test('upload configuration fails before any login, creation or network write without exact owner selectors and authorization',()=>{
 assert.throws(()=>deploymentSelectors({}),/Explicit Railway/);
 const env={GRIDIRON_RAILWAY_PROJECT_ID:'10000000-0000-4000-8000-000000000001',GRIDIRON_RAILWAY_ENVIRONMENT_ID:'10000000-0000-4000-8000-000000000002',GRIDIRON_RAILWAY_WEB_SERVICE_ID:'10000000-0000-4000-8000-000000000003',GRIDIRON_RAILWAY_QUANT_SERVICE_ID:'10000000-0000-4000-8000-000000000004'};
 assert.throws(()=>deploymentSelectors(env),/authorization/);assert.throws(()=>deploymentSelectors({...env,RAILWAY_TOKEN:'SYNTHETIC',RAILWAY_API_TOKEN:'SYNTHETIC'}),/only one/);assert.equal(deploymentSelectors({...env,RAILWAY_TOKEN:'SYNTHETIC'}).web,env.GRIDIRON_RAILWAY_WEB_SERVICE_ID);
});
