import {sportsDataBridgeConfiguration} from '@/lib/sportsbook-reference/bridge';
export const runtime='nodejs';export const dynamic='force-dynamic';
export async function GET(request:Request){
 const sport=new URL(request.url).searchParams.get('sport')??'NFL';
 const send=(body:unknown,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
 if(!['NFL','CFB'].includes(sport))return send({error:'Choose NFL or CFB.'},400);
 const unavailable=(message:string)=>({sport,status:'unavailable',provider:null,items:[],diagnostic:{message},primaryProvider:'PropLine',fallbackProvider:'ParlayAPI',fallbackVerified:false});
 const problem=sportsDataBridgeConfiguration();if(problem)return send(unavailable('The Render prop gateway is not connected. PropLine requires its own free API key on Render; ParlayAPI access remains unverified.'));
 try{
  const response=await fetch(new URL('/data/props/'+sport,process.env.GRIDIRON_RENDER_DATA_URL!),{headers:{Authorization:'Bearer '+process.env.GRIDIRON_DATA_BRIDGE_TOKEN},cache:'no-store',redirect:'error',signal:AbortSignal.timeout(25000)});
  const raw=await response.text();if(Buffer.byteLength(raw)>8_000_000||raw.includes(process.env.GRIDIRON_DATA_BRIDGE_TOKEN!))throw Error();
  const value=JSON.parse(raw);if(!response.ok||value.sport!==sport||!Array.isArray(value.items)||value.items.length>10000||value.items.some((r:any)=>!['PropLine','ParlayAPI'].includes(r.provider)||r.sport!==sport||r.dataFamily!=='sportsbook_reference'||r.draftKingsPredictionsEquivalent!==false))throw Error();
  return send(value);
 }catch{return send(unavailable('The prop gateway could not supply a verified response. No fallback price was substituted.'));}
}
