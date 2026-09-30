(() => {
  const gallery = document.querySelector('.clay-badges');
  if (!gallery) return;

  const earned = [...gallery.querySelectorAll('.clay-badge-item.is-earned[data-rozet-kodu]')];
  const codes = earned.map(card => card.dataset.rozetKodu);
  const key = `ogrenci-rozetleri-goruldu-${gallery.dataset.studentId}`;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let previous = null;
  try {
    const saved = localStorage.getItem(key);
    if (saved !== null) previous = new Set(JSON.parse(saved));
    localStorage.setItem(key, JSON.stringify(codes));
  } catch (_) {
    // Depolama kapalıysa galeri ve giriş animasyonu yine çalışır.
  }

  const newCards = previous ? earned.filter(card => !previous.has(card.dataset.rozetKodu)) : [];
  const toast = gallery.querySelector('.clay-badges-toast');
  let shown = false;
  function reveal() {
    gallery.classList.add('is-visible');
    if (shown || !newCards.length) return;
    shown = true;
    if (reducedMotion) return;
    window.setTimeout(() => {
      for (const card of newCards) card.classList.add('is-new');
      const title = newCards[0].querySelector('.clay-badge-text strong')?.textContent?.trim() || 'Yeni rozet';
      toast.textContent = newCards.length === 1
        ? `Yeni rozet kazandın: ${title}!`
        : `${newCards.length} yeni rozet kazandın!`;
      toast.hidden = false;
      window.setTimeout(() => { toast.hidden = true; }, 4200);
      window.setTimeout(() => { for (const card of newCards) card.classList.remove('is-new'); }, 1400);
    }, 300);
  }

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) {
        reveal();
        observer.disconnect();
      }
    }, { threshold: 0.12 });
    observer.observe(gallery);
  } else {
    reveal();
  }
})();
