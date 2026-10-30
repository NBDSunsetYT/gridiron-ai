// @ts-nocheck -- Deployment tooling has its own pinned dependency/lockfile.
import {defineRailway,project,service,preserve} from 'railway/iac';

// Partial ownership protects unrelated services in an existing Railway project.
export const partial='gridiron-pwa';
export default defineRailway(ctx=>{
 const quant=service('quant',{
  build:{builder:'DOCKERFILE',dockerfilePath:'deployment/railway/quant.Dockerfile'},
  healthcheck:'/health',healthcheckTimeout:120,replicas:1,
  deploy:{restartPolicyType:'ON_FAILURE',restartPolicyMaxRetries:5,drainingSeconds:'240'},
  env:{PORT:'8080',SIMULATION_SERVICE_TOKEN:preserve()},
 });
 const web=service('web',{
  build:{builder:'DOCKERFILE',dockerfilePath:'deployment/railway/web.Dockerfile'},
  healthcheck:'/api/health',healthcheckTimeout:120,replicas:1,
  deploy:{restartPolicyType:'ON_FAILURE',restartPolicyMaxRetries:5,drainingSeconds:'240'},
  env:{
   NODE_ENV:'production',PORT:'8080',HOSTNAME:'0.0.0.0',
   DATA_BACKEND:'supabase',GRIDIRON_CLOUD_ONLY:'1',DATA_DIR:'/tmp/gridiron-hosted-cache',
   SUPABASE_URL:preserve(),SUPABASE_PUBLISHABLE_KEY:preserve(),
   SIMULATION_SERVICE_TOKEN:preserve(),
   APP_URL:preserve(),OPENAI_API_KEY:preserve(),OPENAI_MODEL:preserve(),
   ODDS_API_KEY:preserve(),DEVICE_TOKEN_ENCRYPTION_KEY:preserve(),
   SIMULATION_SERVICE_URL:'http://quant.railway.internal:8080',
  },
 });
 return project(ctx.projectName??'GRIDIRON AI',{resources:[quant,web]});
});
