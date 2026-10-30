import { getDb } from './db';
import type { Market } from './providers';
export function readMarkets(userId:string):Market[] {
  const rows=getDb().prepare('SELECT data FROM markets WHERE user_id=? ORDER BY created_at DESC LIMIT 5000').all(userId) as {data:string}[];
  const seen=new Set<string>();
  return rows.map(r=>JSON.parse(r.data) as Market).filter(m=>{
    const k=[m.event,m.selection,m.market,m.line,m.sportsbook,m.source].join('|');
    if(seen.has(k))return false;seen.add(k);return true;
  });
}
