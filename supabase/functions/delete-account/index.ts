// Supabase-hosted only. Service credentials are injected by Supabase, never shipped to the app.
import { createClient } from 'npm:@supabase/supabase-js@2.118.0';
Deno.serve(async (request: Request) => {
  if (request.method !== 'POST') return Response.json({ error: 'POST required' }, { status: 405 });
  const url = Deno.env.get('SUPABASE_URL');
  const anon = Deno.env.get('SUPABASE_ANON_KEY');
  const secret = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
  if (!url || !anon || !secret) return Response.json({ error: 'Deletion service unavailable' }, { status: 503 });
  const authorization = request.headers.get('Authorization') || '';
  if (!authorization.startsWith('Bearer ')) return Response.json({ error: 'Authentication required' }, { status: 401 });
  const token = authorization.slice(7);
  const scoped = createClient(url, anon, { auth: { persistSession: false, autoRefreshToken: false }, global: { headers: { Authorization: authorization } } });
  const { data, error } = await scoped.auth.getUser(token);
  if (error || !data.user) return Response.json({ error: 'Authentication required' }, { status: 401 });
  let body: { confirmation?: string };
  try { body = await request.json(); } catch { return Response.json({ error: 'JSON required' }, { status: 400 }); }
  if (body.confirmation !== 'DELETE') return Response.json({ error: 'Explicit DELETE confirmation required' }, { status: 400 });
  const admin = createClient(url, secret, { auth: { persistSession: false, autoRefreshToken: false } });
  // Revoke sessions before identity deletion. No user ID is ever accepted from the request body.
  const signedOut = await admin.auth.admin.signOut(token, 'global');
  if (signedOut.error) return Response.json({ error: 'Could not revoke sessions; records were preserved' }, { status: 502 });
  const removed = await admin.auth.admin.deleteUser(data.user.id);
  if (removed.error) return Response.json({ error: 'Account deletion could not finish; contact the operator' }, { status: 502 });
  return Response.json({ deleted: true, authAccountDeleted: true }, { headers: { 'Cache-Control': 'no-store' } });
});
