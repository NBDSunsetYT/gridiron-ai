'use client';
import {useEffect,useState} from 'react';
import {Check,Copy,Info,Smartphone} from 'lucide-react';

export default function PwaInstallation(){
 const [state,setState]=useState({checked:false,installed:false,secure:false,offlineReady:false,url:''}),[message,setMessage]=useState('');
 useEffect(()=>{
  let active=true;const mode=window.matchMedia('(display-mode: standalone)');
  const inspect=()=>{if(active)setState(current=>({...current,checked:true,installed:mode.matches||Boolean((navigator as Navigator&{standalone?:boolean}).standalone),secure:window.isSecureContext,url:window.location.origin+'/'}));};
  inspect();mode.addEventListener('change',inspect);const cleared=()=>setState(current=>({...current,offlineReady:false}));window.addEventListener('gridiron:caches-cleared',cleared);
  if('serviceWorker'in navigator&&'caches'in window){void navigator.serviceWorker.ready.then(async()=>{const shell=await caches.match('/offline.html');if(active)setState(current=>({...current,offlineReady:Boolean(shell)}));}).catch(()=>{});}
  return()=>{active=false;mode.removeEventListener('change',inspect);window.removeEventListener('gridiron:caches-cleared',cleared);};
 },[]);
 const copy=async()=>{try{await navigator.clipboard.writeText(state.url);setMessage('App address copied. Open it in Safari on your iPhone.');}catch{setMessage('Copy the app address shown above, then open it in Safari.');}};
 return <section className="panel settings-install" aria-label="Install GRIDIRON AI"><div className="panel-head"><h3><Smartphone size={18}/> Install on your iPhone</h3><span className="tag">{state.installed?'STANDALONE MODE':'PROGRESSIVE WEB APP'}</span></div><div className="modal-body">
  {state.installed?<div className="notice" role="status"><Check size={17}/><span>GRIDIRON AI is running in standalone mode. Your account records stay synchronized through the server when you are online.</span></div>:<ol className="install-steps"><li><span>01</span><div><strong>Open this app address in Safari.</strong><p>NFL research opens immediately. Sign in only for personal records.</p></div></li><li><span>02</span><div><strong>Tap Share, then Add to Home Screen.</strong><p>Use “Open as Web App” if Safari offers the option.</p></div></li><li><span>03</span><div><strong>Launch GRIDIRON AI from your Home Screen.</strong><p>No App Store, TestFlight or native download is required.</p></div></li></ol>}
  {state.url&&<div className="pwa-address"><span className="muted">Your app address</span><code>{state.url}</code><button className="btn" onClick={()=>void copy()}><Copy size={14}/> Copy app link</button></div>}
  {state.url&&!state.url.startsWith('https:')&&<p className="muted" style={{fontSize:12,lineHeight:1.7}}>This is a local development address. Use the deployed HTTPS app address on your iPhone.</p>}
  <div className="source-line"><div><strong>Secure app context</strong><p>{!state.checked?'Checking…':state.secure?'Secure web-app context available.':'HTTPS is required outside localhost before installation.'}</p></div><span className="tag">{!state.checked?'CHECKING':state.secure?'READY':'HTTPS REQUIRED'}</span></div>
  <div className="source-line"><div><strong>Offline shell</strong><p>{state.offlineReady?'Public interface assets are cached. Private account responses are never cached.':'Visit while online to prepare the public offline interface.'}</p></div><span className="tag">{state.offlineReady?'CACHED':'ONLINE REQUIRED'}</span></div>
  {message&&<p className="notice" role="status">{message}</p>}
  <div className="notice"><Info size={17}/><span>Live markets, AI, transactions and account synchronization require a connection. Optional encrypted historical snapshots are configured separately.</span></div><p className="muted" style={{fontSize:12,lineHeight:1.7,marginTop:12}}>Saving the source ZIP to Files preserves the project; it does not run the backend on an iPhone.</p>
 </div></section>;
}
