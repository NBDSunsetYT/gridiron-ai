'use client';
import {useState,useEffect,useRef,useCallback} from 'react';
import {X,Activity,RefreshCw} from 'lucide-react';
import type {ProbabilityTarget} from '@/lib/probability/schema';
const pct=(v:unknown)=>typeof v==='number'&&Number.isFinite(v)?(v*100).toFixed(2)+'%':'Unavailable';
const phases:Record<string,string>={loading_research:'Loading research',resolving_player:'Resolving player and event',preparing_simulation:'Preparing simulation',simulation_running:'Simulation running',calculating_probability:'Calculating probability',ready:'Ready · conditional pregame estimate',data_delayed:'Data delayed',source_unavailable:'Specific source unavailable',simulation_failed:'Simulation failed'};
export default function ProbabilityToHit({target,onResult,disabled=false,label='GRIDIRON AI PROBABILITY TO HIT'}:{target:ProbabilityTarget;onResult?:(r:any)=>void;disabled?:boolean;label?:string}){
 const [open,setOpen]=useState(false),[count,setCount]=useState(10000),[value,setValue]=useState<any>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[phase,setPhase]=useState('loading_research'),[now,setNow]=useState(Date.now());
 const seq=useRef(0),trigger=useRef<HTMLButtonElement>(null),panel=useRef<HTMLElement>(null),resultRef=useRef(onResult),controller=useRef<AbortController|null>(null),busyRef=useRef(false);resultRef.current=onResult;
 const identity=JSON.stringify(target);
 const calculate=useCallback(async()=>{
  const generation=++seq.current;controller.current?.abort();const abort=new AbortController();controller.current=abort;busyRef.current=true;setBusy(true);setError('');setPhase('loading_research');
  try{
   let response=await fetch('/api/nfl/probability',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target:JSON.parse(identity),simulations:count}),cache:'no-store',signal:abort.signal});
   const started=Date.now();
   for(;;){
    const body=await response.json();if(!response.ok)throw Error(body.error??'Research could not complete.');if(generation!==seq.current)return;
    setValue(body);setPhase(body.state??(body.status==='ready'?'ready':'source_unavailable'));
    if(body.status!=='pending'){if(body.status==='ready')resultRef.current?.(body);break;}
    if(!/^[a-f0-9]{64}$/.test(body.jobId??''))throw Error('The backend did not return a valid simulation request. Retry Analysis.');
    if(Date.now()-started>330000)throw Error('The backend has not finished within this connection window. Your request remains saved. Retry Analysis to retrieve its progress.');
    await new Promise<void>((resolve,reject)=>{const stopped=()=>{clearTimeout(timer);reject(new DOMException('Request cancelled','AbortError'));};const timer=setTimeout(()=>{abort.signal.removeEventListener('abort',stopped);resolve();},3000);abort.signal.addEventListener('abort',stopped,{once:true});});
    response=await fetch('/api/nfl/probability?jobId='+encodeURIComponent(body.jobId),{cache:'no-store',signal:abort.signal});
   }
  }catch(e){if(generation===seq.current&&!abort.signal.aborted){setError((e as Error).message);setPhase('data_delayed');}}
  finally{if(generation===seq.current){busyRef.current=false;setBusy(false);}}
 },[identity,count]);
 useEffect(()=>{if(!open)return;setValue(null);void calculate();const timer=setInterval(()=>setNow(Date.now()),30000),refresh=setInterval(()=>{if(document.visibilityState==='visible'&&!busyRef.current)void calculate();},120000);return()=>{seq.current++;controller.current?.abort();busyRef.current=false;clearInterval(timer);clearInterval(refresh);};},[open,calculate]);
 useEffect(()=>{if(!open)return;panel.current?.focus();const key=(e:KeyboardEvent)=>{if(e.key==='Escape'){setOpen(false);trigger.current?.focus();}if(e.key==='Tab'&&panel.current){const all=Array.from(panel.current.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],select,[tabindex="0"]'));if(!all.length)return;const first=all[0],last=all[all.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}};document.addEventListener('keydown',key);return()=>document.removeEventListener('keydown',key);},[open]);
 const stale=Boolean(value?.kickoff&&Date.parse(value.kickoff)<=now)||Boolean(value?.checkedAt&&now-Date.parse(value.checkedAt)>180000),ready=value?.status==='ready',current=ready&&!busy&&!stale,history=Array.isArray(value?.history)?value.history.filter((v:any)=>typeof v.rawProbability==='number').reverse():[];
 const close=()=>{setOpen(false);trigger.current?.focus();};
 return <><button ref={trigger} className="btn probability-launch" disabled={disabled} onClick={()=>setOpen(true)}><Activity size={15}/>{label}</button>{open&&<div className="modal-backdrop probability-backdrop" onClick={close}><section ref={panel} tabIndex={-1} className="modal probability-dialog" role="dialog" aria-modal="true" aria-label="GRIDIRON AI probability to hit" onClick={e=>e.stopPropagation()}>
  <div className="panel-head"><div><span className="eyebrow">{target.sport} · COMPLETE GAME EVIDENCE</span><h2>Probability to hit</h2></div><button className="icon-btn" onClick={close} aria-label="Close probability"><X size={20}/></button></div>
  <div className="modal-body"><label className="field">Complete simulated games<select className="input" value={count} disabled={busy} onChange={e=>setCount(Number(e.target.value))}>{[10000,50000,100000].map(n=><option value={n} key={n}>{n.toLocaleString()} games</option>)}</select></label>
   <div role="status" aria-live="polite"><p className={busy?'probability-working':''}>{busy&&<RefreshCw size={17} className="spin"/>}{value?.mode==='live_unavailable'?'Live probability unavailable':stale?'Historical / stale estimate':phases[phase]??'Research unavailable'}</p></div>
   {error&&<p role="alert" className="notice notice-error">{error}</p>}
   {value&&<><p>{value.outcome??value.reason}</p>{!ready&&value.reasonCode&&<small>Analysis diagnostic: {value.reasonCode.replaceAll('_',' ')}</small>}{value.retryAt&&<p>Capacity becomes available after {new Date(value.retryAt).toLocaleString()}. Previously saved results remain available.</p>}
    {ready&&<><div className={'probability-gauge '+(!current?'is-stale':'')}><strong>{pct(value.calibratedProbability??value.rawProbability)}</strong><span>{typeof value.calibratedProbability==='number'?'Validated calibrated estimate':'Raw simulation hit rate · not calibrated'}</span></div>
     <dl className="probability-metrics"><div><dt>Successful complete games</dt><dd>{value.hits.toLocaleString()} / {value.simulations.toLocaleString()}</dd></div><div><dt>Raw simulation probability</dt><dd>{pct(value.rawProbability)}</dd></div><div><dt>Calibrated probability</dt><dd>{typeof value.calibratedProbability==='number'?pct(value.calibratedProbability):'No approved calibrator for this sport and market'}</dd></div><div><dt>95% Monte Carlo interval</dt><dd>{value.monteCarloInterval95?.map(pct).join(' – ')??'Unavailable'}</dd></div><div><dt>Monte Carlo standard error</dt><dd>{typeof value.monteCarloSE==='number'?(value.monteCarloSE*100).toFixed(3)+' percentage points':'Unavailable'}</dd></div><div><dt>Model and scenario uncertainty</dt><dd>{value.modelInterval95?.map(pct).join(' – ')??'Not fully quantified'}</dd></div><div><dt>Market break-even before costs</dt><dd>{pct(value.market?.breakEven)}</dd></div><div><dt>After-fee value</dt><dd>Unavailable without verified costs and settlement terms</dd></div></dl>
     {typeof value.independenceComparison==='number'&&<p>Independence comparison only: {pct(value.independenceComparison)}. The joint estimate uses aligned game outcomes.</p>}
     <p className="notice">{value.reason} {value.calibrationReason} More simulated games reduce sampling noise; they do not prove accuracy or remove missing availability and weather evidence.</p>
     <small>{value.modelVersion??'No verified model'} · Simulated {value.calculatedAt?new Date(value.calculatedAt).toLocaleString():'Unavailable'} · Checked {new Date(value.checkedAt).toLocaleString()}</small>
     {value.market?.current===false&&<p className="notice">Current market prices are unavailable. This is independent research on a previously verified threshold; the historical quote is not an executable price.</p>}{value.market?.sourceUpdatedAt&&<p>Quote observed {new Date(value.market.sourceUpdatedAt).toLocaleString()} · {value.market.family==='sportsbook_reference'?'Sportsbook reference; not DraftKings Predictions':'See exact product terms'}</p>}
     <p role="status">{value.persistence?.saved?'Probability snapshot saved to your account.':value.persistence?.reason??'Not saved.'}</p>
    </>}
    {history.length>0&&<details open><summary>Immutable probability history ({history.length})</summary>{history.length>1&&<svg className="probability-history-chart" viewBox="0 0 300 100" role="img" aria-label="Stored raw probability history, zero to one hundred percent"><path d="M5 5V95H295" stroke="currentColor" opacity=".2" fill="none"/><polyline fill="none" stroke="#39e6aa" strokeWidth="2" points={history.map((h:any,i:number)=>(5+i*290/(history.length-1))+','+(95-h.rawProbability*90)).join(' ')}/></svg>}{history.slice(-8).reverse().map((h:any)=><p key={h.id}>{new Date(h.storedAt).toLocaleString()} · {pct(h.rawProbability)} raw · {h.simulations?.toLocaleString()} games</p>)}</details>}
    {ready&&<details><summary>Sources and assumptions</summary><p>{JSON.stringify(value.assumptions??'Availability and weather coverage are incomplete.')}</p>{(value.sources??[]).map((s:any,i:number)=><p key={i}>{/^https:\/\//.test(s.url??'')?<a href={s.url} rel="noopener noreferrer" target="_blank">{s.name??s.id??'Research source'}</a>:s.name??s.id??'Source'} · {s.collectedAt??s.checkedAt??'Timestamp unavailable'}</p>)}</details>}
   </>}
   <button className="btn" disabled={busy} onClick={()=>void calculate()}><RefreshCw size={15}/>{!ready?'Retry Analysis':'Refresh verified evidence'}</button><p className="prop-sampling-note">Research never records a financial transaction. Pregame evidence is not a live probability.</p>
  </div>
 </section></div>}</>;
}
