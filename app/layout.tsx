import type {Metadata,Viewport} from 'next';
import './globals.css';
import '../components/screens.css';
export const metadata:Metadata={title:'GRIDIRON AI — NFL Research Terminal',applicationName:'GRIDIRON AI',description:'Evidence-driven NFL research, contract valuation, game simulation, and your private bankroll. Transparent by design.',manifest:'/manifest.webmanifest',other:{'apple-mobile-web-app-capable':'yes'},formatDetection:{telephone:false},appleWebApp:{capable:true,statusBarStyle:'black-translucent',title:'GRIDIRON AI'},icons:{icon:[{url:'/icon.svg',type:'image/svg+xml'},{url:'/icon-192.png',sizes:'192x192',type:'image/png'},{url:'/icon-512.png',sizes:'512x512',type:'image/png'}],apple:[{url:'/apple-touch-icon.png',sizes:'180x180',type:'image/png'}]}};
export const viewport:Viewport={width:'device-width',initialScale:1,viewportFit:'cover',themeColor:'#090d0c'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en" suppressHydrationWarning><body>{children}</body></html>;}
