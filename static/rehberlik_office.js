(() => {
  document.querySelectorAll('[data-no-save]').forEach(area => {
    area.addEventListener('contextmenu', event => event.preventDefault());
    area.addEventListener('dragstart', event => event.preventDefault());
  });

  const box = document.querySelector('[data-office-url]');
  if (!box) return;
  const status = box.querySelector('[data-office-status]');
  const view = box.querySelector('[data-office-view]');
  const tabs = box.querySelector('[data-office-tabs]');
  const vendor = box.dataset.vendor;
  const type = box.dataset.officeType;

  const loadScript = src => new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = vendor + src;
    script.onload = resolve;
    script.onerror = () => reject(new Error('Görüntüleyici yüklenemedi: ' + src));
    document.head.append(script);
  });

  const fail = error => {
    console.error('Önizleme açılamadı:', error);
    status.hidden = false;
    status.textContent = 'Dosya önizlemesi açılamadı. Sayfayı yenileyip tekrar deneyin.';
  };

  const renderWord = async data => {
    await loadScript('jszip/jszip.min.js');
    await loadScript('docx-preview/docx-preview.min.js');
    await window.docx.renderAsync(data, view, null, {
      className: 'rh-docx', inWrapper: true, ignoreLastRenderedPageBreak: true,
      experimental: true, renderHeaders: true, renderFooters: true, useBase64URL: true,
    });
    const wrapper = view.querySelector('.rh-docx-wrapper');
    const page = wrapper?.querySelector('section.rh-docx');
    const fit = () => {
      if (!page) return;
      wrapper.style.zoom = '';
      wrapper.style.zoom = String(Math.min(1, (view.clientWidth - 8) / (page.offsetWidth + 32)));
    };
    fit();
    addEventListener('resize', fit);
  };

  const renderSheet = async data => {
    await loadScript('sheetjs/xlsx.full.min.js');
    const book = window.XLSX.read(data, {type: 'array', cellStyles: false});
    const show = name => {
      view.innerHTML = window.XLSX.utils.sheet_to_html(book.Sheets[name], {header: '', footer: ''});
      view.querySelector('table')?.classList.add('rh-sheet');
      tabs.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.sheet === name)));
    };
    if (book.SheetNames.length > 1) {
      tabs.hidden = false;
      book.SheetNames.forEach(name => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'app-button';
        button.dataset.sheet = name;
        button.textContent = name;
        button.addEventListener('click', () => show(name));
        tabs.append(button);
      });
    }
    show(book.SheetNames[0]);
  };

  const renderSlides = async data => {
    await loadScript('jszip/jszip.min.js');
    await loadScript('pptx-preview/pptx-preview.umd.js');
    let ratio = 9 / 16;
    try {
      const xml = await (await window.JSZip.loadAsync(data)).file('ppt/presentation.xml').async('string');
      const size = xml.match(/<p:sldSz[^>]*\bcx="(\d+)"[^>]*\bcy="(\d+)"/);
      if (size) ratio = Number(size[2]) / Number(size[1]);
    } catch (error) { /* varsayılan 16:9 */ }
    const width = Math.max(260, Math.min(960, (view.clientWidth || box.clientWidth || 984) - 24));
    const previewer = window.pptxPreview.init(view, {width, height: Math.round(width * ratio), mode: 'slide'});
    await previewer.preview(data);
  };

  (async () => {
    try {
      const response = await fetch(box.dataset.officeUrl, {credentials: 'same-origin'});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const data = await response.arrayBuffer();
      if (type === 'docx') await renderWord(data);
      else if (type === 'xlsx' || type === 'xls') await renderSheet(data);
      else if (type === 'pptx') await renderSlides(data);
      status.hidden = true;
    } catch (error) {
      fail(error);
    }
  })();
})();
