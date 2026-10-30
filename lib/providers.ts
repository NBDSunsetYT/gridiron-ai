import { randomUUID } from 'node:crypto';
export type Market = {
  id:string;event:string;selection:string;market:string;line?:number;odds:number;sportsbook:string;
  source:'manual'|'feed';observedAt:string;sampleSize:number;sourceUrl?:string;provenance?:string;
  samples?:number[];model?:unknown;eventId?:string;commenceTime?:string;provider?:string;
};
export interface OddsProvider { name:string; fetchMarkets():Promise<Market[]> }
export class ProviderError extends Error { constructor(message:string, public status=502){super(message)} }
export class TheOddsApi implements OddsProvider {
  name='The Odds API';
  constructor(private key:string,private transport:typeof fetch=fetch){}
  async fetchMarkets():Promise<Market[]> {
    if(!this.key) throw new ProviderError('ODDS_API_KEY is not configured.',503);
    const url=new URL('https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds');
    url.searchParams.set('apiKey',this.key);url.searchParams.set('regions','us');url.searchParams.set('markets','h2h,spreads,totals');url.searchParams.set('oddsFormat','american');
    let response:Response;
    try {response=await this.transport(url,{signal:AbortSignal.timeout(15000),cache:'no-store'});} catch {throw new ProviderError('The odds provider could not be reached. Cached snapshots remain historical.');}
    if(!response.ok) throw new ProviderError(response.status===401?'Odds provider credentials were rejected.':response.status===429?'Odds provider quota or rate limit reached.':`Odds provider returned HTTP ${response.status}.`,response.status===429?429:502);
    let data:unknown;try{data=await response.json();}catch{throw new ProviderError('The odds provider returned invalid JSON.');}
    if(!Array.isArray(data)) throw new ProviderError('The odds provider response did not contain an event array.');
    const result:Market[]=[];
    for(const event of data) {
      if(!event||typeof event.id!=='string'||typeof event.home_team!=='string'||typeof event.away_team!=='string'||!Array.isArray(event.bookmakers)) continue;
      for(const book of event.bookmakers) {
        // Only expose the requested books when the authorized provider actually supplies them.
        if(!['draftkings','hardrock','hard_rock','hardrockbet'].includes(book.key)||!Array.isArray(book.markets)) continue;
        for(const market of book.markets) for(const outcome of market.outcomes??[]) {
          if(typeof outcome.name!=='string'||!Number.isFinite(outcome.price)||Math.abs(outcome.price)<100) continue;
          const observedAt=market.last_update??book.last_update;
          if(!observedAt||!Number.isFinite(Date.parse(observedAt))) continue;
          result.push({id:randomUUID(),eventId:event.id,event:`${event.away_team} @ ${event.home_team}`,commenceTime:event.commence_time,selection:outcome.name,market:({h2h:'Moneyline',spreads:'Spread',totals:'Game total'} as Record<string,string>)[market.key]??market.key,line:outcome.point,odds:outcome.price,sportsbook:book.key==='draftkings'?'DraftKings':'Hard Rock',source:'feed',provider:this.name,observedAt:new Date(observedAt).toISOString(),sampleSize:0,sourceUrl:'https://the-odds-api.com/'});
        }
      }
    }
    return result;
  }
}
export function providerStatuses(markets:Market[]=[]) {
  const latest=markets.filter(m=>m.source==='feed').map(m=>m.observedAt).sort().at(-1)??null;
  return [
    {name:'DraftKings · The Odds API',status:process.env.ODDS_API_KEY?'configured':'unavailable',updatedAt:latest,message:process.env.ODDS_API_KEY?'Credentials configured; use Refresh to request authorized prices.':'Requires a licensed ODDS_API_KEY. Manual prices are available.'},
    {name:'Hard Rock',status:markets.some(m=>m.source==='feed'&&m.sportsbook==='Hard Rock')?'snapshot':'unavailable',updatedAt:markets.filter(m=>m.sportsbook==='Hard Rock'&&m.source==='feed').map(m=>m.observedAt).sort().at(-1)??null,message:'Availability depends on provider coverage and jurisdiction. No unavailable prices are inferred.'},
    {name:'GRIDIRON INTELLIGENCE',status:process.env.OPENAI_API_KEY?'configured':'unavailable',updatedAt:null,message:process.env.OPENAI_API_KEY?'Server-side OpenAI integration configured.':'Requires a server-side OPENAI_API_KEY.'},
    {name:'Injuries, usage & weather',status:'unavailable',updatedAt:null,message:'No licensed research feed configured. No injury, player usage or weather claims are generated.'}
  ];
}
