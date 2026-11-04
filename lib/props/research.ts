import {marketComparison,thresholdKey} from './view';

export type ObservedGame={gameId:string;value:number;season?:number;week?:number;at?:string};
/** Prices, quote IDs and display names must not change a saved selection's identity. */
export function researchSelectionKey(row:any,includeBook=true):string|null{
 if(!['NFL','CFB'].includes(row.sport)||!row.eventId||!row.player?.id||!row.statistic||!row.market||!Number.isFinite(Date.parse(row.kickoff)))return null;
 return JSON.stringify([row.sport,row.provider,row.eventId,row.espnEventId??null,new Date(row.kickoff).toISOString(),row.player.id,row.statistic,row.market,row.period??'full',row.side,thresholdKey(row.threshold),...(includeBook?[row.book?.key]:[])]);
}
export function distributionSummary(bins:any){
 if(!Array.isArray(bins)||!bins.length||bins.some(b=>!Number.isFinite(b.value)||!Number.isSafeInteger(b.count)||b.count<0))return null;
 const sorted=bins.filter(b=>b.count>0).sort((a,b)=>a.value-b.value),n=sorted.reduce((s,b)=>s+b.count,0);
 if(!Number.isSafeInteger(n)||n<1)return null;
 const quantile=(q:number)=>{let at=0;for(const b of sorted){at+=b.count;if(at>=Math.max(1,Math.ceil(n*q)))return b.value;}return sorted.at(-1)!.value;};
 return{count:n,mean:sorted.reduce((s,b)=>s+b.value*b.count,0)/n,median:quantile(.5),interval80:[quantile(.1),quantile(.9)]};
}
/** Chronology comes from paired published game records, never histogram order. */
export function observedGames(row:any):ObservedGame[]{
 const games=row.historicalGames;
 if(!Array.isArray(games)||games.length>24||games.some(g=>!g||typeof g.gameId!=='string'||!Number.isFinite(g.value)||g.at&&(!Number.isFinite(Date.parse(g.at))||Date.parse(g.at)>=Date.parse(row.kickoff))))return[];
 if(new Set(games.map(g=>g.gameId)).size!==games.length)return[];
 return games;
}
export function trendWindows(row:any){
 const games=observedGames(row),threshold=Number(row.threshold);
 if(!games.length||row.threshold===null||row.threshold===undefined||String(row.threshold).trim()===''||!Number.isFinite(threshold)||!['Over','Under'].includes(row.side)||row.period&&!['full','full_game','game'].includes(row.period))return[];
 const latestSeason=games.at(-1)?.season;
 const windows=[{label:'Last 5',games:games.slice(-5)},{label:'Last 10',games:games.slice(-10)},...(Number.isInteger(latestSeason)?[{label:latestSeason+' sample',games:games.filter(g=>g.season===latestSeason)}]:[])];
 return windows.map(w=>{const hits=w.games.filter(g=>row.side==='Over'?g.value>threshold:g.value<threshold).length,pushes=w.games.filter(g=>g.value===threshold).length;return{label:w.label,n:w.games.length,hits,pushes,frequency:hits/w.games.length,average:w.games.reduce((sum,g)=>sum+g.value,0)/w.games.length};});
}
export function quoteIndex(rows:any[]){
 const index=new Map<string,any[]>();for(const row of rows){if(row.dataFamily==='event_contract')continue;const key=researchSelectionKey(row,false);if(!key)continue;const group=index.get(key)??[];group.push(row);index.set(key,group);}return index;
}
/** Equal-weight reference across other books, not proprietary 'sharp' odds.
 * A half-integer line on these integer NFL/CFB stats avoids unpriced pushes.
 * Both sides must be observed within 60s; no combining unrelated outcomes. */
export function twoSidedReference(row:any,index:Map<string,any[]>,now=Date.now()){
 const supported=['passingYards','passingTouchdowns','passingAttempts','completions','interceptions','rushingYards','carries','receivingYards','receptions','touchdowns','rushingTouchdowns','receivingTouchdowns'];
 if(!supported.includes(row.statistic)||!['Over','Under'].includes(row.side)||!['full','full_game','game'].includes(row.period??'full')||row.threshold===null||!Number.isFinite(Number(row.threshold))||Math.abs(Number(row.threshold)%1)!==.5)return null;
 const overs=comparedQuotes({...row,side:'Over'},index,now),unders=comparedQuotes({...row,side:'Under'},index,now),probabilities:number[]=[];
 for(const over of overs){const under=unders.find(q=>q.quote.book.key===over.quote.book.key);if(!under||over.quote.book.key===row.book.key||!over.current||!under.current||!over.decimalOdds||!under.decimalOdds||Math.abs(Date.parse(over.quote.sourceUpdatedAt)-Date.parse(under.quote.sourceUpdatedAt))>60000)continue;
  const a=1/Number(over.decimalOdds),b=1/Number(under.decimalOdds);if(!(a>0&&b>0&&a+b>=1&&a+b<=1.5))continue;
  probabilities.push(row.side==='Over'?a/(a+b):b/(a+b));
 }
 if(probabilities.length<2)return null;
 const probability=probabilities.reduce((a,b)=>a+b,0)/probabilities.length,target=marketComparison(row,now);
 return{probability,books:probabilities.length,range:[Math.min(...probabilities),Math.max(...probabilities)],differencePp:target.beforeFees===null?null:(probability-target.beforeFees)*100};
}
/** Exact same event/player/stat/threshold/side/period only; loaded-page coverage. */
export function comparedQuotes(row:any,index:Map<string,any[]>,now=Date.now()){
 const key=researchSelectionKey(row,false),byBook=new Map<string,any[]>();
 for(const q of key?index.get(key)??[]:[]){const book=q.book?.key;if(!book)continue;const group=byBook.get(book)??[];group.push(q);byBook.set(book,group);}
 return [...byBook.values()].map(group=>{
  group=group.slice().sort((a,b)=>Date.parse(b.sourceUpdatedAt)-Date.parse(a.sourceUpdatedAt));const quote=group[0],price=marketComparison(quote,now),conflict=group.some(q=>q.sourceUpdatedAt===quote.sourceUpdatedAt&&(q.americanOdds!==quote.americanOdds||q.decimalOdds!==quote.decimalOdds));
  return{quote,decimalOdds:price.decimalOdds,current:!conflict&&price.current&&Date.parse(quote.kickoff)>now,conflict};
 }).sort((a,b)=>Number(b.current)-Number(a.current)||Number(b.decimalOdds??0)-Number(a.decimalOdds??0));
}
