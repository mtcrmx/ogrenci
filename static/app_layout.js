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
  const normalize = value => String(value || '').replaceAll('ı','i').replaceAll('İ','I').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim().replace(/\s+/g,' ');
  window.studentSearchMatches = (name, number, query) => {
    query=normalize(query);
    return /^\d+$/.test(query) ? String(number).startsWith(query) : query.split(' ').every(word=>normalize(name).includes(word));
  };
  const applySearch = () => {
    if (typeof window.filtrele === 'function') window.filtrele();
    else if (typeof window.filterAnalysis === 'function') window.filterAnalysis();
    else document.querySelectorAll('#tracking .ogrenci').forEach(row => row.hidden = !window.studentSearchMatches(row.querySelector('.student-name strong').textContent, row.querySelector('.student-name small')?.textContent.replace(/\D/g,''), search.value));
  };
  const searchForm=document.querySelector('.app-student-search');
  if(search && searchForm){
    const results=document.createElement('div');results.className='app-search-results';results.id='student-search-results';results.hidden=true;results.setAttribute('aria-label','Öğrenci arama sonuçları');
    const status=document.createElement('p');status.setAttribute('role','status');
    searchForm.append(results);search.setAttribute('aria-controls',results.id);search.placeholder='Ad veya okul numarası…';search.autocomplete='off';
    let timer, controller, revision=0;
    function destination(student){
      const current=new URL(location.href), url=new URL(searchForm.action,location.href);
      if(current.pathname==='/lgs'){url.pathname='/lgs';url.search='';url.searchParams.set('ogrenci',student.id);if(current.searchParams.has('bolum'))url.searchParams.set('bolum',current.searchParams.get('bolum'));}
      else if(current.pathname==='/sonuclar'){url.pathname='/sonuclar';url.search='';url.searchParams.set('ogrenci',student.id);}
      else if(current.pathname==='/deneme-analiz'){url.pathname='/deneme-analiz';url.search=current.search;url.searchParams.delete('sinif');url.searchParams.set('ogrenci',student.id);url.searchParams.set('gorunum','birey');}
      else {url.search='';url.searchParams.set(url.pathname==='/analiz'?'sinif_id':'sinif',student.sinif_id);url.searchParams.set('q',student.no);if(url.pathname==='/dashboard')url.hash='ogrenci-listesi';}
      return url.href;
    }
    async function find(){
      clearTimeout(timer);controller?.abort();const own=++revision, query=search.value.trim();
      if(!query){results.hidden=true;return;}
      results.replaceChildren(status);status.textContent='Öğrenciler aranıyor…';results.hidden=false;
      controller=new AbortController();const params=new URLSearchParams({q:query});if(location.pathname==='/lgs')params.set('kapsam','lgs');
      try{
        const response=await fetch('/api/ogrenci-ara?'+params,{signal:controller.signal});if(!response.ok||!response.headers.get('content-type')?.includes('application/json'))throw new Error('search');
        const data=await response.json();if(own!==revision)return;
        status.textContent=data.toplam?data.toplam+' öğrenci bulundu. Açmak için öğrenciyi seçin.':'Öğrenci bulunamadı. Adı veya okul numarasını kontrol edin.';
        for(const student of data.ogrenciler){const link=document.createElement('a');link.href=destination(student);link.textContent=student.ad+' · '+student.sinif+' · No '+student.no;results.append(link);}
      }catch(error){if(error.name!=='AbortError'&&own===revision)status.textContent='Arama tamamlanamadı. Ara düğmesiyle yeniden deneyin.';}
    }
    search.addEventListener('input',()=>{applySearch();controller?.abort();++revision;clearTimeout(timer);if(!search.value.trim()){results.hidden=true;return;}timer=setTimeout(find,180);});
    search.addEventListener('keydown',event=>{if(event.key==='Escape'){controller?.abort();++revision;clearTimeout(timer);results.hidden=true;}if(event.key==='ArrowDown'){event.preventDefault();results.querySelector('a')?.focus();}});
    searchForm.addEventListener('submit',event=>{event.preventDefault();applySearch();window.setDashboardSection?.('liste');find();});
    document.addEventListener('click',event=>{if(!searchForm.contains(event.target)){controller?.abort();++revision;clearTimeout(timer);results.hidden=true;}});
  }
  if (search?.value) applySearch();
  document.getElementById('app-class-select')?.addEventListener('change', e => {
    const url = new URL(location.href);
    if(url.pathname==='/sonuclar'){
      url.search='';url.searchParams.set('sinif',e.target.value);location.href=url.href;return;
    }
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
