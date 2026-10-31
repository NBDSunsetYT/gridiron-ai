import {NextRequest,NextResponse} from 'next/server';
import {selectedBackend} from './lib/backend';
export function middleware(request:NextRequest){
 const path=request.nextUrl.pathname;
 if(path==='/api/backend'||path==='/api/health'||path==='/api/nfl'||path.startsWith('/api/nfl/')||path==='/api/props'||path.startsWith('/api/props/')||path.startsWith('/api/auth/')||path.startsWith('/api/cloud/'))return NextResponse.next();
 if(selectedBackend(request.cookies.get('gridiron_backend')?.value)==='supabase'){
  const url=request.nextUrl.clone();url.pathname='/api/cloud/'+path.slice('/api/'.length);
  return NextResponse.rewrite(url);
 }
 return NextResponse.next();
}
// Vercel Services supports Node middleware; preserve the same backend rewrite.
export const config={matcher:'/api/:path*',runtime:'nodejs'};
