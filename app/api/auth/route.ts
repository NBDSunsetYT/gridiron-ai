import { randomUUID } from 'node:crypto';
import { getDb } from '@/lib/db';
import { ApiError,digest,errorResponse,readJsonObject,getUser,guardMutation,hashPassword,newSession,rateLimit,sessionCookie,verifyPassword,SESSION_COOKIE } from '@/lib/auth';
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export async function GET(request: Request) { try { return Response.json({user:await getUser(request)},{headers:{'Cache-Control':'no-store'}}); } catch(e) {return errorResponse(e);} }
export async function POST(request: Request) {
  try {
    guardMutation(request);
    const body = await readJsonObject(request);
    if (body.action === 'logout') {
      const token = request.headers.get('cookie')?.split(';').map(s=>s.trim()).find(s=>s.startsWith(SESSION_COOKIE+'='))?.slice(SESSION_COOKIE.length+1);
      if (token) getDb().prepare('DELETE FROM sessions WHERE token_hash=?').run(digest(token));
      return Response.json({user:null},{headers:{'Set-Cookie':sessionCookie('',request)}});
    }
    const email = typeof body.email === 'string' ? body.email.trim().toLowerCase() : '';
    const password = typeof body.password === 'string' ? body.password : '';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length>254) throw new ApiError('Enter a valid email address.');
    if (password.length<12 || password.length>128) throw new ApiError('Password must contain 12–128 characters.');
    rateLimit('auth-email:'+digest(email),10,15*60_000);
    rateLimit('auth-ip:'+digest(request.headers.get('x-forwarded-for')?.split(',')[0] || 'local'),50,15*60_000);
    let user: {id:string;email:string;password_hash:string}|undefined;
    if (body.action === 'register') {
      if (getDb().prepare('SELECT id FROM users WHERE email=?').get(email)) throw new ApiError('Unable to create an account with these credentials.',409);
      const id=randomUUID(); const passwordHash=await hashPassword(password);
      getDb().transaction(()=>{
        getDb().prepare('INSERT INTO users(id,email,password_hash,created_at) VALUES(?,?,?,?)').run(id,email,passwordHash,new Date().toISOString());
        getDb().prepare('INSERT INTO settings(user_id) VALUES(?)').run(id);
      })();
      user={id,email,password_hash:passwordHash};
    } else if (body.action === 'login') {
      user=getDb().prepare('SELECT id,email,password_hash FROM users WHERE email=?').get(email) as typeof user;
      const valid=await verifyPassword(password,user?.password_hash || '00000000000000000000000000000000:'+'00'.repeat(64));
      if (!user || !valid) throw new ApiError('Email or password is incorrect.',401);
    } else throw new ApiError('Unknown authentication action.');
    return Response.json({user:{id:user.id,email:user.email}},{headers:{'Set-Cookie':sessionCookie(newSession(user.id),request),'Cache-Control':'no-store'}});
  } catch(e) {return errorResponse(e);}
}
