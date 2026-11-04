'use client';
import {marketComparison} from '@/lib/props/view';
const pct=(p:number)=>(p*100).toFixed(1)+'%';
export default function PropMarketComparison({row,now}:{row:any;now:number}){
 const c=marketComparison(row,now),p=c.differencePp;
 return <div className="prop-market-comparison" aria-label="Model and market comparison"><div><span>Market break-even</span><strong>{c.beforeFees===null?'Unavailable':pct(c.beforeFees)}</strong><small>Before fees · {c.family==='event_contract'?'event contract':'sportsbook reference'}</small></div><div><span>Model–market difference</span><strong className={p===null?'':p>=0?'positive':'negative'}>{p===null?'Unavailable':(p>=0?'+':'')+p.toFixed(1)+' pp'}</strong><small>Comparison only · not verified net value</small></div>{c.family==='event_contract'&&<div><span>After-fee break-even</span><strong>{c.afterFees===null?'Fees/terms unverified':pct(c.afterFees)}</strong></div>}<p>{c.decimalOdds&&<>Decimal odds: {Number(c.decimalOdds).toFixed(3)} · </>}{c.beforeFees===null?c.reason:'High hit probability alone does not establish positive expected value.'}</p></div>;
}
