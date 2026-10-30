/** Shared native policy. Never accepts a caller-supplied credential destination. */
export const NATIVE_AUTH_COOKIE_NAMES = ['gridiron_session','gridiron_sb_access','gridiron_sb_refresh','gridiron_backend'] as const;
export const NATIVE_VIEWS = ['home','contracts','games','simulations','injuries','players','models','performance','movement','history','parlay','intelligence','bankroll','paper','scanner','settings','calendar','warehouse','auditor','pipeline'] as const;
export function trustedNativeOrigin(input:string):string {
  let url:URL;try{url=new URL(input);}catch{throw Error('GRIDIRON_NATIVE_URL must be a complete HTTPS origin.');}
  if(url.protocol!=='https:'||url.username||url.password||url.search||url.hash||url.pathname!=='/'||['localhost','127.0.0.1','0.0.0.0','[::1]'].includes(url.hostname))throw Error('Native release requires one HTTPS origin without credentials, paths, query, fragments or loopback hosts.');
  return url.origin;
}
export function allowedNativeNavigation(target:string,origin:string){try{const expected=trustedNativeOrigin(origin),url=new URL(target,expected);return url.origin===expected&&!url.username&&!url.password&&url.protocol==='https:';}catch{return false;}}
export function nativeDeepLink(input:string):string|null{try{const url=new URL(input);if(url.protocol!=='gridironai:'||url.hostname!=='open'||url.username||url.password||url.pathname&&url.pathname!=='/'||url.hash||Array.from(url.searchParams.keys()).some(key=>key!=='view'))return null;const view=url.searchParams.get('view');return view&&(NATIVE_VIEWS as readonly string[]).includes(view)?view:null;}catch{return null;}}
