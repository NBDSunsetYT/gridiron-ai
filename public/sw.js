/* Only public static resources are cached. Private API responses never enter CacheStorage. */
const CACHE = 'gridiron-interface-v8';
const PUBLIC = ['/offline-reader.js', '/offline.html', '/icon.svg', '/icon-192.png', '/icon-512.png', '/apple-touch-icon.png', '/manifest.webmanifest'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PUBLIC)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('gridiron-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/') || url.pathname.startsWith('/signin') || url.pathname.startsWith('/signout')) return;
  if (request.mode === 'navigate') {
    // Do not cache authenticated HTML. Its content may include personal account data.
    event.respondWith(fetch(request, {cache:'no-store'}).catch(async () => (await caches.match('/offline.html')) || new Response('Offline. Reconnect to open GRIDIRON AI.', {status:503,headers:{'Content-Type':'text/plain; charset=utf-8'}})));
    return;
  }
  if (PUBLIC.includes(url.pathname) || url.pathname.startsWith('/_next/static/')) {
    event.respondWith(caches.open(CACHE).then(async cache => {
      const cached = await cache.match(request);
      if (cached) return cached;
      const response = await fetch(request);
      const policy = response.headers.get('cache-control') || '';
      const html = /text\/html/i.test(response.headers.get('content-type') || '');
      if (response.ok && response.type === 'basic' && !html && !/(?:^|,)\s*(?:private|no-store)\b/i.test(policy)) {
        // A full device cache must not turn a successful online request into an error.
        try { await cache.put(request, response.clone()); } catch {}
      }
      return response;
    }).catch(() => fetch(request)));
  }
});
self.addEventListener('message', event => {
  if (event.data === 'CLEAR_CACHES') event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('gridiron-')).map(key => caches.delete(key)))));
});
