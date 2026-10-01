const viewer = document.querySelector('[data-pdf-url]');
if (viewer) {
  const status = viewer.querySelector('[data-pdf-status]');
  const counter = viewer.querySelector('[data-pdf-page]');
  const canvas = viewer.querySelector('[data-pdf-canvas]');
  const text = viewer.querySelector('[data-pdf-text]');
  const prev = viewer.querySelector('[data-pdf-prev]');
  const next = viewer.querySelector('[data-pdf-next]');
  let documentPdf, pageNumber = 1, task, revision = 0;
  const buttons = (busy) => {
    prev.disabled = busy || pageNumber <= 1;
    next.disabled = busy || pageNumber >= (documentPdf?.numPages || 1);
  };
  const render = async () => {
    const ownRevision = ++revision;
    task?.cancel();
    buttons(true);
    try {
      const page = await documentPdf.getPage(pageNumber);
      if (ownRevision !== revision) return;
      const width = Math.max(180, Math.min(1100, viewer.clientWidth - 2));
      const viewport = page.getViewport({scale:width / page.getViewport({scale:1}).width});
      // Keep text sharp on phones, and cap canvas memory for unusually tall pages.
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(8000000 / (viewport.width * viewport.height)));
      canvas.width = Math.floor(viewport.width * pixelRatio);
      canvas.height = Math.floor(viewport.height * pixelRatio);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;
      canvas.setAttribute('aria-label', `Sunum sayfası ${pageNumber} / ${documentPdf.numPages}`);
      task = page.render({canvas, canvasContext:canvas.getContext('2d'), viewport,
        transform:pixelRatio !== 1 ? [pixelRatio,0,0,pixelRatio,0,0] : null});
      await task.promise;
      if (ownRevision !== revision) return;
      const content = await page.getTextContent();
      if (ownRevision !== revision) return;
      text.textContent = content.items.map(item => (item.str || '') + (item.hasEOL ? '\n' : ' ')).join('') || 'Bu sayfada seçilebilir metin yok. Görseli inceleyebilir veya dosyayı açabilirsiniz.';
      counter.textContent = `Sayfa ${pageNumber} / ${documentPdf.numPages}`;
      status.hidden = true;
      buttons(false);
    } catch (error) {
      if (ownRevision !== revision || error.name === 'RenderingCancelledException') return;
      status.hidden = false;
      status.textContent = 'Bu sayfa görüntülenemedi. Aşağıdaki Dosyayı aç veya İndir düğmesini kullanabilirsiniz.';
      buttons(false);
    }
  };
  try {
    const pdfjs = await import('./vendor/pdfjs/build/pdf.min.mjs?v=6.3.289');
    const assets = new URL('./vendor/pdfjs/', import.meta.url);
    pdfjs.GlobalWorkerOptions.workerSrc = new URL('build/pdf.worker.min.mjs', assets).href;
    documentPdf = await pdfjs.getDocument({url:viewer.dataset.pdfUrl,
      cMapUrl:new URL('cmaps/', assets).href, cMapPacked:true,
      standardFontDataUrl:new URL('standard_fonts/', assets).href,
      wasmUrl:new URL('wasm/', assets).href, isEvalSupported:false}).promise;
    prev.addEventListener('click', () => { if (pageNumber > 1) { pageNumber--; render(); } });
    next.addEventListener('click', () => { if (pageNumber < documentPdf.numPages) { pageNumber++; render(); } });
    let resizeTimeout;
    window.addEventListener('resize', () => { clearTimeout(resizeTimeout); resizeTimeout = setTimeout(render,150); });
    await render();
  } catch (error) {
    console.error('PDF önizleme yüklenemedi:', error);
    status.textContent = 'Sunum açılamadı. Aşağıdaki Dosyayı aç veya İndir düğmesini kullanabilirsiniz.';
    counter.textContent = 'PDF sunumu';
    canvas.hidden = true;
  }
}
