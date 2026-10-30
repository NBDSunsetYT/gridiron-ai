import {EnvHttpProxyAgent,setGlobalDispatcher} from 'undici';
let configured=false;
/** Respect the managed environment's proxy, CA trust and NO_PROXY. Never bypass policy. */
export function configureServerNetwork(){
 if(configured)return;
 if(process.env.HTTPS_PROXY||process.env.HTTP_PROXY||process.env.https_proxy||process.env.http_proxy)setGlobalDispatcher(new EnvHttpProxyAgent());
 configured=true;
}
