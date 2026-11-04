/** Server-only immutable objects. Identity includes the full verified pointer.
 * Every caller gets a copy so market valuation cannot mutate saved evidence. */
import {performanceEvent} from './metrics';
export function immutableCache(limitBytes=16_000_000,maxEntries=24){
 const entries=new Map<string,{json:string;bytes:number;until:number}>(),pending=new Map<string,Promise<string>>();let used=0;
 return async<T>(key:string,load:()=>Promise<T>,size:(v:T)=>number):Promise<T>=>{
  const cached=entries.get(key);if(cached&&cached.until>Date.now()){performanceEvent('immutable_object','hit');return JSON.parse(cached.json);}
  if(cached){used-=cached.bytes;entries.delete(key);}
  let task=pending.get(key);if(!task){performanceEvent('immutable_object','miss');task=(async()=>{const value=await load(),json=JSON.stringify(value),bytes=Math.max(size(value),Buffer.byteLength(json)*2);if(bytes<=limitBytes){while(entries.size&&(used+bytes>limitBytes||entries.size>=maxEntries)){const first=entries.keys().next().value!;used-=entries.get(first)!.bytes;entries.delete(first);}entries.set(key,{json,bytes,until:Date.now()+300000});used+=bytes;}return json;})();pending.set(key,task);void task.finally(()=>pending.delete(key)).catch(()=>{});}else performanceEvent('immutable_object','single_flight');
  return JSON.parse(await task);
 };
}
