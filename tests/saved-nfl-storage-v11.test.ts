import {describe,it,expect,vi} from 'vitest';
const source=vi.hoisted(()=>({job:null as any}));vi.mock('../lib/public-nfl/store',()=>({sharedJob:vi.fn(async()=>source.job)}));
import {savedNflReference,hydrateSavedNflData} from '../lib/storage/saved-nfl';
describe('private NFL saves use immutable shared references',()=>{
 it('reopens the exact saved result without copying it into the private record',async()=>{source.job={id:'SYNTHETIC-ID',game_id:'SYNTHETIC-GAME',status:'completed',result:{result:{simulations:10000,homeWinProbability:.6,representativeGames:[]},summary:{text:'SYNTHETIC research'}}};const data={publicAnalysisId:source.job.id,gameId:source.job.game_id,resultReference:savedNflReference(source.job)};expect(data).not.toHaveProperty('result');expect((await hydrateSavedNflData(data)).result).toEqual(source.job.result.result);source.job.result.result.homeWinProbability=.99;await expect(hydrateSavedNflData(data)).rejects.toThrow('integrity');});
 it('retains legacy inline records and rejects mismatched game references',async()=>{const legacy={result:{simulations:10000},notes:'SYNTHETIC legacy'};expect(await hydrateSavedNflData(legacy)).toBe(legacy);await expect(hydrateSavedNflData({publicAnalysisId:'A',gameId:'A',resultReference:{format:'shared-nfl-result-v1',analysisId:'B',gameId:'A',sha256:'a'.repeat(64)}})).rejects.toThrow('verified');});
});
