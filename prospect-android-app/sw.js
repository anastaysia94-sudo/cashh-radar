'use strict';
const CACHE='cashh-radar-prospects-v7-truthful-timing-20260912';
const FILES=[
  './',
  'index.html',
  'easy.html',
  'easy.css',
  'easy-v3.css',
  'easy-v4.css',
  'prospects.js',
  'data/p500-gz-1.js',
  'data/p500-gz-2.js',
  'data/p500-gz-3.js',
  'data/p500-gz-4.js',
  'data/p500-loader.js',
  'bootstrap-v4.js',
  'easy-core.js',
  'easy-v4-core.js',
  'easy-v4-policy.js',
  'easy-ui.js',
  'easy-send.js',
  'easy-v3.js',
  'easy-v4-ui.js',
  'easy-v4-image.js',
  'prospect-bridge.js',
  'server-performance.js',
  'pwa-runtime.js',
  'manifest.webmanifest',
  'icon.svg'
];

self.addEventListener('install',event=>{
  event.waitUntil(
    caches.open(CACHE)
      .then(cache=>cache.addAll(FILES))
      .then(()=>self.skipWaiting())
  );
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key))))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET')return;
  const url=new URL(event.request.url);
  if(url.origin!==self.location.origin)return;

  // Authenticated/user-specific APIs must never be cached by the PWA. Let the
  // browser perform a normal network request so sessions and state stay isolated.
  if(url.pathname.startsWith('/api/'))return;

  if(event.request.mode==='navigate'){
    event.respondWith(
      fetch(event.request)
        .then(response=>{
          const copy=response.clone();
          caches.open(CACHE).then(cache=>cache.put(event.request,copy));
          return response;
        })
        .catch(()=>caches.match(event.request).then(hit=>hit||caches.match('index.html')))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then(hit=>{
      const network=fetch(event.request).then(response=>{
        if(response&&response.ok){
          const copy=response.clone();
          caches.open(CACHE).then(cache=>cache.put(event.request,copy));
        }
        return response;
      });
      return hit||network;
    })
  );
});
