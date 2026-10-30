import {requireUser,errorResponse,ApiError} from '@/lib/auth';
import {getLedger,getSettings} from '@/lib/ledger';
import {buildFinancialReport,type ReportPeriod} from '@/lib/reports';
export const runtime='nodejs';export const dynamic='force-dynamic';
export async function GET(request:Request){try{const user=await requireUser(request),q=new URL(request.url).searchParams;let report;try{report=buildFinancialReport(getLedger(user.id),{timezone:getSettings(user.id).timezone,period:(q.get('period')||'month') as ReportPeriod,anchor:q.get('anchor')||undefined,sportsbook:q.get('sportsbook')||'all'});}catch(e){throw new ApiError(e instanceof Error?e.message:'Invalid report request.');}return Response.json(report,{headers:{'Cache-Control':'private,no-store'}});}catch(e){return errorResponse(e);}}
