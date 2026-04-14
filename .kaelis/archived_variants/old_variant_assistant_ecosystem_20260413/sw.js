// Kaelis Service Worker - PWA离线支持
const CACHE_NAME = 'kaelis-v1';
const STATIC_ASSETS = [
  '/',
  '/pages/dashboard.html',
  '/pages/chat.html',
  '/pages/login.html',
  '/assets/styles/variables.css',
  '/assets/styles/components.css',
  '/assets/styles/animations.css'
];

// 安装时缓存静态资源
self.addEventListener('install', (event) => {
  console.log('[SW] Service Worker 安装中...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] 缓存静态资源');
        return cache.addAll(STATIC_ASSETS);
      })
      .catch((err) => {
        console.error('[SW] 缓存失败:', err);
      })
  );
  self.skipWaiting();
});

// 激活时清理旧缓存
self.addEventListener('activate', (event) => {
  console.log('[SW] Service Worker 激活中...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => {
            console.log('[SW] 删除旧缓存:', name);
            return caches.delete(name);
          })
      );
    })
  );
  self.clients.claim();
});

// 拦截请求并提供缓存
self.addEventListener('fetch', (event) => {
  // 跳过非GET请求
  if (event.request.method !== 'GET') return;
  
  // 跳过API请求
  if (event.request.url.includes('/api/')) return;
  
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // 返回缓存或发起网络请求
        if (response) {
          console.log('[SW] 从缓存返回:', event.request.url);
          return response;
        }
        
        return fetch(event.request)
          .then((networkResponse) => {
            // 缓存新的静态资源
            if (networkResponse.status === 200 && 
                (event.request.url.endsWith('.html') || 
                 event.request.url.endsWith('.css') || 
                 event.request.url.endsWith('.js'))) {
              const clonedResponse = networkResponse.clone();
              caches.open(CACHE_NAME).then((cache) => {
                cache.put(event.request, clonedResponse);
              });
            }
            return networkResponse;
          })
          .catch((err) => {
            console.error('[SW] 网络请求失败:', err);
            // 返回离线页面
            if (event.request.mode === 'navigate') {
              return caches.match('/pages/offline.html');
            }
          });
      })
  );
});

// 后台同步
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-data') {
    console.log('[SW] 执行后台同步');
    event.waitUntil(syncData());
  }
});

// 推送通知
self.addEventListener('push', (event) => {
  console.log('[SW] 收到推送通知');
  const options = {
    body: event.data ? event.data.text() : '新消息',
    icon: '/assets/icons/icon-192x192.png',
    badge: '/assets/icons/badge-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      url: '/pages/notifications.html'
    },
    actions: [
      {
        action: 'open',
        title: '查看'
      },
      {
        action: 'close',
        title: '关闭'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification('Kaelis', options)
  );
});

// 通知点击
self.addEventListener('notificationclick', (event) => {
  console.log('[SW] 通知被点击');
  event.notification.close();
  
  if (event.action === 'open' || !event.action) {
    event.waitUntil(
      clients.openWindow(event.notification.data.url)
    );
  }
});

// 同步数据函数
async function syncData() {
  // 实现数据同步逻辑
  console.log('[SW] 同步数据中...');
}

console.log('[SW] Service Worker 已加载');
