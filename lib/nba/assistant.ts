import {z} from 'zod';
import type {ChatCompletionTool} from 'openai/resources/chat/completions';
import type {CloudContext} from '../cloud/context';
import {records,record} from '../cloud/store';
import {sharedCache} from '../public-nfl/store';
import {readResearchObject,isResearchPointer} from '../public-nfl/objects';
import {nbaSchedule,nbaMarkets} from './service';

export const nbaTools:ChatCompletionTool[]=[{type:'function',function:{name:'read_nba_research',description:'Retrieve actual NBA schedules, verified PropLine sportsbook-reference quotes, or the authenticated user’s saved NBA simulations. NBA is a separate possession/rotation model. Explain only stored results; distinguish raw probability, Monte Carlo noise, unverified lineup/injury assumptions and uncalibrated models. Never invent statistics or imply DraftKings Predictions equivalence.',parameters:{type:'object',properties:{view:{type:'string',enum:['games','markets','saved','analysis']},analysisId:{type:'string'},playerId:{type:'string'}},required:['view'],additionalProperties:false}}}];
export async function executeNBATool(ctx:CloudContext,args:unknown){
 const p=z.object({view:z.enum(['games','markets','saved','analysis']),analysisId:z.string().max(80).optional(),playerId:z.string().regex(/^nba:espn:\d+$/).optional()}).strict().parse(args);
 if(p.view==='games')return nbaSchedule();
 if(p.view==='markets'){const v=await nbaMarkets();return{...v,items:v.items?.slice(0,20),scope:'First20 verified provider rows; no fabricated complete-board claim.'};}
 if(p.view==='saved')return{records:(await records(ctx,'research_records/saved_nba_simulation',{limit:20})).map(r=>({id:r.id,game:r.data.game,modelVersion:r.data.modelVersion,createdAt:r.created_at})),actualWagers:false};
 if(!p.analysisId)return{error:'Choose an actual saved NBA analysis ID first.'};
 let analysis:any;
 if(/^[a-f0-9]{64}$/.test(p.analysisId))analysis=(await sharedCache('analysis','nba-run:'+p.analysisId))?.data;
 else if(z.string().uuid().safeParse(p.analysisId).success){const r=await record(ctx,p.analysisId,'research_records/saved_nba_simulation');if(isResearchPointer(r.data.reference))analysis=await readResearchObject(r.data.reference);}
 if(!analysis?.result||analysis.result.sport!=='NBA')return{error:'No matching stored NBA simulation. No new simulation was started.'};
 const result=analysis.result,players=p.playerId?{[p.playerId]:result.players[p.playerId]??null}:Object.fromEntries(Object.entries(result.players??{}).slice(0,12));
 return{game:analysis.game,modelVersion:result.modelVersion,createdAt:analysis.createdAt,evidenceCutoff:result.evidenceCutoff,simulations:result.simulations,scoreDistributions:result.scoreDistributions,rawHomeWinProbability:result.homeWinProbability,calibratedProbability:result.calibratedProbability,quality:result.quality,uncertainty:result.uncertainty,players:Object.fromEntries(Object.entries(players).map(([id,stats]:any)=>[id,{name:result.playerNames?.[id],statistics:stats?Object.fromEntries(Object.entries(stats).map(([s,d]:any)=>[s,{mean:d.mean,median:d.median,interval90:d.interval90}])):null}])),sources:analysis.sourceVersions,limitations:result.limitations};
}
