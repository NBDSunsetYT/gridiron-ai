import {describe,it,expect} from 'vitest';
import {collegePlayerProjections} from '../lib/college-football/projections';
const now=Date.parse('2026-10-31T12:00:00Z');
function fixture(){const game:any={id:'cfb:espn:1',sport:'CFB',status:'scheduled',kickoffVerified:true,startTime:'2026-11-07T17:00:00Z',home:{id:'cfb:espn:10',name:'SYNTHETIC College Home'},away:{id:'cfb:espn:11',name:'SYNTHETIC College Away'}},distribution={mean:60,median:60,interval90:[40,80],histogram:[{value:40,count:5000},{value:80,count:5000}]},analysis:any={id:'SYNTHETIC-CFB-ANALYSIS',gameId:game.id,sport:'CFB',status:'completed',stale:false,simulations:10000,research:{playerCatalog:[{id:'cfb:espn:123',name:'SYNTHETIC Receiver',team:game.home.id,observedRoles:['receiver']}]},result:{sport:'CFB',eventStart:game.startTime,modelVersion:'cfb-SYNTHETIC',engineVersion:'cfb-SYNTHETIC',home:game.home.id,away:game.away.id,simulations:10000,homeWinProbability:.5,awayWinProbability:.5,players:{'cfb:espn:123':{receivingYards:distribution,targets:distribution}}}};return{game,analysis};}
describe('Independent college-player research without invented prices',()=>{
 it('extracts only reconciled distributions from actual game evidence and leaves all market fields unavailable',()=>{
  const{game,analysis}=fixture(),rows=collegePlayerProjections(game,analysis,now);expect(rows).toHaveLength(1);expect(rows[0]).toMatchObject({sport:'CFB',dataFamily:'independent_projection',stat:'receivingYards',mean:60,simulations:10000,threshold:null,marketPrice:null,bookmaker:null,calibratedProbability:null,expectedValue:null});expect(rows.some(row=>row.stat==='targets')).toBe(false);
 });
 it('withholds cross-sport, wrong-game, stale, live and unverified participant results',()=>{
  const{game,analysis}=fixture();for(const patch of [{sport:'NFL'},{gameId:'OTHER'},{stale:true},{simulations:50000},{result:{...analysis.result,home:'OTHER'}},{result:{...analysis.result,homeWinProbability:.9}}])expect(collegePlayerProjections(game,{...analysis,...patch},now)).toEqual([]);expect(collegePlayerProjections(game,analysis,Date.parse(game.startTime))).toEqual([]);
  expect(collegePlayerProjections({...game,status:'live'},analysis,now)).toEqual([]);expect(collegePlayerProjections({...game,kickoffVerified:false},analysis,now)).toEqual([]);
  analysis.research.playerCatalog[0].id='00-0000001';expect(collegePlayerProjections(game,analysis,now)).toEqual([]);
 });
 it('does not turn inconsistent histogram counts or means into a projection',()=>{
  const{game,analysis}=fixture();analysis.result.players['cfb:espn:123'].receivingYards.histogram[0].count=4000;expect(collegePlayerProjections(game,analysis,now)).toEqual([]);
 });
});
