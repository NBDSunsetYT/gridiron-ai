/** Finite, visibility-aware status polling. Work cannot overlap itself. */
export function pollResearch(work:()=>Promise<boolean|void>,intervalMs:number,maxAttempts=20){
 let stopped=false,attempts=0,failures=0;const end=Date.now()+30*60000;let timer:ReturnType<typeof setTimeout>;
 const tick=async()=>{if(stopped||attempts>=maxAttempts||Date.now()>end)return;if(document.visibilityState==='visible'){attempts++;try{const ok=await work();failures=ok===false?failures+1:0;}catch{failures++;}}if(!stopped)timer=setTimeout(tick,Math.min(300000,intervalMs*2**Math.min(failures,4)));};
 timer=setTimeout(tick,intervalMs);return()=>{stopped=true;clearTimeout(timer);};
}
