import {describe,it,expect} from 'vitest';
import {contractUncertainty} from '../lib/uncertainty';
describe('Market-specific parameter uncertainty',()=>{
 it('does not attach a home-win interval to a player contract',()=>{const r=contractUncertainty({uncertainty:{modelInterval:[.6,.7]},contracts:[{id:'receiver',monteCarloSE:.01,monteCarloInterval95:[.4,.44]}]},'receiver');expect(r.modelInterval).toBeNull();expect(r.gameHomeWinParameterInterval).toEqual([.6,.7]);});
 it('preserves only the exact contract bootstrap interval',()=>{const r=contractUncertainty({uncertainty:{modelInterval:[.6,.7],parameterBootstrap:{contracts:{receiver:{parameterInterval95:[.2,.5]},other:{parameterInterval95:[.7,.9]}},replicates:20}}},'receiver');expect(r.modelInterval).toEqual([.2,.5]);});
});
