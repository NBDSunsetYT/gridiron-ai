import {cpSync,existsSync,readFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';

export function standalonePaths(root=process.cwd(),dist=process.env.NEXT_DIST_DIR||'.next'){
 if(!/^[a-zA-Z0-9._-]+$/.test(dist)||dist==='.'||dist==='..')throw Error('Invalid Next build directory');
 const build=resolve(root,dist),bundle=join(build,'standalone');
 return{root,dist,build,bundle,server:join(bundle,'server.js')};
}
export function prepareStandalone(root=process.cwd(),dist){
 const paths=standalonePaths(root,dist);
 if(!existsSync(paths.server))throw Error('Standalone server is missing; run the complete Next.js build first.');
 const required=JSON.parse(readFileSync(join(paths.build,'required-server-files.json'),'utf8'));
 if(required.config.output!=='standalone'||required.config.distDir!==paths.dist)throw Error('Next standalone configuration does not match this build.');
 cpSync(join(paths.build,'static'),join(paths.bundle,paths.dist,'static'),{recursive:true});
 if(existsSync(join(root,'public')))cpSync(join(root,'public'),join(paths.bundle,'public'),{recursive:true});
 return paths;
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 prepareStandalone();console.log('Standalone public assets and versioned Next static files prepared.');
}
