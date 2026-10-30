import {contractUncertainty} from './uncertainty';
import Decimal from 'decimal.js';
import { randomUUID,createHash } from 'node:crypto';
import { z } from 'zod';
import { getDb } from './db';
import { ApiError } from './auth';
import { wilson } from './model';

const money=z.string().regex(/^\d{1,6}(\.\d{1,4})?$/,'Use an exact nonnegative decimal cents string.');
const price=money.refine(v=>new Decimal(v).gt(0)&&new Decimal(v).lt(100),'Contract prices must be between 0 and 100 cents.');
const settlementDefinitionSchema=z.object({kind:z.enum(['player','spread','total','team_total','home_win']),home:z.string().min(1).max(100),away:z.string().min(1).max(100),playerId:z.string().min(1).max(180).optional(),stat:z.enum(['passingAttempts','completions','passingYards','passingTouchdowns','interceptions','targets','receptions','receivingYards','receivingTouchdowns','carries','rushingYards','rushingTouchdowns','touchdowns']).optional(),team:z.enum(['home','away']).optional(),threshold:z.number().finite(),direction:z.enum(['over','under']),equality:z.enum(['yes','no'])}).superRefine((d,c)=>{if(d.kind==='player'&&(!d.playerId||!d.stat))c.addIssue({code:'custom',message:'Player settlement requires exact playerId and stat.'});if(d.kind==='team_total'&&!d.team)c.addIssue({code:'custom',message:'Team total requires home or away team.'});if(d.home===d.away)c.addIssue({code:'custom',message:'Home and away teams must differ.'});});
export const quoteSchema=z.object({
  contractId:z.string().min(1).max(180),eventId:z.string().min(1).max(180),event:z.string().min(3).max(200),question:z.string().min(5).max(500),
  threshold:z.number().finite(),operator:z.enum(['gt','gte','lt','lte','eq']),eventStart:z.string().datetime({offset:true}),
  settlementRule:z.string().min(10).max(4000),rulesUrl:z.string().url(),yesAskCents:price,noAskCents:price,
  yesBidCents:price.optional(),noBidCents:price.optional(),liquidityContracts:z.number().int().nonnegative().nullable().default(null),
  quotedAt:z.string().datetime({offset:true}),sourceUrl:z.string().url(),verified:z.literal(true),
  entryFeeCents:money,winFeeCents:money,feeSource:z.string().min(3).max(1000),
  entryFeeRounding:z.enum(['none','up_to_cent']).default('none'),
  settlementDefinition:settlementDefinitionSchema.optional(),
});
export type ContractQuote=z.infer<typeof quoteSchema>&{id:string;source:'manual_verified';createdAt:string};
export function valueContract(quote:Pick<ContractQuote,'yesAskCents'|'noAskCents'|'entryFeeCents'|'winFeeCents'|'entryFeeRounding'>,yesProbability:number,side:'YES'|'NO',quantity:number) {
  if(!Number.isFinite(yesProbability)||yesProbability<=0||yesProbability>=1)throw new Error('Probability must be strictly between zero and one.');
  if(!Number.isInteger(quantity)||quantity<1||quantity>100000)throw new Error('Quantity must be an integer from 1 to 100,000.');
  const p=new Decimal(side==='YES'?yesProbability:1-yesProbability),ask=new Decimal(side==='YES'?quote.yesAskCents:quote.noAskCents);
  let entryFee=new Decimal(quote.entryFeeCents).mul(quantity);
  if(quote.entryFeeRounding==='up_to_cent')entryFee=entryFee.ceil();
  const winFee=new Decimal(quote.winFeeCents).mul(quantity),cost=ask.mul(quantity).add(entryFee),receipt=new Decimal(100).mul(quantity).sub(winFee);
  if(ask.lte(0)||ask.gte(100)||entryFee.lt(0)||winFee.lt(0)||receipt.lte(0))throw new Error('Invalid quote or fee terms.');
  const expected=receipt.mul(p).sub(cost);
  return {askCents:ask.toFixed(),entryFeeCents:entryFee.toFixed(),winFeeCents:winFee.toFixed(),costCents:cost.toFixed(),winNetProfitCents:receipt.sub(cost).toFixed(),lossNetProfitCents:cost.neg().toFixed(),expectedProfitCents:expected.toFixed(8),breakEvenProbability:cost.div(receipt).toNumber(),roi:expected.div(cost).toNumber(),probability:p.toNumber(),quantity,feeAssumption:'User-verified per-contract entry and winning-settlement fees. Actual exchange fee schedules must be checked.'};
}
export function validateQuote(input:unknown,now=new Date()):ContractQuote {
  const raw=quoteSchema.parse(input),q={...raw,quotedAt:new Date(raw.quotedAt).toISOString(),eventStart:new Date(raw.eventStart).toISOString()};
  if(Date.parse(q.quotedAt)>now.getTime()+60000)throw new ApiError('Quote timestamp cannot be in the future.');
  if(q.yesBidCents&&new Decimal(q.yesBidCents).gt(q.yesAskCents)||q.noBidCents&&new Decimal(q.noBidCents).gt(q.noAskCents))throw new ApiError('Bid cannot exceed ask for the same contract side.');
  if(new Decimal(q.winFeeCents).gte(100))throw new ApiError('Winning settlement fees must be less than the 100-cent payout.');
  if(q.settlementDefinition){const d=q.settlementDefinition;if(q.operator==='eq'||d.threshold!==q.threshold||d.direction!==(['gt','gte'].includes(q.operator)?'over':'under')||d.equality!==(['gte','lte'].includes(q.operator)?'yes':'no')||d.kind==='home_win'&&(d.threshold!==0||d.direction!=='over'))throw new ApiError('Structured settlement definition must agree with the quote threshold, operator and equality rule. Home-win uses home margin over zero.');}
  return {...q,id:randomUUID(),source:'manual_verified',createdAt:now.toISOString()};
}
export function saveQuote(userId:string,input:unknown){
  const quote=validateQuote(input);
  const existing=getDb().prepare('SELECT data FROM contract_quotes WHERE user_id=? AND contract_id=? LIMIT 1').get(userId,quote.contractId) as {data:string}|undefined;
  if(existing){const prev=JSON.parse(existing.data);for(const key of ['eventId','threshold','operator','eventStart','settlementRule'] as const)if(prev[key]!==quote[key])throw new ApiError('The same contract ID cannot change its event, threshold, operator or settlement rules. Use the exact new contract identifier.');}
  const definitions=(getDb().prepare('SELECT data FROM contract_quotes WHERE user_id=? AND contract_id=?').all(userId,quote.contractId) as {data:string}[]).map(r=>JSON.parse(r.data).settlementDefinition).filter(Boolean);
  if(definitions.some(d=>JSON.stringify(d)!==JSON.stringify(quote.settlementDefinition)))throw new ApiError('A contract’s established structured settlement definition is immutable. Use a new exact contract identifier for different participants or rules.');
  getDb().prepare('INSERT INTO contract_quotes(id,user_id,contract_id,data,quoted_at,created_at) VALUES(?,?,?,?,?,?)').run(quote.id,userId,quote.contractId,JSON.stringify(quote),quote.quotedAt,quote.createdAt);
  return quote;
}
function jsonRows(table:string,userId:string){
  // Table arguments are internal constants, never request text.
  return (getDb().prepare(`SELECT id,data,created_at FROM ${table} WHERE user_id=? ORDER BY created_at DESC,rowid DESC`).all(userId) as {id:string;data:string;created_at:string}[]).map(r=>({...JSON.parse(r.data),id:r.id,createdAt:r.created_at}));
}
export function contractHistory(userId:string){
  const quotes=jsonRows('contract_quotes',userId) as ContractQuote[],predictions=jsonRows('prediction_snapshots',userId),settlements=jsonRows('contract_settlements',userId),paperPositions=jsonRows('paper_positions',userId);
  const injuries=jsonRows('injury_history',userId);
  const annotated=predictions.filter(p=>p.kind==='binary_contract').map(p=>{
    const changed=injuryChanges(p.injuryVersions??[],injuries);
    const quote=quotes.find(q=>q.id===p.quoteId);
    return {...p,stale:!!p.stale||changed.length>0||!!quote&&Date.now()-Date.parse(quote.quotedAt)>120000,injuryChanges:changed.map(i=>i.id)};
  });
  const seen=new Set<string>(),contracts=quotes.filter(q=>{if(seen.has(q.contractId))return false;seen.add(q.contractId);return true;}).map(q=>({...q,stale:Date.now()-Date.parse(q.quotedAt)>120000,executable:false}));
  return {contracts,quotes,predictions:annotated,settlements,paperPositions:paperPositions.map(p=>{const settlement=settlements.find(s=>s.contractId===p.contractId);return{...p,status:settlement?'settled':'open',realizedProfitCents:settlement?(settlement.outcome===(p.side==='YES'?1:0)?p.valuation.winNetProfitCents:p.valuation.lossNetProfitCents):null};}),performance:performanceHistory(quotes,predictions,settlements),provider:{name:'DraftKings Predictions',status:'unavailable',message:'No authorized direct DraftKings Predictions API is configured. These are user-verified manual binary contract snapshots, not DraftKings sportsbook American odds. No order execution is available.'}};
}
export function injuryChanges(versions:{entityKey:string;factsHash:string}[],records:any[]){
  return versions.flatMap(v=>{const latest=records.filter(r=>r.entityKey===v.entityKey).sort((a,b)=>Date.parse(b.createdAt)-Date.parse(a.createdAt))[0];return latest&&latest.factsHash!==v.factsHash?[latest]:[];});
}
export function validateSimulationSettlement(quote:ContractQuote,contract:any,result:{home?:string;away?:string}){
  const d=quote.settlementDefinition,s=contract.settlement;
  if(!d)throw new ApiError('Generated forecasts require a structured settlementDefinition on the quote: exact kind, home/away teams, participant/statistic where applicable, threshold, direction and equality. Legacy quotes can still record explicitly supplied estimates.');
  if(!s||s.id!==quote.contractId||contract.id!==quote.contractId||d.kind!==s.kind||d.home!==result.home||d.away!==result.away||d.kind==='player'&&(d.playerId!==s.playerId||d.stat!==s.stat)||d.kind==='team_total'&&d.team!==s.team||d.equality!==s.equality||d.kind!=='home_win'&&(d.threshold!==s.threshold||d.direction!==s.direction)||contract.pushProbability!==0)throw new ApiError('Simulation settlement does not match the exact quoted market kind, teams, player/statistic, threshold, direction or equality rule. No generated forecast was attached.');
}
export function savePrediction(userId:string,input:any){
  const parsed=z.object({quoteId:z.string(),probability:z.number().gt(0).lt(1),side:z.enum(['YES','NO']),quantity:z.number().int().min(1).max(100000),asOf:z.string().datetime({offset:true}),inputsHash:z.string().min(8).max(200),modelVersion:z.string().min(3).max(200).default('supplied-estimate-v1'),supersedesPredictionId:z.string().optional(),injuryEntityKeys:z.array(z.string()).max(100).default([]),evidence:z.object({source:z.string().min(3).max(1000),method:z.string().min(3).max(2000),sampleSize:z.number().int().min(20),simulationId:z.string().optional(),outcomes:z.array(z.boolean()).min(20).max(100000).optional()})}).parse(input);
  parsed.asOf=new Date(parsed.asOf).toISOString();
  const row=getDb().prepare('SELECT data FROM contract_quotes WHERE id=? AND user_id=?').get(parsed.quoteId,userId) as {data:string}|undefined;
  if(!row)throw new ApiError('Contract quote not found.',404);
  const quote=JSON.parse(row.data) as ContractQuote,now=new Date().toISOString();
  if(parsed.supersedesPredictionId&&!getDb().prepare('SELECT id FROM prediction_snapshots WHERE id=? AND user_id=? AND entity_key=?').get(parsed.supersedesPredictionId,userId,quote.contractId))throw new ApiError('The superseded prediction must belong to this account and exact contract.');
  if(Date.parse(parsed.asOf)>=Date.parse(quote.eventStart)||Date.parse(parsed.asOf)>Date.now()+60000)throw new ApiError('A prediction must use information strictly before event start and cannot have a future as-of time.');
  if(Date.parse(quote.quotedAt)>Date.parse(parsed.asOf))throw new ApiError('Prediction cannot use a quote observed after its as-of time.');
  const injuryVersions=parsed.injuryEntityKeys.map(key=>{
    const injuryRow=getDb().prepare('SELECT data FROM injury_history WHERE user_id=? AND entity_key=? AND observed_at<=? ORDER BY observed_at DESC,created_at DESC,rowid DESC LIMIT 1').get(userId,key,parsed.asOf) as {data:string}|undefined;
    if(!injuryRow)throw new ApiError('A referenced injury entity has no report available by the prediction as-of time.');
    const injury=JSON.parse(injuryRow.data);return{entityKey:key,id:injury.id,factsHash:injury.factsHash,publicationAt:injury.publicationAt,checkedAt:injury.checkedAt,staleAtCapture:Date.parse(parsed.asOf)-Date.parse(injury.publicationAt)>72*3600000||Date.parse(parsed.asOf)-Date.parse(injury.checkedAt)>24*3600000};
  });
  let yesProbability=parsed.evidence.outcomes?(parsed.evidence.outcomes.filter(Boolean).length+.5)/(parsed.evidence.outcomes.length+1):parsed.probability;
  let sourceValidation=parsed.evidence.outcomes?'calculated_from_submitted_outcomes':'user_supplied_model_estimate_not_independently_verified';
  let probabilityUncertainty:Record<string,unknown>={modelInterval:null,method:'User-supplied external estimate; total uncertainty was not supplied or independently validated.'};
  if(parsed.evidence.outcomes){parsed.evidence.sampleSize=parsed.evidence.outcomes.length;probabilityUncertainty={samplingInterval:wilson(parsed.evidence.outcomes.filter(Boolean).length,parsed.evidence.outcomes.length),modelInterval:null,method:'Wilson sampling interval on user-supplied outcomes; total model uncertainty remains unestimated.'};}
  if(parsed.evidence.simulationId){
    const job=getDb().prepare('SELECT status,result,data,created_at FROM simulation_jobs WHERE user_id=? AND id=?').get(userId,parsed.evidence.simulationId) as {status:string;result:string|null;data:string;created_at:string}|undefined;
    if(!job||job.status!=='completed'||!job.result)throw new ApiError('A completed simulation belonging to this account is required.');
    const result=JSON.parse(job.result),contract=result.contracts?.find((c:any)=>c.id===quote.contractId);
    if(!contract)throw new ApiError('Simulation result has no exact matching contract identifier.');
    validateSimulationSettlement(quote,contract,result);
    if(!Number.isFinite(Date.parse(result.evidenceCutoff))||Date.parse(result.evidenceCutoff)>Date.parse(parsed.asOf)||Date.parse(job.created_at)>Date.parse(parsed.asOf)||Date.parse(result.eventStart)!==Date.parse(quote.eventStart))throw new ApiError('Simulation capture/evidence time and event start must agree with the prediction snapshot.');
    if(!Number.isFinite(contract.probability)||contract.probability<=0||contract.probability>=1)throw new ApiError('Simulation returned a boundary probability; insufficient tail evidence for finite-odds valuation.');
    yesProbability=contract.probability;sourceValidation='calculated_from_completed_simulation';
    if(!Number.isInteger(result.simulations)||result.simulations<1000||typeof result.modelVersion!=='string')throw new ApiError('Completed simulation provenance or sample count is invalid.');
    parsed.evidence.sampleSize=result.simulations;parsed.modelVersion=result.modelVersion;
    probabilityUncertainty=contractUncertainty(result,quote.contractId);
  }
  const auditStatus=Date.parse(now)<Date.parse(quote.eventStart)&&Date.parse(quote.createdAt)<Date.parse(quote.eventStart)&&Math.abs(Date.parse(now)-Date.parse(parsed.asOf))<=120000?'prospective':'retrospective_import';
  const computedInputsHash=createHash('sha256').update(JSON.stringify({quoteId:quote.id,evidence:parsed.evidence,injuryVersions,asOf:parsed.asOf,modelVersion:parsed.modelVersion})).digest('hex');
  const prediction={...parsed,id:randomUUID(),kind:'binary_contract',quoteId:quote.id,contractId:quote.contractId,eventStart:quote.eventStart,yesProbability,probability:parsed.side==='YES'?yesProbability:1-yesProbability,valuation:valueContract(quote,yesProbability,parsed.side,parsed.quantity),auditStatus,injuryVersions,computedInputsHash,sourceValidation,probabilityUncertainty,stale:Math.max(Date.parse(now),Date.parse(parsed.asOf))-Date.parse(quote.quotedAt)>120000||injuryVersions.some(v=>v.staleAtCapture),createdAt:now};
  getDb().prepare('INSERT INTO prediction_snapshots(id,user_id,entity_key,data,as_of,created_at) VALUES(?,?,?,?,?,?)').run(prediction.id,userId,quote.contractId,JSON.stringify(prediction),prediction.asOf,now);
  return prediction;
}
export function settleContract(userId:string,input:unknown){
  const p=z.object({contractId:z.string(),quoteId:z.string(),predictionId:z.string(),outcome:z.union([z.literal(0),z.literal(1)]),settledAt:z.string().datetime({offset:true}),sourceUrl:z.string().url(),verified:z.literal(true)}).parse(input);
  const db=getDb();return db.transaction(()=>{
    const predictionRow=db.prepare('SELECT data FROM prediction_snapshots WHERE id=? AND user_id=?').get(p.predictionId,userId) as {data:string}|undefined;
    if(!predictionRow)throw new ApiError('Prediction snapshot not found.',404);
    const pred=JSON.parse(predictionRow.data);
    if(pred.contractId!==p.contractId||pred.quoteId!==p.quoteId)throw new ApiError('Settlement must reference the same contract, quote and prediction snapshot.');
    if(Date.parse(p.settledAt)<Date.parse(pred.eventStart)||Date.parse(p.settledAt)>Date.now()+60000)throw new ApiError('Settlement must occur after event start and not in the future.');
    if((db.prepare('SELECT data FROM contract_settlements WHERE user_id=? AND contract_id=?').all(userId,p.contractId) as unknown[]).length)throw new ApiError('This contract already has an immutable settlement.');
    const settlement={...p,id:randomUUID(),createdAt:new Date().toISOString(),verification:'manual_user_verified'};
    db.prepare('INSERT INTO contract_settlements(id,user_id,contract_id,quote_id,prediction_id,data,settled_at,created_at) VALUES(?,?,?,?,?,?,?,?)').run(settlement.id,userId,p.contractId,p.quoteId,p.predictionId,JSON.stringify(settlement),p.settledAt,settlement.createdAt);return settlement;
  })();
}
export function savePaperPosition(userId:string,input:unknown){
  const {predictionId}=z.object({predictionId:z.string()}).parse(input);
  const row=getDb().prepare('SELECT data FROM prediction_snapshots WHERE user_id=? AND id=?').get(userId,predictionId) as {data:string}|undefined;
  if(!row)throw new ApiError('Prediction snapshot not found.',404);
  const pred=JSON.parse(row.data),now=new Date().toISOString();
  if(Date.parse(pred.eventStart)<=Date.now())throw new ApiError('Paper positions must be recorded before event start.');
  const position={id:randomUUID(),predictionId,contractId:pred.contractId,side:pred.side,quantity:pred.quantity,valuation:pred.valuation,recordedAt:now,pricing:'hypothetical_snapshot_price_not_verified_fill'};
  getDb().prepare('INSERT INTO paper_positions(id,user_id,entity_key,data,created_at,updated_at) VALUES(?,?,?,?,?,?)').run(position.id,userId,pred.contractId,JSON.stringify(position),now,now);return position;
}
export function performanceHistory(quotes:ContractQuote[],predictions:any[],settlements:any[]){
  const usable=predictions.filter(p=>p.kind==='binary_contract'&&p.auditStatus==='prospective'&&!p.stale).sort((a,b)=>Date.parse(a.createdAt)-Date.parse(b.createdAt));
  const evaluated:{id:string;contractId:string;p:number;y:number;benchmark:number;clv:number|null;modelVersion:string}[]=[],seen=new Set<string>();
  for(const pred of usable){
    if(seen.has(pred.contractId))continue;
    const outcome=settlements.find(s=>s.contractId===pred.contractId),entry=quotes.find(q=>q.id===pred.quoteId);
    if(!outcome||!entry)continue;
    seen.add(pred.contractId);
    const closing=quotes.filter(q=>q.contractId===pred.contractId&&Date.parse(q.quotedAt)<Date.parse(q.eventStart)&&Date.parse(q.createdAt)<Date.parse(q.eventStart)).sort((a,b)=>Date.parse(b.quotedAt)-Date.parse(a.quotedAt))[0];
    const benchmark=new Decimal(entry.yesAskCents).div(new Decimal(entry.yesAskCents).add(entry.noAskCents)).toNumber();
    const key=pred.side==='YES'?'yesAskCents':'noAskCents';
    evaluated.push({id:pred.id,contractId:pred.contractId,p:pred.yesProbability,y:outcome.outcome,benchmark,clv:closing&&closing.id!==entry.id?new Decimal(closing[key]).sub(entry[key]).toNumber():null,modelVersion:pred.modelVersion});
  }
  const n=evaluated.length,loss=(p:number,y:number)=>-(y*Math.log(Math.max(1e-12,p))+(1-y)*Math.log(Math.max(1e-12,1-p)));
  const calibration=Array.from({length:10},(_,i)=>{const rows=evaluated.filter(r=>Math.min(9,Math.floor(r.p*10))===i);return{bucket:`${i*10}–${(i+1)*10}%`,n:rows.length,predicted:rows.length?rows.reduce((s,r)=>s+r.p,0)/rows.length:null,observed:rows.length?rows.reduce((s,r)=>s+r.y,0)/rows.length:null,interval:rows.length?wilson(rows.reduce((s,r)=>s+r.y,0),rows.length):null};});
  const clv=evaluated.filter(r=>r.clv!==null);
  const byModelVersion=Array.from(new Set(evaluated.map(r=>r.modelVersion)),modelVersion=>{const rows=evaluated.filter(r=>r.modelVersion===modelVersion);return{modelVersion,n:rows.length,brier:rows.reduce((s,r)=>s+(r.p-r.y)**2,0)/rows.length,logLoss:rows.reduce((s,r)=>s+loss(r.p,r.y),0)/rows.length,benchmarkBrier:rows.reduce((s,r)=>s+(r.benchmark-r.y)**2,0)/rows.length};});
  return {n,brier:n?evaluated.reduce((s,r)=>s+(r.p-r.y)**2,0)/n:null,logLoss:n?evaluated.reduce((s,r)=>s+loss(r.p,r.y),0)/n:null,benchmarkBrier:n?evaluated.reduce((s,r)=>s+(r.benchmark-r.y)**2,0)/n:null,benchmarkLogLoss:n?evaluated.reduce((s,r)=>s+loss(r.benchmark,r.y),0)/n:null,calibration,byModelVersion,clv:clv.length?clv.reduce((s,r)=>s+r.clv!,0)/clv.length:null,clvN:clv.length,clvUnits:'cents per contract; manual snapshots, no verified execution',benchmark:'normalized contemporaneous YES/NO asks; not a friction-free executable probability',sampleWarning:n<30?'Insufficient evidence for a reliability claim. Fewer than 30 unique settled prospective contracts.':null,validationStatus:'User-verified outcomes and user-supplied evidence; not an independent audit or a league-wide calibration claim. Multiple contracts may share one event.',evaluated,excluded:predictions.length-n,policy:'First captured, nonstale prospective prediction per unique contract; retrospective imports, post-start captures and missing outcomes excluded.'};
}
