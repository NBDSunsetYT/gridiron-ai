import {describe,it,expect} from 'vitest';import{compareFreeProp}from'../lib/free-prop-comparison';
describe('free-feed comparison identity and complete-game counts',()=>{
 const row={sport:'CFB',player:{id:'espn:SYNTHETIC'},eventId:'SYNTHETIC',kickoff:'2099-01-01T00:00:00Z',side:'Over',threshold:'50',statistic:'receivingYards'};
 const evidence={sport:'CFB',providerPlayerId:'espn:SYNTHETIC',providerEventId:'SYNTHETIC',kickoff:row.kickoff,stale:false,simulations:10000,statistic:row.statistic,modelVersion:'SYNTHETIC',histogram:[{value:40,count:2000},{value:50,count:1000},{value:60,count:7000}]};
 it('calculates hits and pushes separately without manufacturing calibrated probability or EV',()=>expect(compareFreeProp(row,evidence)).toMatchObject({modelProbability:.7,pushProbability:.1,calibratedProbability:null,expectedValue:null}));
 it('cannot join NFL/CFB or names alone',()=>{for(const change of[{sport:'NFL'},{providerPlayerId:'OTHER'},{providerEventId:'OTHER'},{stale:true}])expect(compareFreeProp(row,{...evidence,...change}).modelProbability).toBeNull();});
 it('requires complete matching histograms',()=>expect(compareFreeProp(row,{...evidence,simulations:50000}).modelProbability).toBeNull());
 it('does not invent touchdown thresholds',()=>expect(compareFreeProp({...row,threshold:null},evidence).modelProbability).toBeNull());
});
