'use client';
import {useEffect,useState} from 'react';
import {Capacitor,registerPlugin,type PluginListenerHandle} from '@capacitor/core';
import {Bell,ShieldCheck,Smartphone} from 'lucide-react';
import {nativeDeepLink} from '@/lib/native/policy';
type NativeSession={status():Promise<{configured:boolean;keychain:boolean;pushEntitlement:boolean;apnsEnvironment:string}>;capture():Promise<{stored:number}>;restore():Promise<{restored:number;changed:boolean}>;clear():Promise<{cleared:boolean}>};
const Session=registerPlugin<NativeSession>('GridironSession');
/** Optional enhancement only; browser/PWA behavior remains unchanged. */
export default function NativeBridge({userId,view}:{userId?:string|null;view?:string}){
 const [native,setNative]=useState(false),[ready,setReady]=useState(false),[pushEntitlement,setPushEntitlement]=useState(false),[apnsEnvironment,setApnsEnvironment]=useState('development'),[currentView,setCurrentView]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false),[haptics,setHaptics]=useState(true);
 useEffect(()=>{if(!Capacitor.isNativePlatform()||Capacitor.getPlatform()!=='ios')return;setNative(true);let active=true;const handles:PluginListenerHandle[]=[];let click:((e:MouseEvent)=>void)|undefined;
 const hash=()=>setCurrentView(window.location.hash.slice(1));hash();window.addEventListener('hashchange',hash);
 const clear=()=>{void Session.clear().catch(()=>{});void import('@capacitor/push-notifications').then(({PushNotifications})=>PushNotifications.unregister()).catch(()=>{});};window.addEventListener('gridiron:logout',clear);
 void(async()=>{try{
  const status=await Session.status();if(!active)return;setPushEntitlement(status.pushEntitlement);setApnsEnvironment(status.apnsEnvironment);const restored=await Session.restore();if(restored.changed){window.location.reload();return;}setReady(true);
  const [{App},{Haptics,ImpactStyle},{StatusBar,Style},{SplashScreen}]=await Promise.all([import('@capacitor/app'),import('@capacitor/haptics'),import('@capacitor/status-bar'),import('@capacitor/splash-screen')]);
  if(!active)return;
  await StatusBar.setStyle({style:Style.Dark}).catch(()=>{});await StatusBar.setOverlaysWebView({overlay:false}).catch(()=>{});await SplashScreen.hide().catch(()=>{});
  const apply=(url:string)=>{const next=nativeDeepLink(url);if(next)window.location.hash=next;};const launch=await App.getLaunchUrl();if(launch?.url)apply(launch.url);
  const link=await App.addListener('appUrlOpen',event=>apply(event.url));if(active)handles.push(link);else await link.remove();
  const resume=await App.addListener('appStateChange',state=>{if(state.isActive)void Session.capture().catch(()=>{});});if(active)handles.push(resume);else await resume.remove();
  if(!active)return;
  click=event=>{if(localStorage.getItem('gridiron-native-haptics')==='off')return;const target=event.target instanceof Element?event.target.closest('.bottom-nav button,.nav-item,.btn-primary'):null;if(target)void Haptics.impact({style:ImpactStyle.Light}).catch(()=>{});};document.addEventListener('click',click);setHaptics(localStorage.getItem('gridiron-native-haptics')!=='off');
 }catch(e){if(active)setNotice((e as Error).message||'Native enhancements could not initialize. Your web application remains available.');}})();
 return()=>{active=false;window.removeEventListener('hashchange',hash);window.removeEventListener('gridiron:logout',clear);if(click)document.removeEventListener('click',click);for(const handle of handles)void handle.remove();};},[]);
 useEffect(()=>{if(native&&ready&&userId)void Session.capture().catch(()=>setNotice('Native Keychain could not save this session. You can sign in again after restarting.'));},[native,ready,userId]);
 const push=async()=>{setBusy(true);setNotice('');try{
  if(!pushEntitlement)throw Error('Push capability is not enabled in this signed binary. Rebuild with GRIDIRON_IOS_PUSH=1 and a matching Apple provisioning profile.');
  if(!userId)throw Error('Sign in before registering this device.');
  const {PushNotifications}=await import('@capacitor/push-notifications');const permission=await PushNotifications.requestPermissions();if(permission.receive!=='granted')throw Error('Notifications were not permitted. You can change this in iPhone Settings.');
  await new Promise<void>((resolve,reject)=>{let registration:PluginListenerHandle|undefined,error:PluginListenerHandle|undefined;const cleanup=()=>{clearTimeout(timer);void registration?.remove();void error?.remove();};const timer=setTimeout(()=>{cleanup();reject(Error('Apple did not complete registration. Verify signed-device provisioning and network access.'));},15000);
   void(async()=>{registration=await PushNotifications.addListener('registration',async token=>{try{const request=await fetch('/api/devices',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({platform:'ios',token:token.value,environment:apnsEnvironment})}),result=await request.json();if(!request.ok)throw Error(result.error||'Device registration could not be saved.');setNotice(result.message||'Device registered. Live delivery requires the configured APNs service.');cleanup();resolve();}catch(e){cleanup();reject(e);}});
   error=await PushNotifications.addListener('registrationError',()=>{cleanup();reject(Error('Native APNs registration failed. Check the Apple provisioning profile and Push Notifications capability.'));});await PushNotifications.register();})().catch(e=>{cleanup();reject(e);});
  });
 }catch(e){setNotice((e as Error).message);}finally{setBusy(false);}};
 const disable=async()=>{setBusy(true);try{const r=await fetch('/api/devices',{method:'DELETE',headers:{'Content-Type':'application/json'},body:'{}'});if(!r.ok)throw Error('Sign in to remove saved device registrations.');const {PushNotifications}=await import('@capacitor/push-notifications');await PushNotifications.unregister().catch(()=>{});setNotice('Saved registrations removed and native notifications unregistered.');}catch(e){setNotice((e as Error).message);}finally{setBusy(false);}};
 if(!native||(view||currentView)!=='settings')return null;
 return <section className="panel" style={{marginTop:24}}><div className="panel-head"><div className="heading-icon"><Smartphone size={18}/><h3>Your private iPhone app</h3></div><span className="tag">NATIVE IOS</span></div><div className="modal-body" style={{paddingTop:0}}><div className="notice"><ShieldCheck size={16}/><span>{ready?'Approved authentication cookies are protected by device-only Keychain storage. Passwords and service credentials are never exposed by the native bridge.':'Initializing secure native session support…'}</span></div><label className="check-row"><input type="checkbox" checked={haptics} onChange={event=>{setHaptics(event.target.checked);localStorage.setItem('gridiron-native-haptics',event.target.checked?'on':'off');}}/> Native navigation haptics</label><p className="muted" style={{fontSize:12,lineHeight:1.8,marginBottom:18}}>Push registration requires your permission, an Apple-enabled signed binary, server-side token encryption and APNs delivery credentials. Registration alone does not create a live injury feed or notification delivery.</p><div className="action-row"><button className="btn" disabled={busy} onClick={()=>void push()}><Bell size={15}/>{busy?'Working…':'Enable native notifications'}</button><button className="btn" disabled={busy} onClick={()=>void disable()}>Disable registrations</button></div>{notice&&<p className="muted" role="status" style={{fontSize:11,lineHeight:1.8,marginTop:16}}>{notice}</p>}</div></section>;
}
