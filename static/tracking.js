(() => {
  const root = document.getElementById('tracking');
  if (!root) return;
  const globalStatus = document.getElementById('tracking-save-state');
  const retryButton = document.getElementById('save-retry');
  const fields = [...root.querySelectorAll('.status-select,.birey')];
  const failed = new Set();
  let pending = 0;
  fields.forEach(el => { el.dataset.saved = el.value; });
  const report = () => {
    if (!globalStatus) return;
    globalStatus.classList.toggle('is-error', failed.size > 0);
    globalStatus.textContent = pending ? 'Kaydediliyor…' : failed.size ? 'Kaydedilemeyen değişiklik var. Tekrar deneyin.' : '✓ Kaydedildi';
    retryButton.hidden = !failed.size;
  };
  const counter = () => {
    const counts = {okudu:0,getirdi:0,tam:0,eksik:0,yok:0};
    root.querySelectorAll('.status-select').forEach(el => { if (el.value in counts) counts[el.value]++; el.dataset.state = el.value; });
    for (const [key,value] of Object.entries(counts)) document.getElementById('say-'+key).textContent = value;
  };
  async function post(url, body) {
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), 15000);
    try {
      const response = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:abort.signal});
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error('save');
      return result;
    } finally { clearTimeout(timer); }
  }
  const payload = (el) => ({sinif_id:Number(root.dataset.class),hafta:root.dataset.week,ogrenci_id:Number(el.closest('.ogrenci').dataset.ogrenci),alan:el.dataset.alan,deger:el.value});
  async function save(el) {
    if (el.disabled) return;
    const state = el.closest('.ogrenci').querySelector('[data-row-state]');
    const value = el.value;
    el.disabled = true; pending++; state.textContent = 'Kaydediliyor…'; state.classList.remove('is-error'); report();
    try {
      await post(el.classList.contains('status-select') ? root.dataset.markUrl : root.dataset.textUrl,payload(el));
      el.dataset.saved = value; failed.delete(el); el.removeAttribute('aria-invalid'); state.textContent = '✓ Kaydedildi';
      if (el.dataset.alan === 'odev_durum') {
        const note = el.closest('td').querySelector('[data-parent-reported]');
        if (note) note.textContent = value ? 'Veli bildirdi · değerlendirildi' : 'Veli bildirdi · onay bekliyor';
      }
    } catch {
      failed.add(el); el.setAttribute('aria-invalid','true'); state.textContent = 'Kaydedilmedi · tekrar deneyin'; state.classList.add('is-error');
    } finally {
      const rowFailed = [...failed].some(field => field.closest('.ogrenci') === el.closest('.ogrenci'));
      state.classList.toggle('is-error',rowFailed);
      if(rowFailed)state.textContent='Kaydedilemeyen alan var · tekrar deneyin';
      el.disabled = false; pending--; counter(); report();
    }
  }
  fields.forEach(el => el.addEventListener('change', () => {
    counter();
    if (el.classList.contains('kitap-sec')) {
      const total = el.selectedOptions[0]?.dataset.sayfa;
      el.closest('label').querySelector('.kitap-toplam').textContent = Number(total) ? '/ '+total+' sayfa' : '';
    }
    save(el);
  }));
  retryButton?.addEventListener('click', () => [...failed].forEach(save));
  root.querySelectorAll('.detail-toggle').forEach(button => button.addEventListener('click', () => {
    const detail = document.getElementById(button.getAttribute('aria-controls'));
    detail.hidden = !detail.hidden;
    button.setAttribute('aria-expanded',String(!detail.hidden));
    button.textContent = detail.hidden ? 'Detay' : 'Kapat';
  }));
  root.querySelectorAll('.toplu').forEach(button => button.addEventListener('click', async () => {
    if (pending || failed.size) { globalStatus.textContent = 'Önce bekleyen değişikliklerin kaydını tamamlayın.'; return; }
    const affected = [...root.querySelectorAll('.status-select')].filter(el => el.dataset.alan === button.dataset.alan);
    button.disabled = true; affected.forEach(el => el.disabled = true); pending++; report();
    try {
      await post(root.dataset.bulkUrl,{sinif_id:Number(root.dataset.class),hafta:root.dataset.week,alan:button.dataset.alan,deger:button.dataset.deger});
      affected.forEach(el => {el.value=button.dataset.deger;el.dataset.saved=el.value;el.closest('.ogrenci').querySelector('[data-row-state]').textContent='✓ Kaydedildi';const note=el.closest('td').querySelector('[data-parent-reported]');if(note)note.textContent='Veli bildirdi · değerlendirildi';});
    } catch { globalStatus.textContent='Toplu işlem kaydedilmedi. Tekrar deneyin.';globalStatus.classList.add('is-error'); }
    finally { button.disabled=false;affected.forEach(el=>el.disabled=false);pending--;counter();if(!globalStatus.classList.contains('is-error'))report(); }
  }));
  window.addEventListener('beforeunload', event => {
    if (pending || failed.size) { event.preventDefault(); event.returnValue=''; }
  });
})();
