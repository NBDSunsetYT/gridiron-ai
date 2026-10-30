import {readFileSync} from 'node:fs';
import {describe,it,expect} from 'vitest';

describe('Vercel release boundaries',()=>{
 it('uses the existing Next build and Hobby-compatible maximum without paid build or memory settings',()=>{
  const config=JSON.parse(readFileSync('vercel.json','utf8'));
  expect(config.framework).toBe('nextjs');expect(config.installCommand).toBe('npm ci');expect(config.buildCommand).toBe('npm run build');
  expect(config.functions['app/api/**/*.ts'].maxDuration).toBe(300);
  expect(config).not.toHaveProperty('builds');expect(config).not.toHaveProperty('env');expect(config).not.toHaveProperty('build');
  expect(config.functions['app/api/**/*.ts']).not.toHaveProperty('memory');
 });
 it('retains the actual research reports imported by the web app while excluding private local state and native/Python deployment sources',()=>{
  const ignores=readFileSync('.vercelignore','utf8').split('\n');
  for(const path of ['.env','.env.*','data/','backups/','artifacts/','node_modules/','.next*/','modeling/','ios/','native/','deployment/'])expect(ignores).toContain(path);
  for(const report of ['baseline-backtest','simulation-backtest','v4-model-benchmark']){expect(ignores).toContain(`!docs/reports/${report}.json`);expect(JSON.parse(readFileSync(`docs/reports/${report}.json`,'utf8'))).toBeTruthy();}
 });
});
