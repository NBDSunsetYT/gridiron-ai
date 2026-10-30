export async function register(){
 if(process.env.NEXT_RUNTIME==='nodejs'){
  const {configureServerNetwork}=await import('./lib/network');configureServerNetwork();
 }
}
