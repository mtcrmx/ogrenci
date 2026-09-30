(() => {
  const card = document.querySelector('[data-lgs-countdown][data-target]');
  if (!card) return;
  const target = Date.parse(card.dataset.target);
  const serverNow = Date.parse(card.dataset.now);
  if (!Number.isFinite(target) || !Number.isFinite(serverNow)) return;
  const start = performance.now();
  const clock = card.querySelector('[data-countdown-clock]');
  const message = card.querySelector('[data-countdown-message]');
  const days = card.querySelector('[data-countdown-days]');
  const hours = card.querySelector('[data-countdown-hours]');
  const minutes = card.querySelector('[data-countdown-minutes]');
  const update = () => {
    const now = serverNow + performance.now() - start;
    const remaining = Math.max(0, Math.floor((target - now) / 1000));
    clock.hidden = remaining === 0;
    message.hidden = remaining > 0;
    if (remaining === 0) {
      const estimated = card.dataset.confirmed !== '1';
      message.textContent = now < target + 86400000
        ? (estimated ? 'Bugün hedef gün!' : 'Bugün LGS günü!')
        : (estimated ? 'Hedef tarihi geçti' : 'Sınav tarihi geçti');
      return;
    }
    days.textContent = Math.floor(remaining / 86400);
    hours.textContent = String(Math.floor(remaining % 86400 / 3600)).padStart(2, '0');
    minutes.textContent = String(Math.floor(remaining % 3600 / 60)).padStart(2, '0');
  };
  update();
  setInterval(() => { if (!document.hidden) update(); }, 1000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) update(); });
})();
