const CACHE_NAME = 'bs-textile-v1';

// Страницы и ресурсы для кэша
const PRECACHE = [
  '/menu',
  '/login',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/apple-touch-icon.png',
];

// При установке — кэшируем базовые страницы
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(PRECACHE).catch(() => {});
    })
  );
  self.skipWaiting();
});

// При активации — удаляем старые кэши
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Стратегия: сначала сеть, при ошибке — кэш
self.addEventListener('fetch', event => {
  // Пропускаем API запросы — они всегда должны быть свежими
  if (event.request.url.includes('/api/')) return;

  // Пропускаем POST запросы
  if (event.request.method !== 'GET') return;

  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Кэшируем успешные GET ответы
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => {
        // Сеть недоступна — отдаём из кэша
        return caches.match(event.request).then(cached => {
          if (cached) return cached;
          // Если нет в кэше — отдаём страницу входа
          return caches.match('/login');
        });
      })
  );
});
