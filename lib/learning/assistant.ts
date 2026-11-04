import continuedAudit from '@/docs/reports/model-audit-v17-summary.json';
import {z} from 'zod';
import type {ChatCompletionTool} from 'openai/resources/chat/completions';
import {realityArchive,realityDetail} from './service';
import offlineReport from '@/docs/reports/v16-iterative-learning.json';
import {offlineExperimentEvidence} from './offline-evidence';
export const learningTools:ChatCompletionTool[]=[{type:'function',function:{name:'read_simulation_reality',description:'Retrieve actual frozen NFL/CFB simulations versus verified final scores/player statistics, performance and learning journals. Historical reruns must not be described as prospective accuracy. Never invent learning progress or causal diagnoses.',parameters:{type:'object',properties:{sport:{type:'string',enum:['NFL','CFB']},comparisonId:{type:'string'},gameId:{type:'string'}},additionalProperties:false}}}];
export async function executeLearningTool(args:unknown){const p=z.object({sport:z.enum(['NFL','CFB']).default('NFL'),comparisonId:z.string().regex(/^[a-f0-9]{64}$/).optional(),gameId:z.string().max(120).optional()}).strict().parse(args);if(p.comparisonId){const d=await realityDetail(p.comparisonId);if(d.record.sport!==p.sport)return{error:'The requested archive belongs to a different sport.'};return d;}return realityArchive(p.sport,{gameId:p.gameId});}
learningTools.push({type:'function',function:{name:'read_model_experiments',description:'Read actual archived NFL/CFB/NBA challenger decisions, locked final-test metrics and stopping conditions. Distinguish retrospective research, raw probability reliability and production promotion. A better score average alone is not a validated improvement. This read-only tool starts no training.',parameters:{type:'object',properties:{sport:{type:'string',enum:['NFL','CFB','NBA']}},additionalProperties:false}}});
export function executeOfflineLearningTool(args:unknown){return {...offlineExperimentEvidence(offlineReport,args),continuedAudit};}
