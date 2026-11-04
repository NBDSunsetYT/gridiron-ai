/** Operator-only real historical acceptance. No HTTP mutation route or secret output. */
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {EnvHttpProxyAgent,setGlobalDispatcher} from 'undici';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {gzipSync} from 'node:zlib';
if(process.env.HTTPS_PROXY)setGlobalDispatcher(new EnvHttpProxyAgent());
async function main(){
 const input=process.argv[2];if(!input)throw Error('A locally generated real historical audit file is required.');const f=JSON.parse(readFileSync(input,'utf8'));if(f.retrospective!==true)throw Error('This acceptance script is only for clearly labeled historical experiments.');
 const{captureSimulation,learningPayload,learningRecord}=await import('../lib/learning/store'),{compareFrozenForecast,refreshFootballLearning,refreshLearningPerformance,realityArchive,realityDetail}=await import('../lib/learning/service');
 // Preserve exact numeric JSON bytes from the Python artifact. No pickle or
 // executable model format is used; validate public-only fields before packing.
 const canonical=execFileSync('python',['-c',"import json,sys;sys.stdout.buffer.write(json.dumps(json.load(open(sys.argv[1])),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())",input.replace(/\.json$/,'.input.json')],{maxBuffer:5_000_000}),inputSha=createHash('sha256').update(canonical).digest('hex');
 if(inputSha!==f.result.runManifest?.inputArtifactSha256)throw Error('The fitted artifact does not match the frozen manifest.');
 const {researchDocument}=await import('../lib/storage/schema');researchDocument(f.game.sport,f.game.id,'model_artifact',{model:JSON.parse(canonical.toString())});
 const archivePayload={schemaVersion:1,encoding:'gzip-base64-canonical-json-v1',sha256:inputSha,rawBytes:canonical.length,modelVersion:f.modelVersion,body:gzipSync(canonical,{level:6}).toString('base64')},reference=await(await import('../lib/storage/research')).saveSharedResearch(f.game.sport,f.game.id,'model_artifact',archivePayload);
 const {putCache}=await import('../lib/public-nfl/store');await putCache('analysis','gafie-replay:'+inputSha,{verified:true,reference,sha256:inputSha,rawBytes:canonical.length,encoding:archivePayload.encoding},inputSha,86400000);
 if(f.research?.gafieCandidate){const c=f.research.gafieCandidate;await(await import('../lib/learning/store')).appendLearning('candidate',f.game,f.modelVersion,c.artifactId,c,{title:'Original GAFIE full-game candidate',status:'experimental_unpromoted',productionEligible:false,trainingGames:c.trainingGames.length,holdoutGames:c.holdoutGames.length,message:'Play-selection validation is separate from full-game forecasting accuracy.'});}
 const started=Date.now(),row=await captureSimulation(f.game,{id:f.analysisId,createdAt:f.predictedAt,inputVersion:f.inputVersion,result:f.result,research:f.research},{retrospective:true});if(row.mode!=='retrospective')throw Error('A historical replay was incorrectly classified.');
 const reopened=await learningPayload<any>((await learningRecord(row.id))!);if(reopened.inputVersion!==f.inputVersion||reopened.result.simulations!==f.result.simulations)throw Error('Persistent forecast failed read-back.');
 const comparison=await compareFrozenForecast(row),d:any=await realityDetail(comparison.row.id);if(d.data.simulations!==f.result.simulations||d.data.mode!=='retrospective'||!d.data.players.length)throw Error('Final comparison failed.');
 const retry=await compareFrozenForecast(row);if(retry.row.id!==comparison.row.id||retry.created)throw Error('Idempotent reconciliation created duplicate history.');
 const background=await refreshFootballLearning();await refreshLearningPerformance(f.game.sport);const archive=await realityArchive(f.game.sport),report={checkedAt:new Date().toISOString(),gameId:f.game.id,sport:f.game.sport,mode:row.mode,forecastId:row.id,evaluationId:comparison.row.id,simulations:d.data.simulations,players:d.data.players.length,pendingPlayerStatistics:d.data.pendingPlayerStatistics,predicted:{home:d.data.home.mean,away:d.data.away.mean},actual:{home:d.data.home.actual,away:d.data.away.actual},errors:{home:d.data.home.absoluteError,away:d.data.away.absoluteError,total:d.data.total.absoluteError,margin:d.data.margin.absoluteError},persistentReadBack:true,idempotentRetry:true,sourceCount:d.data.sources.length,sourceUrls:d.data.sources.map((s:any)=>s.url),prospectiveGames:archive.performance?.overall?.games??null,retrospectiveGames:archive.performance?.retrospectiveGames??null,background,status:'passed',seconds:(Date.now()-started)/1000,claim:'Mechanical persistence and historical comparison only; no prospective accuracy or model superiority claim.'};
 mkdirSync('docs/reports',{recursive:true});writeFileSync('docs/reports/reality-'+(String(f.modelVersion).includes('gafie')?'gafie-':'')+String(f.game.sport).toLowerCase()+'-historical-production.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}
main().catch(e=>{console.error(e instanceof Error?e.message:'Historical acceptance failed.');process.exitCode=1;});
