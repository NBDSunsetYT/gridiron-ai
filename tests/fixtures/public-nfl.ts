/** Synthetic browser transport fixture only. Never imported by application code. */
export function publicResearchFixture(){
 const now=new Date().toISOString(),startTime=new Date(Date.now()+86400000).toISOString();
 const source={id:'SYNTHETIC-BROWSER-SOURCE',name:'SYNTHETIC browser transport fixture',url:'https://example.test/synthetic-browser-source',collectedAt:now,status:'available'};
 const game={id:'SYNTHETIC-BROWSER-GAME',season:2026,week:9,startTime,status:'scheduled',home:{id:'SYNTH-H',abbreviation:'SYN-H',name:'SYNTHETIC Home'},away:{id:'SYNTH-A',abbreviation:'SYN-A',name:'SYNTHETIC Away'},sources:[source]};
 const dist=(value:number)=>({mean:value,median:value,interval90:[value,value],histogram:[{value,count:10000}]});
 const result={modelVersion:'SYNTHETIC-BROWSER-TRANSPORT',engineVersion:'SYNTHETIC-ONLY',inputDataVersion:'SYNTHETIC-INPUT',simulations:10000,home:'SYNTH-H',away:'SYNTH-A',homeWinProbability:.5,awayWinProbability:.5,tieProbability:0,scoreDistributions:{'SYNTH-H':dist(21),'SYNTH-A':dist(21)},totalDistribution:dist(42),marginDistribution:dist(0),players:{'SYNTHETIC-PLAYER':{receivingYards:dist(50),receptions:dist(5)}},monteCarloInterval95:[.49,.51],evidence:{games:20,plays:1000},uncertainty:{model:'SYNTHETIC fixture: no NFL forecast claimed.'},convergence:[{simulations:10000,homeWinProbability:.5,monteCarloSE:.005}],contracts:[]};
 const summary={text:'SYNTHETIC browser transport explanation only. This text is a cited fixture, not a live AI response or an NFL forecast.',generatedByAI:false,method:'evidence_brief',createdAt:now,citations:[source],limitations:['SYNTHETIC transport only']};
 const analysis={id:'10000000-0000-4000-8000-000000000005',gameId:game.id,status:'completed',simulations:10000,updatedAt:now,createdAt:now,stale:false,result,summary};
 const coverage=(message:string)=>({status:'unavailable',items:[],checkedAt:now,message,sources:[]});
 const detail={game,analysis,status:'ready',sources:[source],injuries:coverage('Injury evidence unavailable in this SYNTHETIC browser fixture.'),weather:{status:'unavailable',checkedAt:now,message:'Weather evidence unavailable in this SYNTHETIC browser fixture.',sources:[]},markets:coverage('Verified live market prices unavailable in this SYNTHETIC browser fixture.'),summary,statistics:{playerNames:{'SYNTHETIC-PLAYER':'SYNTHETIC Player'}},ai:{available:false,generatedByAI:false},updatedAt:now};
 const dashboard={games:[game],updatedAt:now,sources:[source],modelPerformance:{n:0,status:'research_only',message:'SYNTHETIC browser transport only'},refresh:{status:'fresh',message:'SYNTHETIC fixture'},guestAccess:true};
 return{game,result,summary,analysis,detail,dashboard};
}
