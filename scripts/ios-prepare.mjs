/** Configure a private iPhone build. No database or signing material is modified. */
import {readFileSync,writeFileSync,existsSync,mkdirSync} from 'node:fs';
import {createRequire} from 'node:module';
import {spawnSync} from 'node:child_process';
import {resolve} from 'node:path';
const require=createRequire(import.meta.url),plist=require('plist'),xcode=require('xcode');
const optional=process.argv.includes('--unconfigured');
const raw=process.env.GRIDIRON_NATIVE_URL;
let origin=null;
if(raw){const url=new URL(raw);if(url.protocol!=='https:'||url.username||url.password||url.search||url.hash||url.pathname!=='/'||['localhost','127.0.0.1','0.0.0.0','[::1]'].includes(url.hostname))throw Error('GRIDIRON_NATIVE_URL must be the actual HTTPS application origin, with no paths, credentials or loopback hosts.');origin=url.origin;}
else if(!optional)throw Error('Set GRIDIRON_NATIVE_URL to your actual deployed HTTPS application before preparing a device build. No placeholder URL is substituted.');
const bundle=process.env.GRIDIRON_IOS_BUNDLE_ID||'ai.gridiron.personal';
if(!/^[A-Za-z][A-Za-z0-9-]*(\.[A-Za-z0-9-]+){2,}$/.test(bundle))throw Error('Use a valid reverse-domain iOS bundle identifier.');
const cli='node_modules/@capacitor/cli/bin/capacitor';
if(!existsSync(cli))throw Error('Install locked npm dependencies before preparing iOS.');
const cap=spawnSync(process.execPath,[cli,existsSync('ios/App/App.xcodeproj')?'sync':'add','ios',...(!existsSync('ios/App/App.xcodeproj')?['--packagemanager','SPM']:[])],{stdio:'inherit',env:process.env});
if(cap.status!==0)throw Error('Capacitor iOS preparation failed. Existing user data was not changed.');
const infoPath='ios/App/App/Info.plist',info=plist.parse(readFileSync(infoPath,'utf8'));
const push=process.env.GRIDIRON_IOS_PUSH==='1',apns=process.env.GRIDIRON_APNS_ENV||'development';
if(!['development','production'].includes(apns))throw Error('GRIDIRON_APNS_ENV must be development or production.');
Object.assign(info,{GRIDIRON_API_ORIGIN:origin||'',GRIDIRON_PUSH_ENABLED:push,GRIDIRON_APNS_ENV:apns,WKAppBoundDomains:origin?[new URL(origin).hostname]:[],NSAppTransportSecurity:{NSAllowsArbitraryLoads:false,NSAllowsArbitraryLoadsInWebContent:false,NSAllowsLocalNetworking:false},CFBundleURLTypes:[{CFBundleURLName:bundle,CFBundleURLSchemes:['gridironai']}],UIRequiredDeviceCapabilities:['arm64'],UISupportedInterfaceOrientations:['UIInterfaceOrientationPortrait'],UIStatusBarStyle:'UIStatusBarStyleLightContent'});
if(push)info.UIBackgroundModes=['remote-notification'];else delete info.UIBackgroundModes;
writeFileSync(infoPath,plist.build(info));
writeFileSync('ios/App/App/Gridiron.entitlements',plist.build(push?{'aps-environment':apns}:{}));
const projectPath='ios/App/App.xcodeproj/project.pbxproj',project=xcode.project(projectPath);project.parseSync();
const group=project.findPBXGroupKey({path:'App'}),target=project.getFirstTarget().uuid;
for(const file of ['GridironNative.swift'])if(!project.hasFile(file))project.addSourceFile(file,{target},group);
for(const file of ['PrivacyInfo.xcprivacy'])if(!project.hasFile(file))project.addResourceFile(file,{target},group);
let source=project.writeSync();source=source.replace(/PRODUCT_BUNDLE_IDENTIFIER = [^;]+;/g,`PRODUCT_BUNDLE_IDENTIFIER = ${bundle};`).replace(/TARGETED_DEVICE_FAMILY = [^;]+;/g,'TARGETED_DEVICE_FAMILY = 1;').replace(/MARKETING_VERSION = [^;]+;/g,'MARKETING_VERSION = 4.0;');
source=source.replace(/(PRODUCT_BUNDLE_IDENTIFIER = [^;]+;)/g,'$1\n\t\t\t\tCODE_SIGN_ENTITLEMENTS = App/Gridiron.entitlements;');
// Repeated prepare remains idempotent.
source=source.replace(/(\n\s*CODE_SIGN_ENTITLEMENTS = App\/Gridiron.entitlements;){2,}/g,'\n\t\t\t\tCODE_SIGN_ENTITLEMENTS = App/Gridiron.entitlements;');
source=source.replace(/\s+(fileEncoding|explicitFileType|lastKnownFileType) = undefined;/g,'').replace(/lastKnownFileType = unknown;/g,'lastKnownFileType = text.xml;');
writeFileSync(projectPath,source);
const scene='ios/App/App/SceneDelegate.swift';writeFileSync(scene,readFileSync(scene,'utf8').replace('window?.rootViewController = CAPBridgeViewController()','window?.rootViewController = GridironRootViewController()'));
const storyboard='ios/App/App/Base.lproj/Main.storyboard';writeFileSync(storyboard,readFileSync(storyboard,'utf8').replace('customClass="CAPBridgeViewController" customModule="Capacitor"','customClass="GridironRootViewController" customModule="App" customModuleProvider="target"'));
const appDelegate='ios/App/App/AppDelegate.swift';let app=readFileSync(appDelegate,'utf8');if(!app.includes('didRegisterForRemoteNotificationsWithDeviceToken'))app=app.replace(/\n}\s*$/,'\n    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {\n        NotificationCenter.default.post(name: .capacitorDidRegisterForRemoteNotifications, object: deviceToken)\n    }\n    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {\n        NotificationCenter.default.post(name: .capacitorDidFailToRegisterForRemoteNotifications, object: error)\n    }\n}\n');writeFileSync(appDelegate,app);
const status={configured:Boolean(origin),origin,bundleId:bundle,pushCapability:push,apnsEnvironment:push?apns:null,keychain:'approved HttpOnly cookies; device-only while unlocked',nativeCompilation:'not performed by prepare',signing:'requires macOS, Xcode, Apple team and personal device provisioning'};
mkdirSync('native',{recursive:true});writeFileSync('native/preparation.json',JSON.stringify(status,null,2)+'\n');console.log(JSON.stringify(status));
