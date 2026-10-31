import {errorResponse,requireUser} from '@/lib/auth';
import {getLedger} from '@/lib/ledger';
export const runtime='nodejs';export const dynamic='force-dynamic';
function cell(value:unknown){const str=String(value??'');const safe=typeof value==='string'&&/^[=+@\-\t\r]/.test(str)?"'"+str:str;return '"'+safe.replaceAll('"','""')+'"';}
export async function GET(request:Request){try{const user=await requireUser(request);const ledger=getLedger(user.id);const kind=new URL(request.url).searchParams.get('kind');let rows:unknown[][];
if(kind==='bets')rows=[['id','sportsbook','event','player','market','selection','market_instrument','odds','contract_price_cents','contract_quantity','entry_fee_cents','stake','placed_at','settled_at','result','payout','notes'],...ledger.bets.map(b=>[b.id,b.sportsbook,b.event,b.player,b.market,b.selection,b.marketInstrument,b.odds,b.contractPriceCents,b.contractQuantity,b.entryFeeCents,b.stake,b.placedAt,b.settledAt,b.result,b.payout,b.notes])];
else rows=[['id','type','sportsbook','amount','date','note','reference','reverses_id','reversed'],...ledger.transactions.map(t=>[t.id,t.type,t.sportsbook,Number(t.amount),t.date,t.note,t.reference,t.reversesId,t.reversed])];
return new Response(rows.map(r=>r.map(cell).join(',')).join('\r\n'),{headers:{'Content-Type':'text/csv; charset=utf-8','Content-Disposition':`attachment; filename="gridiron-${kind==='bets'?'bets':'ledger'}.csv"`,'Cache-Control':'no-store'}});}catch(e){return errorResponse(e);}}
