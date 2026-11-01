import {describe,it,expect,vi,beforeEach} from 'vitest';
const m=vi.hoisted(()=>({feed:vi.fn(),joint:vi.fn(),cap:vi.fn()}));
vi.mock('../lib/free-props-service',()=>({freeProps:m.feed}));vi.mock('../lib/probability/joint',()=>({alignedJoint:m.joint}));vi.mock('../lib/probability/capacity',()=>({probabilityCapacity:m.cap}));
import {automaticCombination} from '../lib/probability/automatic-combinations';
const row:any={eventId:'SYNTHETIC',player:{id:'SYNTHETIC'},market:'receiving_yards',side:'Over',threshold:'10.5',book:{key:'SYNTHETIC'},state:'ready',method:'empirical_history',empiricalProbability:.6,modelGameId:'SYNTHETIC',inputVersion:'SYNTHETIC'};
const ref={eventId:row.eventId,playerId:row.player.id,playerName:'SYNTHETIC',market:row.market,side:row.side,threshold:row.threshold,book:row.book.key};
const target:any={type:'combination',sport:'NFL',legs:[{type:'prop',sport:'NFL',cursor:0,reference:ref},{type:'prop',sport:'NFL',cursor:0,reference:{...ref,threshold:'20.5'}}]};
beforeEach(()=>{vi.clearAllMocks();m.feed.mockResolvedValue({items:[row,{...row,threshold:'20.5'}]});m.cap.mockResolvedValue({used:500000,backgroundLimit:300000});});
describe('automatic unsent research combinations',()=>{
 it('retrieves every exact leg, but never multiplies empirical marginals into a joint probability',async()=>{const r=await automaticCombination(target);expect(r.legs).toHaveLength(2);expect(r.rawProbability).toBeNull();expect(r.status).toBe('pending');expect(m.joint).not.toHaveBeenCalled();expect(r.evidenceKey).toHaveLength(64);});
 it('does not consume the reserved on-demand compute allowance for automatic joint research',async()=>{m.feed.mockResolvedValue({items:[{...row,method:'full_game_simulation',modelProbability:.6},{...row,method:'full_game_simulation',threshold:'20.5',modelProbability:.4}]});const r=await automaticCombination(target);expect(r.rawProbability).toBeNull();expect(r.reason).toMatch(/capacity/);expect(m.joint).not.toHaveBeenCalled();});
 it('withholds a mismatched threshold rather than selecting another available line',async()=>{m.feed.mockResolvedValue({items:[row]});const r=await automaticCombination(target);expect(r.legs[1].status).toBe('pending');expect(r.rawProbability).toBeNull();});
});
