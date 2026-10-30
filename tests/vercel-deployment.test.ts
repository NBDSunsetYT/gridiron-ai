import {readFileSync} from 'node:fs';
import {describe,it,expect} from 'vitest';
import {NextRequest} from 'next/server';
import {config as middlewareConfig,middleware} from '../middleware';

describe('Vercel release boundaries',()=>{
 it('uses the existing Next build and Hobby-compatible maximum without paid build or memory settings',()=>{
  const config=JSON.parse(readFileSync('vercel.json','utf8'));
  expect(config.services.web.framework).toBe('nextjs');expect(config.services.web.installCommand).toBe('npm ci');expect(config.services.web.buildCommand).toBe('npm run build');
  expect(config.services.web.functions['app/api/**/*.ts'].maxDuration).toBe(300);
  expect(config).not.toHaveProperty('builds');expect(config).not.toHaveProperty('env');expect(config).not.toHaveProperty('build');
  expect(config).not.toHaveProperty('framework');expect(config).not.toHaveProperty('buildCommand');expect(config).not.toHaveProperty('functions');
  expect(config.services.web.functions['app/api/**/*.ts']).not.toHaveProperty('memory');
 });
 it('retains actual research reports and Python runtime while excluding private local state and native deployment sources',()=>{
  const ignores=readFileSync('.vercelignore','utf8').split('\n');
  for(const path of ['.env','.env.*','data/','backups/','artifacts/','node_modules/','.next*/','modeling/test_*.py','ios/','native/','deployment/'])expect(ignores).toContain(path);
  for(const report of ['baseline-backtest','simulation-backtest','v4-model-benchmark']){expect(ignores).toContain(`!docs/reports/${report}.json`);expect(JSON.parse(readFileSync(`docs/reports/${report}.json`,'utf8'))).toBeTruthy();}
 });
 it('keeps the original Python engine private and gives only the web service an authenticated internal binding',()=>{
  const config=JSON.parse(readFileSync('vercel.json','utf8'));
  expect(config.services.quant).toMatchObject({framework:'fastapi',entrypoint:'modeling.service:app'});
  expect(config.services.quant.functions['modeling/service.py'].maxDuration).toBe(300);
  expect(config.services.web.bindings).toEqual([{type:'service',service:'quant',format:'url',env:'SIMULATION_SERVICE_URL'}]);
  expect(config.rewrites).toEqual([{source:'/(.*)',destination:{service:'web'}}]);
  expect(readFileSync('requirements.txt','utf8')).toContain('-r modeling/requirements.txt');
  expect(readFileSync('.python-version','utf8').trim()).toBe('3.12');
 });
 it('uses Services-compatible Node middleware while retaining the owned cloud API rewrite and health bypass',()=>{
  expect(middlewareConfig.runtime).toBe('nodejs');
  const previous=process.env.GRIDIRON_CLOUD_ONLY;process.env.GRIDIRON_CLOUD_ONLY='1';
  try{
   const response=middleware(new NextRequest('https://gridiron.example/api/ledger'));
   expect(response.headers.get('x-middleware-rewrite')).toBe('https://gridiron.example/api/cloud/ledger');
   expect(middleware(new NextRequest('https://gridiron.example/api/health')).headers.get('x-middleware-rewrite')).toBeNull();
  }finally{if(previous===undefined)delete process.env.GRIDIRON_CLOUD_ONLY;else process.env.GRIDIRON_CLOUD_ONLY=previous;}
 });
});
