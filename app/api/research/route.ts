import { NextResponse } from 'next/server';
import { requireUser,errorResponse } from '@/lib/auth';
import {readInjuries} from '@/lib/injuries';
export async function GET(request:Request) {
  try {const user=await requireUser(request);const injuryRecords=readInjuries(user.id).records;return NextResponse.json({games:[],injuries:injuryRecords,injurySource:'manual_user_verified',weather:[],players:[],status:injuryRecords.length?'partial':'unavailable',message:'No live score, injury, player usage or weather provider is configured. Injury citations, where present, are user-verified records rather than fetched live reports. Imported market event names are not a verified NFL schedule.',checkedAt:new Date().toISOString()},{headers:{'Cache-Control':'private,no-store'}});}catch(e){return errorResponse(e);}
}
