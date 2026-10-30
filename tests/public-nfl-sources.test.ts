import {afterEach,describe,it,expect,vi} from 'vitest';
import {gzipSync} from 'node:zlib';
import {normalizePublicSchedule,fetchInjuries,fetchWeather,sha,nflSeason} from '../lib/public-nfl/sources';
import type {PublicGame} from '../lib/public-nfl/types';
const at='2026-10-30T20:00:00Z';
const csv='game_id,season,week,gameday,gametime,home_team,away_team,home_score,away_score,stadium,roof,surface,espn,home_moneyline\n2026_08_BAL_BUF,2026,8,2026-11-01,13:00,BUF,BAL,,,SYNTHETIC source stadium,outdoors,grass,12345,-200\n2026_07_BAL_CHI,2026,7,2026-10-25,13:00,CHI,BAL,21,14,SYNTHETIC stadium,outdoors,grass,12344,-300\n';
const game:PublicGame={id:'2026_08_BAL_BUF',season:2026,week:8,startTime:'2026-11-01T18:00:00Z',status:'scheduled',home:{id:'BUF',abbreviation:'BUF',name:'Buffalo Bills'},away:{id:'BAL',abbreviation:'BAL',name:'Baltimore Ravens'},espnId:'12345',roof:'outdoors',sources:[]};
afterEach(()=>{vi.unstubAllGlobals();vi.useRealTimers();});
describe('Published NFL source boundaries',()=>{
 it('converts the documented Eastern kickoff across DST and never treats archived moneylines as live contracts',()=>{const data=normalizePublicSchedule(csv,at,2026);expect(data.games).toHaveLength(2);expect(data.games[1]).toMatchObject({id:game.id,startTime:'2026-11-01T18:00:00.000Z',status:'scheduled',home:{score:null},away:{score:null}});expect(data.games[0]).toMatchObject({status:'final',home:{score:21},away:{score:14}});expect(JSON.stringify(data.games)).not.toContain('moneyline');expect(data.sources[0].publishedAt).toBeNull();});
 it('rejects malformed or absent season evidence instead of inventing an NFL schedule',()=>{expect(()=>normalizePublicSchedule('unrelated,column\n1,2',at,2026)).toThrow(/fields/);expect(()=>normalizePublicSchedule(csv,at,2025)).toThrow(/no valid/);expect(nflSeason(new Date('2027-01-15T00:00Z'))).toBe(2026);});
 it('never infers a live game or live score solely because the scheduled clock passed',()=>{const pending=csv.replace('2026-11-01,13:00','2026-10-29,13:00'),data=normalizePublicSchedule(pending,at,2026),game=data.games.find(g=>g.id==='2026_08_BAL_BUF')!;expect(game.status).toBe('scheduled');expect(game.statusMessage).toMatch(/live score has not been verified/);expect(game.home.score).toBeNull();expect(game.away.score).toBeNull();});
 it('changes the source version when actual evidence changes, using raw byte fidelity',()=>{expect(sha(Buffer.from('SYNTHETIC'))).toBe(sha('SYNTHETIC'));expect(normalizePublicSchedule(csv,at,2026).inputVersion).not.toBe(normalizePublicSchedule(csv.replace('21,14','24,14'),at,2026).inputVersion);});
 it('preserves uncertain and reported-out designations and unknown publication times without availability probabilities',async()=>{
  const raw='season,team,week,gsis_id,full_name,position,report_status,practice_status,report_primary_injury\n2026,BUF,8,SYNTHETIC-Q,SYNTHETIC QUESTIONABLE,WR,Questionable,Limited Participation in Practice,Ankle\n2026,BAL,8,SYNTHETIC-OUT,SYNTHETIC OUT,CB,Out,Did Not Participate,Foot\n2026,BUF,7,SYNTHETIC-OLD,SYNTHETIC OLD,WR,Out,,Knee';
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(gzipSync(raw))));const result=await fetchInjuries(game);expect(result.items).toHaveLength(2);expect(result.items[0]).toMatchObject({status:'Questionable',availability:'uncertain',publishedAt:null,officialConfirmed:false});expect(result.items[1].status).toBe('Out');expect(result.items.every(i=>!('activeProbability'in i))).toBe(true);expect(result.items.every(i=>i.publishedAt===null)).toBe(true);
 });
 it('does not label a missing matching report as a clean bill of health',async()=>{vi.stubGlobal('fetch',vi.fn(async()=>new Response(gzipSync('team,week,report_status,practice_status,gsis_id\nBUF,7,Out,,SYNTHETIC-OLD'))));const result=await fetchInjuries(game);expect(result.status).toBe('partial');expect(result.items).toHaveLength(0);expect(result.message).toMatch(/does not confirm/i);});
 it('returns unavailable on failed injury feeds and omits invented values',async()=>{vi.stubGlobal('fetch',vi.fn(async()=>new Response('Not available',{status:503})));const result=await fetchInjuries(game);expect(result.status).toBe('unavailable');expect(result.items).toEqual([]);expect(result.sources[0].status).toBe('unavailable');});
 it('withholds weather for a mismatched event identity and never imports provider odds or predicted probabilities',async()=>{vi.stubGlobal('fetch',vi.fn(async()=>Response.json({header:{id:'DIFFERENT'},gameInfo:{weather:{temperature:77}},odds:[{price:.7}],predictor:{homeTeam:{gameProjection:80}}})));const result=await fetchWeather(game);expect(result.status).toBe('unavailable');expect(result).not.toHaveProperty('temperatureF');expect(result).not.toHaveProperty('homeWinProbability');});
 it('retains a published partial forecast without guessing absent wind or precise publication time',async()=>{vi.stubGlobal('fetch',vi.fn(async()=>Response.json({header:{id:'12345'},gameInfo:{weather:{temperature:65,precipitation:10}}})));const result=await fetchWeather(game);expect(result).toMatchObject({status:'partial',temperatureF:65,precipitationProbability:10});expect(result.windMph).toBeUndefined();expect(result.sources[0].publishedAt).toBeNull();});
 it('fingerprints every worker asset and deduplicates simultaneous season checks across matchups',async()=>{
  vi.resetModules();vi.useFakeTimers();vi.setSystemTime(new Date(at));
  const transport=vi.fn(async(_url:any,options:any)=>{expect(options.method).toBe('HEAD');return new Response(null,{headers:{ETag:'SYNTHETIC-ASSET-V1'}});});vi.stubGlobal('fetch',transport);
  const {fetchStatisticsVersion}=await import('../lib/public-nfl/sources');
  const [first,second]=await Promise.all([fetchStatisticsVersion(game),fetchStatisticsVersion({...game,id:'SYNTHETIC-OTHER-GAME'})]);
  expect(transport).toHaveBeenCalledTimes(7);expect(first.version).toBe(second.version);expect(first.sources).toHaveLength(7);
  expect(first.sources.map(s=>s.id)).toEqual(['nflverse-pbp','nflverse-injuries','nflverse-snaps','nflverse-rosters','nflverse-depth','nflverse-player-stats','nflverse-team-stats']);
  expect(first.sources.every(s=>s.status==='available'&&s.publishedAt===null)).toBe(true);
  expect(transport.mock.calls.map(([url])=>String(url))).toContain('https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_2026.csv.gz');
  vi.setSystemTime(new Date(Date.parse(at)+61000));const refreshed=await fetchStatisticsVersion(game);
  expect(transport).toHaveBeenCalledTimes(14);expect(refreshed.version).toBe(first.version);expect(refreshed.sources[0].collectedAt).not.toBe(first.sources[0].collectedAt);
 });
 it('invalidates the composite evidence when roster, snaps, depth, injury or weekly usage changes without a PBP update',async()=>{
  vi.resetModules();vi.useFakeTimers();let clock=Date.parse(at);vi.setSystemTime(clock);let changed='';
  const paths=['/injuries/','/snap_counts/','/rosters/','/depth_charts/','/stats_player/','/stats_team/'];
  vi.stubGlobal('fetch',vi.fn(async(url:any)=>new Response(null,{headers:{ETag:String(url).includes(changed)&&changed?'SYNTHETIC-CHANGED-ASSET':'SYNTHETIC-UNCHANGED-ASSET'}})));
  const {fetchStatisticsVersion}=await import('../lib/public-nfl/sources');const base=await fetchStatisticsVersion(game);
  for(const path of paths){changed=path;vi.setSystemTime(clock+=61000);const next=await fetchStatisticsVersion(game);expect(next.version).not.toBe(base.version);expect(next.source.version).toBe(base.source.version);}
 });
 it('keeps unavailable or missing version metadata stable across clocks and marks the coverage explicitly',async()=>{
  vi.resetModules();vi.useFakeTimers();vi.setSystemTime(new Date(at));
  vi.stubGlobal('fetch',vi.fn(async(url:any)=>String(url).includes('/rosters/')?new Response('SYNTHETIC unavailable',{status:503}):new Response(null)));
  const {fetchStatisticsVersion}=await import('../lib/public-nfl/sources');const first=await fetchStatisticsVersion(game);
  expect(first.sources.find(s=>s.id==='nflverse-rosters')?.status).toBe('unavailable');expect(first.source.status).toBe('partial');
  vi.setSystemTime(new Date('2026-10-31T20:00:00Z'));const second=await fetchStatisticsVersion(game);expect(second.version).toBe(first.version);
 });
});
