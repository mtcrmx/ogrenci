(function () {
  const menu = document.getElementById('veli-menu');
  const toggle = document.getElementById('veli-menu-toggle');
  const scrim = document.getElementById('veli-menu-scrim');
  if (!menu || !toggle || !scrim) return;

  const mobile = window.matchMedia('(max-width: 760px)');
  const sectionLinks = Array.from(menu.querySelectorAll('.vp-nav-link[href^="#"]'));

  function setOpen(open, restoreFocus) {
    const active = mobile.matches && open;
    menu.classList.toggle('is-open', active);
    document.body.classList.toggle('vp-menu-open', active);
    scrim.hidden = !active;
    toggle.setAttribute('aria-expanded', String(active));
    toggle.setAttribute('aria-label', active ? 'Menüyü kapat' : 'Menüyü aç');
    menu.inert = mobile.matches && !active;
    if (active) menu.querySelector('.vp-nav-link').focus();
    else if (restoreFocus) toggle.focus();
  }

  function updateCurrentSection() {
    const target = location.hash || '#genel';
    sectionLinks.forEach(function (link) {
      const current = link.getAttribute('href') === target;
      link.classList.toggle('is-current', current);
      if (current) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  }

  toggle.addEventListener('click', function () { setOpen(!menu.classList.contains('is-open'), false); });
  scrim.addEventListener('click', function () { setOpen(false, true); });
  menu.addEventListener('click', function (event) {
    if (event.target.closest('a')) setOpen(false, false);
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && menu.classList.contains('is-open')) setOpen(false, true);
  });
  mobile.addEventListener('change', function () { setOpen(false, false); });
  window.addEventListener('hashchange', updateCurrentSection);
  setOpen(false, false);
  updateCurrentSection();
})();
