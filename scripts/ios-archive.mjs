/** Private development/ad-hoc IPA only. No App Store/TestFlight distribution. */
import {existsSync,mkdirSync,readFileSync,writeFileSync,readdirSync,copyFileSync,mkdtempSync,rmSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {resolve,join} from 'node:path';
import {tmpdir} from 'node:os';
import {createHash,randomBytes} from 'node:crypto';
const require=createRequire(import.meta.url),plist=require('plist');
if(process.platform!=='darwin')throw Error('A genuine signed IPA requires macOS with Xcode/iOS SDK. This Linux host cannot build or sign one. No IPA has been generated.');
const team=process.env.APPLE_TEAM_ID,device=process.env.APPLE_DEVICE_UDID,method=process.env.GRIDIRON_IOS_EXPORT_METHOD||'debugging';
if(!team||!/^[A-Z0-9]{10}$/.test(team)||!device||!/^[A-Za-z0-9-]{16,64}$/.test(device))throw Error('Provide APPLE_TEAM_ID and your personal APPLE_DEVICE_UDID through your local environment. Configure signing in Xcode first.');
if(!['debugging','release-testing'].includes(method))throw Error('Only private development/debugging or ad-hoc/release-testing export is allowed; App Store/TestFlight export is excluded.');
if(process.env.GRIDIRON_ALLOW_APPLE_SIGNING!=='1')throw Error('Apple signing is required. After configuring your Apple account and device profile in Xcode, set GRIDIRON_ALLOW_APPLE_SIGNING=1 to authorize this local signing operation.');
const run=(command,args,capture=false)=>{const result=spawnSync(command,args,{encoding:'utf8',stdio:capture?'pipe':'inherit',env:process.env});if(result.status!==0)throw Error(`${command} did not complete. Review its local error; no valid IPA is claimed.`);return result.stdout;};
run('xcodebuild',['-version']);run(process.execPath,['scripts/ios-prepare.mjs']);
const preparation=JSON.parse(readFileSync('native/preparation.json','utf8'));if(!preparation.configured)throw Error('The actual HTTPS backend must be configured before a private device release.');
const output=resolve('artifacts/ios',`build-${new Date().toISOString().replace(/[:.]/g,'-')}-${randomBytes(4).toString('hex')}`),archive=join(output,'GRIDIRON-AI.xcarchive'),exportPath=join(output,'private-export');mkdirSync(output,{recursive:true,mode:0o700});
run('xcodebuild',['-project','ios/App/App.xcodeproj','-scheme','App','-configuration','Release','-destination','generic/platform=iOS','-archivePath',archive,`DEVELOPMENT_TEAM=${team}`,'CODE_SIGN_STYLE=Automatic','archive']);
const options=join(output,'ExportOptions.plist');writeFileSync(options,plist.build({method,destination:'export',signingStyle:'automatic',teamID:team,uploadSymbols:false}));
run('xcodebuild',['-exportArchive','-archivePath',archive,'-exportPath',exportPath,'-exportOptionsPlist',options]);
const file=readdirSync(exportPath).find(name=>name.endsWith('.ipa'));if(!file)throw Error('Xcode returned no IPA; no installable artifact is claimed.');
const ipa=join(output,'GRIDIRON-AI-private.ipa');copyFileSync(join(exportPath,file),ipa);
const verify=mkdtempSync(join(tmpdir(),'gridiron-ipa-verify-'));
try{
 run('unzip',['-q',ipa,'-d',verify]);const payload=join(verify,'Payload'),app=readdirSync(payload).find(name=>name.endsWith('.app'));if(!app)throw Error('Exported IPA has no native application bundle.');const appPath=join(payload,app);
 run('codesign',['--verify','--deep','--strict',appPath]);const profile=plist.parse(run('security',['cms','-D','-i',join(appPath,'embedded.mobileprovision')],true));
 if(!(profile.TeamIdentifier||[]).includes(team)||!(profile.ProvisionedDevices||[]).includes(device)||new Date(profile.ExpirationDate)<=new Date())throw Error('Signing profile does not match the team, personal device or validity period. The IPA must not be installed.');
 if(preparation.pushCapability&&profile.Entitlements?.['aps-environment']!==preparation.apnsEnvironment)throw Error('The exported Apple APNs environment does not match the native configuration. Rebuild with the correct GRIDIRON_APNS_ENV.');
 const appInfo=plist.parse(run('plutil',['-convert','xml1','-o','-',join(appPath,'Info.plist')],true));if(appInfo.CFBundleIdentifier!==preparation.bundleId)throw Error('Exported bundle identifier does not match the configured personal app.');
 const report={artifact:'GRIDIRON-AI-private.ipa',method,bundleId:preparation.bundleId,sha256:createHash('sha256').update(readFileSync(ipa)).digest('hex'),signatureVerified:true,personalDeviceProvisioningVerified:true,profileExpires:new Date(profile.ExpirationDate).toISOString(),physicalInstallation:'not performed by archive script',createdAt:new Date().toISOString()};writeFileSync(join(output,'verification.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}catch(error){rmSync(ipa,{force:true});throw error;}finally{rmSync(verify,{recursive:true,force:true});}
