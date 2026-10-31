'use client';

import {useEffect,useState} from 'react';
import dynamic from 'next/dynamic';
import {ShieldCheck} from 'lucide-react';
const PlayerPropIntelligence=dynamic(()=>import('./PlayerPropIntelligence'),{loading:()=> <div className="skeleton public-card-skeleton" aria-label="Loading NFL event contracts"/>});
const FreePlayerProps=dynamic(()=>import('./FreePlayerProps'),{loading:()=> <div className="skeleton public-card-skeleton" aria-label="Loading NFL sportsbook references"/>});
type Props={user:{id:string;email:string}|null;onSignIn:()=>void;onOpenGame:(id:string)=>void;onAdvanced:()=>void;onWallet:()=>void};
/** A source-family choice is explicit. Sportsbook odds never populate an event contract. */
export default function NflPlayerPropHub(props:Props){
 const [family,setFamily]=useState<'sportsbook'|'predictions'>('sportsbook');
 useEffect(()=>{const sync=()=>setFamily(/^props\/(?:predictions(?:\/|$)|combinations\/|what-if\/)/.test(window.location.hash.replace(/^#(?:nfl\/)?/,''))?'predictions':'sportsbook');sync();window.addEventListener('hashchange',sync);return()=>window.removeEventListener('hashchange',sync);},[]);
 const choose=(next:typeof family)=>{setFamily(next);window.location.hash=next==='predictions'?'props/predictions':'props';};
 return <div className="nfl-player-prop-hub"><div className="football-source-choice panel"><div><ShieldCheck size={17}/><strong>Choose the market source</strong></div><div className="consumer-tabs" role="group" aria-label="NFL player prop source"><button aria-pressed={family==='sportsbook'} className={family==='sportsbook'?'active':''} onClick={()=>choose('sportsbook')}>Sportsbook references (PropLine)</button><button aria-pressed={family==='predictions'} className={family==='predictions'?'active':''} onClick={()=>choose('predictions')}>DraftKings Predictions contracts</button></div><p>Sportsbook odds and percentage-priced event contracts have separate prices, source access and settlement rules.</p></div>{family==='predictions'?<PlayerPropIntelligence {...props}/>:<FreePlayerProps sport="NFL" user={props.user} onSignIn={props.onSignIn}/>}</div>;
}
