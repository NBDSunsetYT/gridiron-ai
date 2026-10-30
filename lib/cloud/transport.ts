/** Server-only transport adaptations for bounded hosted request/response bodies.
 * Complete artifacts remain in owned persistent records; only their transport
 * representation changes. Call job compaction after provenance verification. */
export function compactApiEnabled(){return ['1','true'].includes(process.env.GRIDIRON_COMPACT_API??'');}

export function compactSimulationResult(jobId:string,result:Record<string,any>){
 if(!compactApiEnabled()||!result?.model)return result;
 const model:Record<string,any>={};
 for(const key of ['version','sha256','asOf','source','teams','modelOptions','dataAvailabilityVerified'])if(result.model[key]!==undefined)model[key]=result.model[key];
 return{...result,model,modelJobId:jobId,modelReferenceOnly:true};
}

export function compactSimulationJob(job:Record<string,any>){
 if(!compactApiEnabled()||!job.result)return job;
 return{...job,result:compactSimulationResult(job.id,job.result)};
}

/** Large exports can stream the same JSON without a buffered platform response.
 * Never cache private account payloads, including streamed encrypted exports. */
export function cloudJson(data:unknown,status=200):Response{
 const headers={'Content-Type':'application/json; charset=utf-8','Cache-Control':'private, no-store'};
 if(!compactApiEnabled())return Response.json(data,{status,headers});
 const raw=JSON.stringify(data);
 if(Buffer.byteLength(raw,'utf8')<=1_000_000)return new Response(raw,{status,headers});
 const bytes=new TextEncoder().encode(raw);let offset=0;
 const stream=new ReadableStream<Uint8Array>({pull(controller){if(offset>=bytes.length){controller.close();return;}const end=Math.min(offset+64*1024,bytes.length);controller.enqueue(bytes.subarray(offset,end));offset=end;}});
 return new Response(stream,{status,headers});
}
