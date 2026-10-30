import type {CapacitorConfig} from '@capacitor/cli';
import {trustedNativeOrigin} from './lib/native/policy';
const raw=process.env.GRIDIRON_NATIVE_URL;
const origin=raw?trustedNativeOrigin(raw):null;
const config:CapacitorConfig={
  appId:process.env.GRIDIRON_IOS_BUNDLE_ID||'ai.gridiron.personal',
  appName:'GRIDIRON AI',webDir:'native/www',loggingBehavior:'none',
  server:origin?{url:origin,cleartext:false,allowNavigation:[new URL(origin).hostname]}:undefined,
  ios:{contentInset:'automatic',allowsLinkPreview:false,webContentsDebuggingEnabled:false,limitsNavigationsToAppBoundDomains:true},
  plugins:{SplashScreen:{launchShowDuration:1500,launchAutoHide:true,backgroundColor:'#090d0c',showSpinner:false},StatusBar:{style:'DARK',backgroundColor:'#090d0c'}}
};
export default config;
