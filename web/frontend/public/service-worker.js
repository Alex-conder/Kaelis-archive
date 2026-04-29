const CACHE_NAME = 'kaelis-v1'
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/assets/icon-192.png',
  '/assets/icon-512.png',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request)
    })
  )
})

// ====== Push Notifications ======
self.addEventListener('push', (event) => {
  if (!event.data) return

  const data = event.data.json()
  const options = {
    body: data.body || 'Kaelis 新通知',
    icon: data.icon || '/assets/icon-192.png',
    tag: data.tag || 'default',
    requireInteraction: true,
  }

  event.waitUntil(
    self.registration.showNotification(data.title || 'Kaelis', options)
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  event.waitUntil(
    self.clients.openWindow('/')
  )
})
