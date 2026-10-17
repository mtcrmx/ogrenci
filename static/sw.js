self.addEventListener("install", event => {
  event.waitUntil(caches.open("ogrenci-takip-v3").then(cache => cache.addAll(["/login"])));
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(self.clients.claim());
});

function haberGoster(veri) {
  const baslik = (veri && veri.baslik) || "Öğrenci takip";
  return self.registration.showNotification(baslik, {
    body: (veri && veri.metin) || "Yeni bir mesaj var.",
    icon: "/static/icon-192.png",
    badge: "/static/icon-192.png",
    tag: "veli-haber-" + Date.now(),
    renotify: true,
    silent: false,
    vibrate: [400, 200, 400, 200, 800],
    requireInteraction: true,
    data: { url: (veri && veri.url) || "/veli" },
  });
}

self.addEventListener("message", function (event) {
  const veri = event.data || {};
  if (veri.tur === "haber" && self.registration && self.registration.showNotification) {
    event.waitUntil(haberGoster(veri));
  }
});

self.addEventListener("push", function (event) {
  let veri = {};
  try {
    veri = event.data ? event.data.json() : {};
  } catch (e) {
    veri = { metin: event.data ? event.data.text() : "" };
  }
  event.waitUntil(haberGoster(veri));
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/veli";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (list) {
      for (let i = 0; i < list.length; i++) {
        const pencere = list[i];
        if (pencere.url.indexOf("/veli") !== -1 && "focus" in pencere) {
          return pencere.navigate(url).then(function (client) { return (client || pencere).focus(); });
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
