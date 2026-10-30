import {createHash} from 'node:crypto';
import {gunzip as gunzipCallback} from 'node:zlib';
import {promisify} from 'node:util';
import {parseWarehouseCSV,easternKickoff,NFLVERSE_GAMES} from '../warehouse';
import {ApiError} from '../auth';
import type {PublicGame,ResearchSource,PublicCoverage,PublicInjury,PublicWeather} from './types';

const gunzip=promisify(gunzipCallback);
export const NFLVERSE_RELEASE='https://github.com/nflverse/nflverse-data/releases/download';
export const TEAM_NAMES:Record<string,string>={ARI:'Arizona Cardinals',ATL:'Atlanta Falcons',BAL:'Baltimore Ravens',BUF:'Buffalo Bills',CAR:'Carolina Panthers',CHI:'Chicago Bears',CIN:'Cincinnati Bengals',CLE:'Cleveland Browns',DAL:'Dallas Cowboys',DEN:'Denver Broncos',DET:'Detroit Lions',GB:'Green Bay Packers',HOU:'Houston Texans',IND:'Indianapolis Colts',JAX:'Jacksonville Jaguars',KC:'Kansas City Chiefs',LA:'Los Angeles Rams',LAR:'Los Angeles Rams',LAC:'Los Angeles Chargers',LV:'Las Vegas Raiders',MIA:'Miami Dolphins',MIN:'Minnesota Vikings',NE:'New England Patriots',NO:'New Orleans Saints',NYG:'New York Giants',NYJ:'New York Jets',PHI:'Philadelphia Eagles',PIT:'Pittsburgh Steelers',SEA:'Seattle Seahawks',SF:'San Francisco 49ers',TB:'Tampa Bay Buccaneers',TEN:'Tennessee Titans',WAS:'Washington Commanders'};
export function nflSeason(now=new Date()){return now.getUTCMonth()<2?now.getUTCFullYear()-1:now.getUTCFullYear();}
export function source(id:string,name:string,url:string,collectedAt:string,status:ResearchSource['status']='available',note?:string,version?:string):ResearchSource{return{id,name,url,collectedAt,publishedAt:null,status,...note?{note}:{},...version?{version}:{}};}
export function sha(value:unknown){return createHash('sha256').update(Buffer.isBuffer(value)?value:typeof value==='string'?value:JSON.stringify(value)).digest('hex');}
export async function boundedFetch(url:string,maxBytes=15_000_000,timeout=12000,method='GET'){
 const response=await fetch(url,{method,cache:'no-store',signal:AbortSignal.timeout(timeout),headers:{Accept:'application/json,text/csv,*/*'}});
 if(!response.ok)throw new ApiError('A published NFL source is temporarily unavailable.',502);
 if(Number(response.headers.get('content-length')||0)>maxBytes)throw new ApiError('The published source exceeds the safe ingestion bound.',413);
 if(method==='HEAD')return{body:Buffer.alloc(0),headers:response.headers};
 const reader=response.body?.getReader();if(!reader)throw new ApiError('The published source has no readable body.',502);
 const chunks:Uint8Array[]=[];let bytes=0;for(;;){const{done,value}=await reader.read();if(done)break;bytes+=value.byteLength;if(bytes>maxBytes){await reader.cancel();throw new ApiError('The published source exceeds the safe ingestion bound.',413);}chunks.push(value);}
 return{body:Buffer.concat(chunks),headers:response.headers};
}
export function normalizePublicSchedule(raw:string,checkedAt:string,season=nflSeason()):{games:PublicGame[];sources:ResearchSource[];updatedAt:string;inputVersion:string}{
 const rows=parseWarehouseCSV(raw);if(!rows.length||!['game_id','season','home_team','away_team','gameday','gametime'].every(key=>key in rows[0]))throw new ApiError('Published NFL schedule fields are missing.',502);
 const version=sha(raw),provenance=source('nflverse-schedule','nflverse NFL schedule',NFLVERSE_GAMES,checkedAt,'available','Kickoff times are converted from the source-documented America/New_York timezone. Historical line columns are not treated as live market prices.',version),games:PublicGame[]=[],seen=new Set<string>();
 for(const row of rows){
  if(Number(row.season)!==season||!/^\d{4}_\d{2,3}_[A-Z0-9]{2,3}_[A-Z0-9]{2,3}$/.test(row.game_id)||seen.has(row.game_id))continue;
  const kickoff=easternKickoff(row.gameday,row.gametime);if(!kickoff||!row.home_team||!row.away_team||row.home_team===row.away_team)continue;
  const number=(value:string)=>value!==''&&Number.isInteger(Number(value))&&Number(value)>=0?Number(value):null,homeScore=number(row.home_score),awayScore=number(row.away_score);
  // An elapsed kickoff alone is never evidence of a live score.
  const status=homeScore!==null&&awayScore!==null?'final':'scheduled';
  games.push({id:row.game_id,season,week:Number(row.week),startTime:kickoff,status,...status==='scheduled'&&Date.parse(kickoff)<=Date.parse(checkedAt)?{statusMessage:'Scheduled kickoff has passed; a live score has not been verified.'}:{},home:{id:row.home_team,abbreviation:row.home_team,name:TEAM_NAMES[row.home_team]||row.home_team,score:homeScore},away:{id:row.away_team,abbreviation:row.away_team,name:TEAM_NAMES[row.away_team]||row.away_team,score:awayScore},venue:row.stadium||null,roof:row.roof||null,surface:row.surface||null,espnId:/^\d+$/.test(row.espn||'')?row.espn:null,sources:[provenance]});seen.add(row.game_id);
 }
 if(!games.length)throw new ApiError('The published source has no valid games for this NFL season.',502);
 games.sort((a,b)=>Date.parse(a.startTime)-Date.parse(b.startTime));return{games,sources:[provenance],updatedAt:checkedAt,inputVersion:version};
}
export async function fetchPublicSchedule(){const result=await boundedFetch(NFLVERSE_GAMES);return normalizePublicSchedule(result.body.toString('utf8'),new Date().toISOString());}
export async function fetchInjuries(game:PublicGame):Promise<PublicCoverage<PublicInjury>>{
 const checkedAt=new Date().toISOString(),url=`${NFLVERSE_RELEASE}/injuries/injuries_${game.season}.csv.gz`;
 try{
  const fetched=await boundedFetch(url,3_000_000),raw=await gunzip(fetched.body,{maxOutputLength:15_000_000}),rows=parseWarehouseCSV(raw.toString('utf8'));
  if(!rows.length||!['team','week','report_status','practice_status','gsis_id'].every(key=>key in rows[0]))throw Error('Unsupported injury source fields');
  const s=source('nflverse-injuries','nflverse published NFL injury reports',url,checkedAt,'available','The dataset supplies report/practice designations but not an individual publication time. Missing designations do not establish unrestricted availability.',sha(raw));
  const items:PublicInjury[]=rows.filter(row=>Number(row.week)===game.week&&[game.home.id,game.away.id].includes(row.team)&&(row.report_status||row.practice_status)).map(row=>{const status=row.report_status||'Practice report only';return{id:row.gsis_id||sha([row.team,row.full_name]).slice(0,24),player:row.full_name||[row.first_name,row.last_name].filter(Boolean).join(' ')||'Name unavailable',team:row.team,position:row.position||null,status,availability:/questionable|doubtful/i.test(status)?'uncertain':'unknown',practiceParticipation:row.practice_status||null,sourceUrl:url,sourceName:s.name,publishedAt:null,checkedAt,officialConfirmed:false,note:[row.report_primary_injury,row.practice_primary_injury].filter(Boolean).join('; ')||undefined};});
  return{status:items.length?'available':'partial',items,checkedAt,message:items.length?'Published report and practice designations. Uncertain availability is retained; no active/inactive probability is invented.':'No matching report is published for this game week yet. This does not confirm a clean injury report.',sources:[s]};
 }catch{return{status:'unavailable',items:[],checkedAt,message:'The injury report could not be verified right now. No player availability is assumed.',sources:[source('nflverse-injuries','nflverse published NFL injury reports',url,checkedAt,'unavailable')]};}
}
const STATES:Record<string,string>={AZ:'Arizona',GA:'Georgia',MD:'Maryland',NY:'New York',NC:'North Carolina',IL:'Illinois',OH:'Ohio',TX:'Texas',CO:'Colorado',MI:'Michigan',WI:'Wisconsin',IN:'Indiana',FL:'Florida',MO:'Missouri',CA:'California',NV:'Nevada',MN:'Minnesota',MA:'Massachusetts',LA:'Louisiana',NJ:'New Jersey',PA:'Pennsylvania',WA:'Washington',TN:'Tennessee',VA:'Virginia'};
export async function fetchWeather(game:PublicGame):Promise<PublicWeather>{
 const checkedAt=new Date().toISOString(),unavailable=(message:string,sources:ResearchSource[]=[]):PublicWeather=>({status:'unavailable',checkedAt,message,sources});
 if(/dome|closed/i.test(game.roof||''))return{status:'partial',checkedAt,message:'The published stadium roof is indoors/closed. Outdoor forecast is not applied to the model.',sources:game.sources};
 if(!game.espnId)return unavailable('Stadium weather coverage is unavailable for this matchup.');
 const summaryUrl=`https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=${game.espnId}`;
 try{
  const fetched=await boundedFetch(summaryUrl,3_000_000,10000),data=JSON.parse(fetched.body.toString('utf8')),info=data.gameInfo,venue=info?.venue;
  const published=source('espn-game-weather','ESPN published game weather',summaryUrl,checkedAt,'partial','Reported game context; individual forecast publication time is not supplied. No sportsbook prices or ESPN model probabilities are imported.');
  if(data.header?.id!==game.espnId)throw Error('Event identity mismatch');
  const city=venue?.address?.city,state=venue?.address?.state,zip=venue?.address?.zipCode;
  if(typeof city==='string'&&city.length<100&&Date.parse(game.startTime)>Date.now()&&Date.parse(game.startTime)<Date.now()+15*86400000){
   try{
    const geocodeUrl=`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(city)}&count=10&language=en&format=json`,geo=JSON.parse((await boundedFetch(geocodeUrl,200000,6000)).body.toString('utf8'));
    const locations=(geo.results||[]).filter((r:any)=>r.country_code==='US'&&r.name?.toLowerCase()===city.toLowerCase()),location=locations.find((r:any)=>typeof zip==='string'&&r.postcodes?.includes(zip))||locations.find((r:any)=>STATES[state]&&r.admin1===STATES[state]);
    if(location&&Number.isFinite(location.latitude)&&Number.isFinite(location.longitude)){
     const weatherUrl=`https://api.open-meteo.com/v1/forecast?latitude=${location.latitude}&longitude=${location.longitude}&hourly=temperature_2m,wind_speed_10m,precipitation_probability&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=UTC&forecast_days=16`,forecast=JSON.parse((await boundedFetch(weatherUrl,300000,6000)).body.toString('utf8')),hours=forecast.hourly?.time;
     const target=Math.floor(Date.parse(game.startTime)/3600000)*3600000,index=Array.isArray(hours)?hours.findIndex((t:string)=>Date.parse(t+'Z')===target):-1;
     if(index>=0&&Number.isFinite(forecast.hourly.temperature_2m[index])&&Number.isFinite(forecast.hourly.wind_speed_10m[index]))return{status:'available',temperatureF:forecast.hourly.temperature_2m[index],windMph:forecast.hourly.wind_speed_10m[index],...(Number.isFinite(forecast.hourly.precipitation_probability?.[index])?{precipitationProbability:forecast.hourly.precipitation_probability[index]}:{}),forecastAt:new Date(target).toISOString(),checkedAt,message:`Forecast near ${city} at kickoff; city coordinates, not a stadium microclimate. Weather impact is not assumed without fitted evidence.`,sources:[published,source('open-meteo-geocoding','Open-Meteo geocoding',geocodeUrl,checkedAt),source('open-meteo-weather','Open-Meteo hourly forecast',weatherUrl,checkedAt)]};
    }
   }catch{/* Preserve the attributed published fallback without guessing missing wind. */}
  }
  if(Number.isFinite(info?.weather?.temperature))return{status:'partial',temperatureF:info.weather.temperature,...(Number.isFinite(info.weather.precipitation)?{precipitationProbability:info.weather.precipitation}:{}),forecastAt:game.startTime,checkedAt,message:'Reported game temperature; wind and exact forecast publication time are unavailable. No quantitative weather adjustment is invented.',sources:[published]};
  return unavailable('No verified weather forecast is published for this matchup.',[published]);
 }catch{return unavailable('Weather could not be verified right now. No weather value was guessed.',[source('espn-game-weather','ESPN published game weather',summaryUrl,checkedAt,'unavailable')]);}
}
const STATISTIC_ASSETS=[
 ['pbp','pbp','play_by_play','play-by-play'],
 ['injuries','injuries','injuries','injury reports'],
 ['snaps','snap_counts','snap_counts','snap counts'],
 ['rosters','rosters','roster','rosters'],
 ['depth','depth_charts','depth_charts','depth charts'],
 ['player-stats','stats_player','stats_player_week','player statistics'],
 ['team-stats','stats_team','stats_team_week','team statistics'],
] as const;
type StatisticsVersion={version:string;source:ResearchSource;sources:ResearchSource[]};
const statisticsCache=new Map<number,{expiresAt:number;value:StatisticsVersion}>();
const statisticsPending=new Map<number,Promise<StatisticsVersion>>();
export async function fetchStatisticsVersion(game:PublicGame):Promise<StatisticsVersion>{
 const cached=statisticsCache.get(game.season);if(cached&&cached.expiresAt>Date.now())return cached.value;
 const pending=statisticsPending.get(game.season);if(pending)return pending;
 const task=(async()=>{try{
  const checkedAt=new Date().toISOString();
  // These are the same fixed release assets consumed by the private worker.
  // A roster or opportunity update must invalidate research even when PBP has
  // not changed. Collection clocks never enter this semantic fingerprint.
  const assets=await Promise.all(STATISTIC_ASSETS.map(async([kind,tag,prefix,name])=>{
   const url=`${NFLVERSE_RELEASE}/${tag}/${prefix}_${game.season}.csv.gz`;
   try{
    const result=await boundedFetch(url,50_000_000,8000,'HEAD'),etag=result.headers.get('etag'),modified=result.headers.get('last-modified');
    const fingerprint=etag?`etag:${etag}`:modified?`modified:${modified};bytes:${result.headers.get('content-length')??'unknown'}`:'metadata-unverified';
    return{kind,fingerprint,source:source(`nflverse-${kind}`,`nflverse ${name}`,url,checkedAt,etag||modified?'available':'partial',etag||modified?'Published asset version checked; the compute worker separately verifies actual downloaded bytes and excludes future plays.':'Asset reachable, but version metadata is unavailable. The compute worker independently verifies historical coverage.',fingerprint)};
   }catch{return{kind,fingerprint:'source-check-unavailable',source:source(`nflverse-${kind}`,`nflverse ${name}`,url,checkedAt,'unavailable','Asset version could not be verified. No statistics or availability were substituted.')}};
  }));
  const value={version:sha(assets.map(({kind,fingerprint})=>({kind,fingerprint}))),source:assets[0].source,sources:assets.map(item=>item.source)};
  if(statisticsCache.size>=2&&!statisticsCache.has(game.season))statisticsCache.delete(statisticsCache.keys().next().value!);
  statisticsCache.set(game.season,{expiresAt:Date.now()+60000,value});return value;
 }finally{statisticsPending.delete(game.season);}})();
 statisticsPending.set(game.season,task);return task;
}
