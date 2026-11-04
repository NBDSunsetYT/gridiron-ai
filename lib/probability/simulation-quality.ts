/** Integrity/availability checks, independent of price and outcome accuracy. */
export function footballSimulationQuality(result:any,research:any,injuries:any[],now=Date.now()){
 const reasons:string[]=[];const catalog=Array.isArray(research?.playerCatalog)?research.playerCatalog:[];
 const current=(injuries??[]).filter(i=>/^(?:out|inactive|suspended|ir)$/i.test(String(i.status_code??''))&&Number.isFinite(Date.parse(i.source_updated_at))&&Date.parse(i.source_updated_at)<=now+60000);
 for(const injury of current){
  const matches=catalog.filter((p:any)=>p.id==='cfb:'+injury.player_id||'espn:'+p.espnId===injury.player_id);
  if(matches.length!==1)continue;
  const stats=result?.players?.[matches[0].id];if(!stats)continue;
  if(['passingAttempts','targets','receptions','carries'].some(s=>typeof stats[s]?.mean==='number'&&stats[s].mean>0))reasons.push((matches[0].name??injury.player_name??'A player')+' is reported unavailable but still receives simulated opportunities. The game requires a personnel-aware rerun.');
 }
 if(result?.players&&Object.values(result.players).length>0&&Object.values(result.players).every((p:any)=>['passingYards','receivingYards','completions','receptions'].every(s=>Number.isFinite(p?.[s]?.mean)))){
  const sum=(stat:string)=>Object.values(result.players).reduce((n:number,p:any)=>n+(Number.isFinite(p?.[stat]?.mean)?p[stat].mean:0),0);
  if(Math.abs(sum('passingYards')-sum('receivingYards'))>1e-6||Math.abs(sum('completions')-sum('receptions'))>1e-6)reasons.push('The archived player passing and receiving totals do not reconcile.');
 }
 return{usable:reasons.length===0,status:reasons.length?'failed':'conditional',reasonCode:reasons.length?'simulation_integrity_or_availability_failed':null,reasons,validated:false,warning:'Accounting checks do not establish calibration, injury-adjusted accuracy or model reliability.'};
}
