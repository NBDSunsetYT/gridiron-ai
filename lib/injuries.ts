import {createHash,randomUUID} from 'node:crypto';
import {z} from 'zod';
import {getDb} from './db';
import {ApiError} from './auth';
import {wilson} from './model';
import {queueInjuryResimulation} from './jobs';
const officialHosts=['nfl.com','buffalobills.com','miamidolphins.com','patriots.com','newyorkjets.com','baltimoreravens.com','bengals.com','clevelandbrowns.com','steelers.com','houstontexans.com','texans.com','colts.com','jaguars.com','tennesseetitans.com','denverbroncos.com','chiefs.com','raiders.com','chargers.com','dallascowboys.com','giants.com','philadelphiaeagles.com','commanders.com','chicagobears.com','detroitlions.com','packers.com','vikings.com','atlantafalcons.com','panthers.com','neworleanssaints.com','buccaneers.com','azcardinals.com','therams.com','49ers.com','seahawks.com'];
export function authoritativeUrl(url:string){try{const parsed=new URL(url);return parsed.protocol==='https:'&&officialHosts.some(h=>parsed.hostname===h||parsed.hostname.endsWith('.'+h));}catch{return false;}}
const cohortSchema=z.object({active:z.number().int().nonnegative(),limited:z.number().int().nonnegative(),out:z.number().int().nonnegative(),sourceUrl:z.string().url(),description:z.string().min(20).max(3000),asOf:z.string().datetime({offset:true})});
export const injurySchema=z.object({entityKey:z.string().min(2).max(180),player:z.string().min(3).max(120),team:z.string().min(2).max(100),status:z.enum(['healthy','questionable','doubtful','out','injured_reserve','suspended','limited','full','did_not_participate','unknown']),publicationAt:z.string().datetime({offset:true}),checkedAt:z.string().datetime({offset:true}),sourceUrl:z.string().url(),sourceName:z.string().min(3).max(200),sourceType:z.enum(['official','licensed']).default('official'),verified:z.literal(true),note:z.string().max(4000).default(''),cohorts:cohortSchema.optional()});
export type InjuryInput=z.infer<typeof injurySchema>;
export function availabilityScenario(input:Pick<InjuryInput,'status'|'cohorts'>){
  if(['out','injured_reserve','suspended'].includes(input.status))return{active:0,limited:0,out:1,basis:'Recorded official designation, subject to subsequent report changes.',sampleSize:null,uncertainty:null};
  const c=input.cohorts;
  if(!c||c.active+c.limited+c.out<20)return null;
  const n=c.active+c.limited+c.out;
  return{active:c.active/n,limited:c.limited/n,out:c.out/n,sampleSize:n,basis:'Empirical frequencies from the user-supplied comparable historical cohort; not independently verified.',uncertainty:{active:wilson(c.active,n),limited:wilson(c.limited,n),out:wilson(c.out,n)}};
}
export function readInjuries(userId:string){
  const rows=getDb().prepare('SELECT data FROM injury_history WHERE user_id=? ORDER BY created_at DESC,rowid DESC').all(userId) as {data:string}[];
  const history=rows.map(r=>JSON.parse(r.data));const seen=new Set<string>();
  const records=history.filter(r=>{if(seen.has(r.entityKey))return false;seen.add(r.entityKey);return true;}).map(r=>({...r,stale:Date.now()-Date.parse(r.checkedAt)>24*3600000||Date.now()-Date.parse(r.publicationAt)>72*3600000}));
  return{records,history,sources:[{name:'Official NFL / team reports',status:'manual_verification',message:'Records are user-verified citations. This application has not fetched or independently verified the report content.'}],policy:'No injury-driven multipliers are invented. Uncertain status has no numerical availability probability without a documented cohort of at least 20 comparable historical outcomes.'};
}
export function saveInjury(userId:string,input:unknown){
  const raw=injurySchema.parse(input),p={...raw,publicationAt:new Date(raw.publicationAt).toISOString(),checkedAt:new Date(raw.checkedAt).toISOString()},now=new Date().toISOString();
  if(p.sourceType==='official'&&!authoritativeUrl(p.sourceUrl))throw new ApiError('An official report requires an HTTPS NFL or official team source URL. Use licensed with an explicit authorized provider citation where appropriate.');
  if(Date.parse(p.publicationAt)>Date.parse(p.checkedAt)||Date.parse(p.checkedAt)>Date.now()+60000)throw new ApiError('Publication must be no later than the checked time; checked time cannot be in the future.');
  if(p.cohorts&&Date.parse(p.cohorts.asOf)>Date.parse(p.checkedAt))throw new ApiError('Historical cohort evidence cannot be newer than the checked time.');
  if(p.cohorts&&p.cohorts.active+p.cohorts.limited+p.cohorts.out<20)throw new ApiError('At least 20 comparable cohort outcomes are required to assign uncertain availability weights.');
  const factsHash=createHash('sha256').update(JSON.stringify({status:p.status,note:p.note,cohorts:p.cohorts??null})).digest('hex');
  const record={...p,id:randomUUID(),factsHash,availability:availabilityScenario(p),verification:'manual_user_attested',createdAt:now};
  const db=getDb();return db.transaction(()=>{
    const prevRow=db.prepare('SELECT data FROM injury_history WHERE user_id=? AND entity_key=? ORDER BY created_at DESC,rowid DESC LIMIT 1').get(userId,p.entityKey) as {data:string}|undefined;
    const previous=prevRow?JSON.parse(prevRow.data):null;
    if(previous&&Date.parse(p.checkedAt)<Date.parse(previous.checkedAt))throw new ApiError('A new current report cannot have a checked time earlier than the current record. Historical reports belong in a separate evidence import.');
    db.prepare('INSERT INTO injury_history(id,user_id,entity_key,data,source,observed_at,created_at) VALUES(?,?,?,?,?,?,?)').run(record.id,userId,p.entityKey,JSON.stringify(record),p.sourceUrl,p.checkedAt,now);
    const affected:string[]=[];
    if(!previous||previous.factsHash!==factsHash){
      const predictions=db.prepare('SELECT id,data FROM prediction_snapshots WHERE user_id=? ORDER BY created_at DESC,rowid DESC').all(userId) as {id:string;data:string}[];
      const queuedContracts=new Set<string>();
      for(const r of predictions){const pred=JSON.parse(r.data);if(!(pred.injuryEntityKeys??[]).includes(p.entityKey)||Date.parse(pred.eventStart??'')<=Date.now()||queuedContracts.has(pred.contractId))continue;
        queuedContracts.add(pred.contractId);
        affected.push(r.id);
        const notice={id:randomUUID(),type:'prediction_stale',predictionId:r.id,injuryRecordId:record.id,previousInjuryId:previous?.id??null,entityKey:p.entityKey,reason:'Referenced injury evidence changed; resimulation is required before relying on this prediction.',createdAt:now,delivery:'in_app_only'};
        db.prepare('INSERT INTO notification_history(id,user_id,data,created_at) VALUES(?,?,?,?)').run(notice.id,userId,JSON.stringify(notice),now);
        queueInjuryResimulation(userId,{...pred,id:r.id},record);
      }
    }
    return{record,affectedPredictionIds:affected,resimulationRequired:affected.length};
  })();
}
