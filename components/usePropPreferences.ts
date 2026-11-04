'use client';
import {useEffect,useRef,useState} from 'react';
import {DEFAULT_PROP_VIEW,validPropView,type PropView} from '@/lib/props/view';
/** Browser storage is only a non-sensitive preference mirror. Signed-in users
 * use their existing owner-scoped database preferences across devices. */
export function usePropPreferences(sport:'NFL'|'CFB',user?:{id:string}|null){
 const [view,setView]=useState<PropView>(DEFAULT_PROP_VIEW),[loaded,setLoaded]=useState(''),[status,setStatus]=useState(''),[epoch,setEpoch]=useState(0),saved=useRef(''),current=useRef(view);current.current=view;
 const account=user?.id??'guest',key='propView.'+sport,local='gridiron-prop-view-v1:'+account+':'+sport;
 useEffect(()=>{let stopped=false;setLoaded('');setStatus('');saved.current='';(async()=>{let value=DEFAULT_PROP_VIEW;let localDirty=false;try{const mirror=JSON.parse(localStorage.getItem(local)??'null');value=validPropView(mirror?.view??mirror)??value;localDirty=mirror?.dirty===true;}catch{}
  if(account!=='guest')try{const r=await fetch('/api/preferences',{cache:'no-store'}),body=await r.json();if(!r.ok)throw Error();const cloud=validPropView(body.preferences?.[key]);if(cloud&&!localDirty)value=cloud;saved.current=cloud?JSON.stringify(cloud):'';}catch{saved.current=localDirty?'':JSON.stringify(value);if(!stopped)setStatus('Preference sync delayed; changes stay queued on this device.');}
  if(!stopped){setView(value);setLoaded(account+':'+sport);}
 })();return()=>{stopped=true;};},[account,sport,key,local]);
 const ready=loaded===account+':'+sport;
 useEffect(()=>{if(!ready)return;try{localStorage.setItem(local,JSON.stringify({view,dirty:account!=='guest'&&JSON.stringify(view)!==saved.current}));}catch{setStatus('Device preference storage unavailable.');}if(account==='guest'||JSON.stringify(view)===saved.current)return;let stopped=false;const t=setTimeout(async()=>{const sent=current.current;try{if(!navigator.onLine)throw Error();const r=await fetch('/api/preferences',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({preferences:{[key]:sent}})});const receipt=await r.json();if(!r.ok||JSON.stringify(validPropView(receipt.preferences?.[key]))!==JSON.stringify(sent))throw Error();if(!stopped){saved.current=JSON.stringify(sent);try{if(JSON.stringify(current.current)===saved.current)localStorage.setItem(local,JSON.stringify({view:sent,dirty:false}));}catch{}setStatus('Preferences synced');}}catch{if(!stopped)setStatus('Preference sync delayed; changes stay queued on this device.');}},700);return()=>{stopped=true;clearTimeout(t);};},[view,ready,account,key,local,epoch]);
 useEffect(()=>{const online=()=>setEpoch(e=>e+1),t=setInterval(()=>{if(account!=='guest'&&JSON.stringify(current.current)!==saved.current)online();},15000);window.addEventListener('online',online);return()=>{clearInterval(t);window.removeEventListener('online',online);};},[account]);
 return{view,setView,ready,status};
}
