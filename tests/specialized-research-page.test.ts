import {afterEach,describe,expect,it,vi} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
vi.mock('next/navigation',()=>({notFound:()=>{throw Error('research_disabled_404');}}));
import Page from '../app/research/v24/models/page';
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
describe('Frozen specialized research dashboard',()=>{
 it('stays unavailable without the explicit research flag',async()=>{vi.stubEnv('GRIDIRON_RESEARCH_V24','');await expect(Page({searchParams:Promise.resolve({})})).rejects.toThrow('research_disabled_404');});
 it('renders measured league results without network, private accounts or compute calls',async()=>{vi.stubEnv('GRIDIRON_RESEARCH_V24','1');const transport=vi.fn();vi.stubGlobal('fetch',transport);const html=renderToStaticMarkup(await Page({searchParams:Promise.resolve({sport:'NBA'})}));expect(html).toContain('rebounds');expect(html).toContain('No production model promotion');expect(html).toContain('not qualified');expect(html).toContain('not verified historical prop lines');expect(transport).not.toHaveBeenCalled();});
});
