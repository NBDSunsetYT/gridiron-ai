import {createHash} from 'node:crypto';
import {ApiError} from '../auth';
import type {CollegeGame,CollegeTeam,CollegeSource,CollegeConference,CollegeProvider,CollegeCoverage} from './types';

const ESPN='https://site.api.espn.com/apis/site/v2/sports/football/college-football';
export const collegeHash=(value:unknown)=>createHash('sha256').update(typeof value==='string'?value:JSON.stringify(value)).digest('hex');
export function collegeSource(id:string,name:string,url:string,at:string,version:string,status:CollegeSource['status']='available',note?:string):CollegeSource{return{id,name,url,collectedAt:at,publishedAt:null,availableAt:at,version,status,...note?{note}:{}};}
export async function collegeJson(url:string,maxBytes=5_000_000,timeout=15000,headers:Record<string,string>={}){
 const parsed=new URL(url);if(parsed.protocol!=='https:'||parsed.username||parsed.password)throw new ApiError('A secure published college-football source is required.',503);
 let response:Response;try{response=await fetch(parsed,{headers:{Accept:'application/json',...headers},redirect:'error',cache:'no-store',signal:AbortSignal.timeout(timeout)});}catch{throw new ApiError('The college-football source is temporarily unavailable.',503);}
 if(!response.ok)throw new ApiError(response.status===429?'The college-football source is temporarily rate limited.':'The college-football source could not be verified.',response.status===429?429:503);
 if(Number(response.headers.get('content-length')??0)>maxBytes)throw new ApiError('The college-football source exceeds its safe response bound.',413);
 const reader=response.body?.getReader();if(!reader)throw new ApiError('The college-football source returned no readable data.',503);
 const chunks:Uint8Array[]=[];let bytes=0;for(;;){const{done,value}=await reader.read();if(done)break;bytes+=value.byteLength;if(bytes>maxBytes){await reader.cancel();throw new ApiError('The college-football source exceeds its safe response bound.',413);}chunks.push(value);}
 const raw=Buffer.concat(chunks).toString('utf8');try{return{value:JSON.parse(raw),version:collegeHash(raw)}}catch{throw new ApiError('The college-football source returned an unsupported response.',503);}
}
const integer=(value:unknown,min:number,max:number):number|null=>{const n=typeof value==='number'?value:typeof value==='string'&&/^\d+$/.test(value)?Number(value):NaN;return Number.isInteger(n)&&n>=min&&n<=max?n:null;};
const text=(value:unknown,max=180)=>typeof value==='string'&&value.trim()&&value.length<=max?value.trim():null;
export function collegeEventId(id:string){if(!/^cfb:espn:\d{6,12}$/.test(id))throw new ApiError('Choose a verified college-football game.',400);return id.slice('cfb:espn:'.length);}
function conferencesFrom(data:any){const found=new Map<string,CollegeConference>();const visit=(v:any)=>{if(!v||typeof v!=='object')return;if(Array.isArray(v)){v.forEach(visit);return;}if(/^\d+$/.test(String(v.id??''))&&text(v.name??v.displayName))found.set(String(v.id),{id:'cfb:espn-conference:'+v.id,name:text(v.name??v.displayName)});for(const key of ['groups','children','conferences'])if(v[key])visit(v[key]);};visit(data.groups);return found;}
export function normalizeCollegeSchedule(data:any,url:string,checkedAt:string,version:string){
 if(!data||!Array.isArray(data.events))throw new ApiError('Published college-football schedule fields are unavailable.',503);
 const source=collegeSource('espn-cfb-schedule','ESPN published college-football schedule',url,checkedAt,version,'available','Published scoreboard identities, schedules and scores only. ESPN probabilities and sportsbook odds are not used as independent forecasts. Logo licensing is not assumed.');
 const conferences=conferencesFrom(data),games:CollegeGame[]=[],seen=new Set<string>();
 for(const event of data.events){
  const competition=event.competitions?.find((c:any)=>String(c.id)===String(event.id))??event.competitions?.[0],competitors=competition?.competitors;
  const rawId=String(event.id??''),startTime=typeof event.date==='string'?new Date(event.date):null,season=integer(event.season?.year,2000,2100),week=integer(event.week?.number??data.week?.number,1,30);
  if(!/^\d{6,12}$/.test(rawId)||seen.has(rawId)||!startTime||!Number.isFinite(startTime.getTime())||season===null||!Array.isArray(competitors))continue;
  const statusValue=event.status??competition.status,statusType=statusValue?.type,status=statusType?.completed===true||statusType?.state==='post'?'final':statusType?.state==='in'?'live':'scheduled';
  const team=(side:string):CollegeTeam|null=>{const entry=competitors.find((c:any)=>c.homeAway===side),t=entry?.team,id=String(t?.id??''),name=text(t?.displayName),abbreviation=text(t?.abbreviation,20);if(!/^\d{1,12}$/.test(id)||!name||!abbreviation)return null;
   const confId=/^\d+$/.test(String(t.conferenceId??''))?String(t.conferenceId):null;
   return{id:'cfb:espn:'+id,providerId:id,espnId:id,name,abbreviation,score:status==='scheduled'?null:integer(entry.score,0,200),ranking:integer(entry.curatedRank?.current,1,25),conference:confId?conferences.get(confId)??{id:'cfb:espn-conference:'+confId,name:null}:null,classification:'unknown',record:text(entry.records?.find((r:any)=>r.type==='total')?.summary,40)};
  };
  const home=team('home'),away=team('away');if(!home||!away||home.id===away.id)continue;
  games.push({id:'cfb:espn:'+rawId,sport:'CFB',espnId:rawId,providerIds:{espn:rawId},season,week,startTime:startTime.toISOString(),kickoffVerified:competition.timeValid===true&&competition.dateValid!==false,status,statusMessage:text(statusType?.detail??statusType?.description,300)??'Published schedule',home,away,venue:text(competition.venue?.fullName,250),neutralSite:typeof competition.neutralSite==='boolean'?competition.neutralSite:null,conferenceGame:typeof competition.conferenceCompetition==='boolean'?competition.conferenceCompetition:null,sources:[source]});seen.add(rawId);
 }
 games.sort((a,b)=>Date.parse(a.startTime)-Date.parse(b.startTime));return{games,sources:[source],updatedAt:checkedAt,conferences:[...new Map(games.flatMap(g=>[g.home.conference,g.away.conference]).filter((v):v is CollegeConference=>v!==null).map(v=>[v.id,v])).values()],inputVersion:version};
}
const schedules=new Map<string,{expires:number;value:ReturnType<typeof normalizeCollegeSchedule>}>(),pending=new Map<string,Promise<ReturnType<typeof normalizeCollegeSchedule>>>();
export async function fetchCollegeSchedule(date?:string){
 const day=date??new Date().toISOString().slice(0,10),parsed=new Date(day+'T12:00:00Z');if(!/^20\d{2}-\d{2}-\d{2}$/.test(day)||!Number.isFinite(parsed.getTime())||parsed.toISOString().slice(0,10)!==day)throw new ApiError('Choose a valid college-football date.');
 const key=date?'date:'+day:'current',cached=schedules.get(key);if(cached&&cached.expires>Date.now())return cached.value;const active=pending.get(key);if(active)return active;
 const task=(async()=>{try{
  const url=ESPN+'/scoreboard?groups=80&limit=200'+(date?'&dates='+day.replaceAll('-',''):''),read=await collegeJson(url),first=normalizeCollegeSchedule(read.value,url,new Date().toISOString(),read.version);
  const season=integer(read.value.events?.[0]?.season?.year??read.value.leagues?.[0]?.season?.year,2000,2100),week=integer(read.value.week?.number,1,29),seasonType=integer(read.value.events?.[0]?.season?.type??read.value.leagues?.[0]?.season?.type?.id,1,4);
  let value=first;
  if(season!==null&&week!==null&&seasonType!==null){
   const nextUrl=ESPN+'/scoreboard?groups=80&limit=200&dates='+season+'&week='+(week+1)+'&seasontype='+seasonType;
   try{const upcoming=await collegeJson(nextUrl),next=normalizeCollegeSchedule(upcoming.value,nextUrl,new Date().toISOString(),upcoming.version),all=[...new Map([...first.games,...next.games].map(g=>[g.id,g])).values()].sort((a,b)=>Date.parse(a.startTime)-Date.parse(b.startTime));value={games:all,sources:[...first.sources,...next.sources],conferences:[...new Map([...first.conferences,...next.conferences].map(c=>[c.id,c])).values()],updatedAt:next.updatedAt,inputVersion:collegeHash([first.inputVersion,next.inputVersion])};}
   catch{value={...first,sources:[...first.sources,collegeSource('espn-cfb-upcoming','ESPN upcoming college-football schedule',nextUrl,new Date().toISOString(),'unavailable','unavailable','The next published week could not be verified; current-week games remain available.')]};}
  }
  if(schedules.size>=8&&!schedules.has(key))schedules.delete(schedules.keys().next().value!);schedules.set(key,{expires:Date.now()+60000,value});return value;
 }finally{pending.delete(key);}})();pending.set(key,task);return task;
}
export async function fetchCollegeGame(id:string){
 const event=collegeEventId(id),schedule=await fetchCollegeSchedule().catch(()=>null),found=schedule?.games.find(game=>game.id===id);if(found)return found;
 const url=ESPN+'/summary?event='+event,read=await collegeJson(url),header=read.value?.header;if(String(header?.id)!==event)throw new ApiError('The published college-football event identity could not be verified.',404);
 const normalized=normalizeCollegeSchedule({events:[header]},url,new Date().toISOString(),read.version);if(!normalized.games.length)throw new ApiError('The published college-football game is unavailable.',404);return normalized.games[0];
}
export function unavailableCollegeCoverage(message:string,sources:CollegeSource[]=[]):CollegeCoverage{return{status:'unavailable',items:[],checkedAt:new Date().toISOString(),message,sources};}
export function collegeProviders():CollegeProvider[]{const configured=Boolean(process.env.GRIDIRON_RENDER_DATA_URL&&process.env.GRIDIRON_DATA_BRIDGE_TOKEN);return[{provider:'ESPN published scoreboard',status:'available',configured:true,checkedAt:new Date().toISOString(),message:'Published college schedules and scores; access is checked for each refresh.',sourceUrl:ESPN+'/scoreboard'},{provider:'CollegeFootballData',status:configured?'partial':'not_configured',configured,checkedAt:new Date().toISOString(),message:configured?'The private Render data bridge must independently verify licensed college-football coverage.':'The private college-football data bridge is not configured. No licensed statistics or injuries are fabricated.',sourceUrl:'https://collegefootballdata.com'},{provider:'DraftKings Predictions',status:'not_configured',configured:false,checkedAt:new Date().toISOString(),message:'No authorized college-football event-contract feed is configured. Sportsbook odds are not substituted for percentage-priced contracts.',sourceUrl:'https://predictions.draftkings.com/en'}];}
