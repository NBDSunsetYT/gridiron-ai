import {describe,it,expect} from 'vitest';
import {ApiError} from '../lib/auth';
import {evidenceFailure} from '../lib/probability/failures';
import {samePropSelection} from '../lib/probability/market-identity';
import {thresholdProbability} from '../lib/probability/math';
describe('probability failure and identity audit',()=>{
 it('preserves capacity and already-running reasons rather than calling them insufficient evidence',()=>{expect(evidenceFailure(new ApiError('Daily capacity reached',429))).toMatchObject({state:'data_delayed',reasonCode:'compute_capacity_reached',retryable:true});expect(evidenceFailure(new ApiError('Already running',409))).toMatchObject({state:'simulation_running'});expect(evidenceFailure(new ApiError('Player has no historical cohort',422))).toMatchObject({reason:'Player has no historical cohort',retryable:false});});
 it('matches stable sport-independent provider identities and exact definitions, never player names or prices',()=>{const ref={eventId:'SYNTHETIC-EVENT',playerId:'espn:SYNTHETIC-1',playerName:'SYNTHETIC NAME',market:'player_rec_yds',side:'Over',threshold:'25.5',book:'draftkings'},row={...ref,player:{id:ref.playerId,name:'SYNTHETIC ALIAS'},book:{key:'draftkings'},americanOdds:200};expect(samePropSelection(row,ref)).toBe(true);for(const changed of[{eventId:'OTHER'},{playerId:'OTHER'},{market:'player_rush_yds'},{threshold:26.5},{book:'fanduel'},{side:'Under'},{playerId:null}])expect(samePropSelection(row,{...ref,...changed})).toBe(false);});
 it.each(['receivingYards','rushingYards','passingYards','receptions','touchdowns'])('calculates exact supported %s thresholds from N shared-game outcomes',()=>{const r=thresholdProbability([{value:1,count:3400},{value:2,count:6600}],10000,1.5,'over');expect(r.hits).toBe(6600);expect(r.rawProbability).toBe(.66);expect(r.monteCarloSE).toBeCloseTo(Math.sqrt(.66*.34/10000),12);expect(r.monteCarloInterval95[0]).toBeLessThan(.66);expect(r.monteCarloInterval95[1]).toBeGreaterThan(.66);});
});
