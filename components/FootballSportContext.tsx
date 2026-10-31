'use client';

import {createContext,useCallback,useContext,useEffect,useRef,useState,type ReactNode} from 'react';

export type FootballSport='NFL'|'CFB';
type SportPreference={sport:FootballSport;selectSport:(sport:FootballSport)=>void;ready:boolean;syncStatus:'loading'|'device'|'syncing'|'synced'};
const SportContext=createContext<SportPreference>({sport:'NFL',selectSport:()=>{},ready:true,syncStatus:'device'});
const valid=(value:unknown):value is FootballSport=>value==='NFL'||value==='CFB';
const key=(owner:string|null)=>`gridiron-football-sport-v8:${owner??'guest'}`;
function cached(owner:string|null):{sport:FootballSport;pending:boolean}{
 try{const raw=localStorage.getItem(key(owner));if(raw){const value=JSON.parse(raw);if(valid(value?.sport))return{sport:value.sport,pending:value.pending===true};}}catch{}
 return{sport:'NFL',pending:false};
}
function remember(owner:string|null,sport:FootballSport,pending:boolean){try{localStorage.setItem(key(owner),JSON.stringify({sport,pending}));}catch{}}

/** This cache contains only the public sport preference. Financial, saved
 * research and conversation records remain in the authenticated backend. */
export function useFootballSportPreference(userId:string|null,authReady:boolean):SportPreference{
 const [sport,setSport]=useState<FootballSport>('NFL'),[ready,setReady]=useState(false),[syncStatus,setSyncStatus]=useState<SportPreference['syncStatus']>('loading');
 const owner=useRef(userId),revision=useRef(0),alive=useRef(true),saveQueue=useRef(Promise.resolve());owner.current=userId;
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const persist=useCallback((next:FootballSport,atRevision:number)=>{
  if(!userId)return;const target=userId;setSyncStatus('syncing');
  saveQueue.current=saveQueue.current.catch(()=>{}).then(async()=>{
   if(owner.current!==target)return;
   const response=await fetch('/api/preferences',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preferences:{footballSport:next}}),cache:'no-store'});
   if(!response.ok)throw Error('Sport preference synchronization is unavailable.');
   if(owner.current===target&&revision.current===atRevision){remember(target,next,false);if(alive.current)setSyncStatus('synced');}
  }).catch(()=>{if(alive.current&&owner.current===target&&revision.current===atRevision)setSyncStatus('device');});
 },[userId]);
 const selectSport=useCallback((next:FootballSport)=>{
  if(!valid(next)||!authReady)return;const atRevision=++revision.current;setSport(next);setReady(true);remember(userId,next,Boolean(userId));
  if(userId)persist(next,atRevision);else setSyncStatus('device');
 },[authReady,userId,persist]);
 useEffect(()=>{
  if(!authReady)return;let current=true;const atRevision=++revision.current,local=cached(userId);setSport(local.sport);setReady(true);setSyncStatus(userId?'loading':'device');
  if(!userId)return;
  if(local.pending){persist(local.sport,atRevision);return;}
  const controller=new AbortController();
  void fetch('/api/preferences',{cache:'no-store',signal:controller.signal}).then(async response=>{if(!response.ok)throw Error('Sport preference unavailable.');return response.json();}).then(value=>{
   if(!current||owner.current!==userId||revision.current!==atRevision)return;const remote=value.preferences?.footballSport;
   if(valid(remote)){setSport(remote);remember(userId,remote,false);}setSyncStatus('synced');
  }).catch(()=>{if(current&&revision.current===atRevision)setSyncStatus('device');});
  return()=>{current=false;controller.abort();};
 },[userId,authReady,persist]);
 useEffect(()=>{const reconnect=()=>{if(!userId)return;const value=cached(userId);if(value.pending)persist(value.sport,revision.current);};window.addEventListener('online',reconnect);return()=>window.removeEventListener('online',reconnect);},[userId,persist]);
 return{sport,selectSport,ready,syncStatus};
}
export function FootballSportProvider({value,children}:{value:SportPreference;children:ReactNode}){return <SportContext.Provider value={value}>{children}</SportContext.Provider>;}
export function useFootballSport(){return useContext(SportContext);}
export function FootballSportSelector(){const {sport,selectSport,ready}=useFootballSport();return <div className="football-sport-selector" role="group" aria-label="Football sport">{(['NFL','CFB'] as const).map(value=><button key={value} aria-label={value==='NFL'?'NFL':'College Football'} aria-pressed={sport===value} className={sport===value?'selected':''} onClick={()=>selectSport(value)} disabled={!ready}>{value==='NFL'?'NFL':'College Football'}<span aria-hidden="true">{value==='NFL'?'PRO':'NCAA'}</span></button>)}</div>;}
