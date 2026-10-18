(() => {
  const host = document.getElementById('parent-activity');
  if (!host) return;
  const content = document.getElementById('parent-activity-content');
  const status = document.getElementById('parent-activity-status');
  const more = document.getElementById('parent-activity-more');
  let filter = 'all', expanded = false, busy = false;
  let lastHtml = content.innerHTML.trim();
  function apply() {
    let shown = 0;
    content.querySelectorAll('[data-kind]').forEach(item => {
      const match = filter === 'all' || item.dataset.kind === filter;
      item.hidden = !match || (!expanded && shown >= 8);
      if (match) shown++;
    });
    more.hidden = shown <= 8;
    more.textContent = expanded ? 'Daha az göster' : `Diğer kayıtları göster (${shown - 8})`;
    host.querySelectorAll('[data-feed-filter]').forEach(button => button.setAttribute('aria-pressed',String(button.dataset.feedFilter === filter)));
    document.getElementById('parent-filter-empty').hidden = shown > 0 || filter === 'all';
  }
  host.addEventListener('click', event => {
    const button = event.target.closest('[data-feed-filter]');
    if (button) { filter=button.dataset.feedFilter; expanded=false; apply(); }
  });
  more.addEventListener('click', () => { expanded=!expanded; apply(); });
  async function refresh() {
    if (busy || document.hidden || content.contains(document.activeElement)) return;
    busy=true;
    try {
      const response=await fetch('/veli/akis',{cache:'no-store',headers:{Accept:'text/html'}});
      if (response.status===401) { status.textContent='Oturumunuz sona erdi. Yeniden giriş yapın.'; return; }
      if (!response.ok || response.redirected) throw new Error('refresh');
      const html=await response.text();
      if (lastHtml!==html.trim()) { lastHtml=html.trim(); content.innerHTML=html; apply(); }
      status.textContent='Güncel · Yeni bilgiler otomatik görünür';
    } catch { status.textContent='Bağlantı bekleniyor · Mevcut bilgiler gösteriliyor'; }
    finally { busy=false; }
  }
  document.addEventListener('visibilitychange',refresh);
  window.addEventListener('focus',refresh);
  document.getElementById('parent-refresh').addEventListener('click',refresh);
  setInterval(refresh,10000);
  apply();
})();
