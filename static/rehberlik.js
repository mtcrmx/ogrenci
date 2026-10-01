(() => {
  const radios = document.querySelectorAll('input[name=hedef]');
  const setAudience = () => {
    const mode = document.querySelector('input[name=hedef]:checked')?.value;
    document.querySelectorAll('[data-audience]').forEach(el => {
      el.hidden = el.dataset.audience !== mode;
      el.querySelectorAll('input[type=checkbox]').forEach(input => input.disabled = el.hidden);
    });
  };
  radios.forEach(r => r.addEventListener('change',setAudience));
  if (radios.length) setAudience();
  const search = document.querySelector('[data-recipient-search]');
  const count = document.querySelector('[data-recipient-count]');
  const labels = [...document.querySelectorAll('[data-recipient]')];
  const update = () => {
    const term = (search?.value || '').toLocaleLowerCase('tr').trim();
    labels.forEach(label => label.hidden = !label.textContent.toLocaleLowerCase('tr').includes(term));
    if (count) count.textContent = `${labels.filter(l => l.querySelector('input').checked).length} veli seçildi · ${labels.filter(l => !l.hidden).length} öğrenci gösteriliyor`;
  };
  search?.addEventListener('input',update);
  labels.forEach(label => label.addEventListener('change',update));
  update();
  const openMeeting = () => {
    if (location.hash === '#icerik-gorusme') {
      const detail = document.querySelector('[data-meeting-details]');
      if (detail) detail.open = true;
    }
  };
  addEventListener('hashchange',openMeeting);
  document.querySelector('a[href="#icerik-gorusme"]')?.addEventListener('click', () => {
    const detail = document.querySelector('[data-meeting-details]');
    if (detail) detail.open = true;
  });
  openMeeting();
})();
