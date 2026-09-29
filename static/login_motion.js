(() => {
  const backdrop = document.querySelector('.login-motion-backdrop');
  const video = backdrop?.querySelector('video');
  if (!video) return;

  const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;

  function syncVideo() {
    if (motionPreference.matches || connection?.saveData) {
      video.pause();
      backdrop.classList.remove('is-playing');
      return;
    }

    if (!video.src) {
      video.src = video.dataset.src;
      video.load();
    }
    video.play().catch(() => {
      backdrop.classList.remove('is-playing');
    });
  }

  video.addEventListener('playing', () => backdrop.classList.add('is-playing'));
  motionPreference.addEventListener?.('change', syncVideo);
  connection?.addEventListener?.('change', syncVideo);
  syncVideo();
})();
