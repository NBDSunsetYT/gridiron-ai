import {readFileSync} from 'node:fs';
import {describe,it,expect} from 'vitest';

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
});
