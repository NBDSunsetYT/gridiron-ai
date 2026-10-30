'use client';
import {useEffect,useState} from 'react';
import {LoaderCircle} from 'lucide-react';

/** Auth redirects return to the application, never a developer dashboard. */
export function AppAuthReturn(){
 useEffect(()=>{const query=new URLSearchParams(window.location.search),code=query.get('code');if(code)window.location.replace('/auth/callback?code='+encodeURIComponent(code));},[]);return null;
}
export default function AppSignInMethods(){
 const[apple,setApple]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{let active=true;fetch('/api/auth/providers',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(data=>{if(active)setApple(data?.apple===true);}).catch(()=>{});return()=>{active=false;};},[]);
 if(!apple)return null;
 const signIn=async()=>{setBusy(true);setError('');try{const response=await fetch('/api/auth/apple',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}),value=await response.json();if(!response.ok)throw Error(value.error||'Sign in with Apple is temporarily unavailable.');const url=new URL(value.url);if(url.protocol!=='https:'||!url.pathname.endsWith('/auth/v1/authorize'))throw Error('Sign-in could not be started.');window.location.assign(url.href);}catch(e){setError(e instanceof Error?e.message:'Sign-in could not be started.');setBusy(false);}};
 return <div style={{marginBottom:18}}><button className="btn" type="button" style={{width:'100%',justifyContent:'center'}} disabled={busy} onClick={()=>void signIn()}>{busy?<LoaderCircle size={16} className="spin"/>:<span aria-hidden="true" style={{fontSize:20}}></span>} Continue with Apple</button>{error&&<p className="negative" role="alert" style={{fontSize:12,marginTop:10}}>{error}</p>}<p className="muted" style={{textAlign:'center',fontSize:11,marginTop:14}}>or use your email</p></div>;
}
