import type { NextConfig } from 'next';
const config: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR || '.next',
  output: 'standalone', poweredByHeader: false,
  // Per-route evidence readers enforce 20 MB. Preserve their complete bodies
  // through middleware rather than Next's default 10 MB truncation.
  experimental: {middlewareClientMaxBodySize:'25mb'},
  serverExternalPackages: ['better-sqlite3'],
  async headers(){ return [{source:'/(.*)',headers:[
    {key:'X-Content-Type-Options',value:'nosniff'},
    {key:'X-Frame-Options',value:'DENY'},
    {key:'Referrer-Policy',value:'strict-origin-when-cross-origin'},
    {key:'Permissions-Policy',value:'camera=(), microphone=(), geolocation=()'}
  ]},{source:'/api/:path*',headers:[{key:'Cache-Control',value:'private, no-store'}]},
  {source:'/sw.js',headers:[{key:'Cache-Control',value:'no-cache'},{key:'Service-Worker-Allowed',value:'/'}]}]; }
};
export default config;
