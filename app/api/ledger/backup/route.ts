import {errorResponse,readJsonObject,guardMutation,rateLimit,requireUser} from '@/lib/auth';
import {getLedger,getSettings} from '@/lib/ledger';import {encryptBackup} from '@/lib/backups';
import {getDb} from '@/lib/db';import {getPreferences} from '@/lib/research-store';
export const runtime='nodejs';export const dynamic='force-dynamic';
export async function POST(request:Request){try{guardMutation(request);const user=await requireUser(request);rateLimit('backup:'+user.id,3,60_000);const body=await readJsonObject(request);const db=getDb();
const tables=['markets','research_records','contract_quotes','prediction_snapshots','contract_settlements','injury_history','notification_history','simulation_jobs','simulation_inputs','paper_positions','watchlists','reports','warehouse_records','conversations','conversation_messages'] as const;
const research=Object.fromEntries(tables.map(table=>[table,db.prepare(`SELECT * FROM ${table} WHERE user_id=?`).all(user.id)]));
const rawLedger={journal:db.prepare('SELECT * FROM journal WHERE user_id=?').all(user.id),postings:db.prepare('SELECT p.* FROM postings p JOIN journal j ON j.id=p.journal_id WHERE j.user_id=?').all(user.id),bets:db.prepare('SELECT * FROM bets WHERE user_id=?').all(user.id),audit:db.prepare('SELECT * FROM audit WHERE user_id=?').all(user.id)};
const payload={version:2,createdAt:new Date().toISOString(),email:user.email,ledger:getLedger(user.id),rawLedger,settings:getSettings(user.id),preferences:getPreferences(user.id),research};
return Response.json(await encryptBackup(payload,body.password),{headers:{'Content-Disposition':'attachment; filename="gridiron-backup.encrypted.json"','Cache-Control':'no-store'}});}catch(e){return errorResponse(e);}}
