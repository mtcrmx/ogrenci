(() => {
  const menu = document.getElementById('app-menu');
  const toggle = document.querySelector('[data-app-menu-toggle]');
  const scrim = document.querySelector('.app-scrim');
  const mobile = matchMedia('(max-width:760px)');
  const workspace = document.querySelector('.app-workspace');
  const setOpen = (open, focus = false) => {
    if (!menu) return;
    open = open && mobile.matches;
    menu.classList.toggle('is-open', open);
    menu.inert = mobile.matches && !open;
    if (workspace) workspace.inert = open;
    document.body.classList.toggle('app-menu-open', open);
    toggle?.setAttribute('aria-expanded', String(open));
    if (scrim) scrim.hidden = !open;
    if (open) menu.querySelector('a')?.focus();
    else if (focus) toggle?.focus();
  };
  window.appMenuToggle = () => setOpen(!menu?.classList.contains('is-open'));
  window.appMenuClose = () => setOpen(false);
  toggle?.addEventListener('click', window.appMenuToggle);
  document.querySelectorAll('[data-app-menu-close]').forEach(el => el.addEventListener('click', () => setOpen(false, true)));
  menu?.addEventListener('click', e => { if (e.target.closest('a')) setOpen(false); });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && menu?.classList.contains('is-open')) setOpen(false, true);
    if (e.key === 'Tab' && menu?.classList.contains('is-open')) {
      const items = [...menu.querySelectorAll('a,button,summary')].filter(el => el.getClientRects().length);
      if (e.shiftKey && document.activeElement === items[0]) { e.preventDefault(); items.at(-1)?.focus(); }
      else if (!e.shiftKey && document.activeElement === items.at(-1)) { e.preventDefault(); items[0]?.focus(); }
    }
  });
  mobile.addEventListener('change', () => setOpen(false));
  setOpen(false);
  const search = document.getElementById('ara');
  const applySearch = () => {
    if (typeof window.filtrele === 'function') window.filtrele();
    else if (typeof window.filterAnalysis === 'function') window.filterAnalysis();
    else document.querySelectorAll('#tracking .ogrenci').forEach(row => row.hidden = !row.querySelector('.student-name strong').textContent.toLocaleLowerCase('tr').includes(search.value.toLocaleLowerCase('tr')));
  };
  search?.addEventListener('input', applySearch);
  document.querySelector('.app-student-search')?.addEventListener('submit', event => {
    if (document.querySelector('#tracking,.dashboard-shell,#analysis-view')) { event.preventDefault(); applySearch(); }
  });
  if (search?.value) applySearch();
  document.getElementById('app-class-select')?.addEventListener('change', e => {
    const url = new URL(location.href);
    const key = url.pathname === '/analiz' || url.searchParams.has('sinif_id') ? 'sinif_id' : 'sinif';
    url.searchParams.delete(key === 'sinif' ? 'sinif_id' : 'sinif');
    url.searchParams.set(key, e.target.value);
    // Pages without a class-level destination return to the selected class dashboard.
    if (!['/dashboard','/haftalik-takip','/analiz','/analiz-merkezi','/karne'].includes(url.pathname)) {
      const destination = new URL(document.querySelector('.app-student-search')?.action || '/dashboard',location.href);
      destination.searchParams.set(destination.pathname === '/analiz' ? 'sinif_id' : 'sinif',e.target.value);
      location.href = destination.href;
    } else location.href = url.href;
  });
  const sections = [...document.querySelectorAll('[data-parent-section]')];
  if (!sections.length) return;
  const aliases = {kitaplar:'hafta',notlar:'mesajlar',gorusme:'mesajlar',rozetler:'raporlar','kitap-kazanimlari':'hafta','lgs-hedefi':'genel'};
  const titles = {genel:'Ana sayfa',hafta:'Ödev ve kitap',mesajlar:'Mesajlar',raporlar:'Raporlar'};
  const showSection = () => {
    const hash = location.hash.slice(1) || 'genel';
    const key = aliases[hash] || (titles[hash] ? hash : 'genel');
    sections.forEach(el => el.hidden = el.dataset.parentSection !== key);
    document.querySelectorAll('[data-parent-nav]').forEach(link => {
      const active = link.dataset.parentNav === key;
      link.classList.toggle('is-current', active);
      if (active) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current');
    });
    const heading = document.getElementById('parent-page-title');
    if (heading) heading.textContent = titles[key];
    setOpen(false);
  };
  window.addEventListener('hashchange', () => { showSection(); window.scrollTo({top:0,behavior:'instant'}); });
  showSection();
})();
