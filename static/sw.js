self.addEventListener("install", event => {
  event.waitUntil(caches.open("ogrenci-takip-v2").then(cache => cache.addAll(["/login"])));
});

self.addEventListener("message", function (event) {
  const veri = event.data || {};
  if (veri.tur === "haber" && self.registration && self.registration.showNotification) {
    self.registration.showNotification(veri.baslik || "Öğrenci takip", {
      body: veri.metin || "",
      icon: "/static/icon-192.png"
    });
  }
});
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
