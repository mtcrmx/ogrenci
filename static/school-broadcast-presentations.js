// Local viewers: documents and slide assets stay on this school's server.
const scripts = new Map();
// The local PPTX renderer misses paragraph defaults on text runs. Materialize
// those defaults in an in-memory copy, preserving explicit run formatting.
async function presentationBytes(zip, original) {
  const ns='http://schemas.openxmlformats.org/drawingml/2006/main';let changed=false;
  for(const file of Object.values(zip.files).filter(f=>/^ppt\/slides\/slide\d+\.xml$/.test(f.name))){
    const xml=new DOMParser().parseFromString(await file.async('string'),'application/xml');let edited=false;
    for(const paragraph of xml.getElementsByTagNameNS(ns,'p')){
      const defaults=Array.from(paragraph.children).find(e=>e.localName==='pPr')?.getElementsByTagNameNS(ns,'defRPr')[0];
      if(!defaults)continue;
      for(const run of Array.from(paragraph.children).filter(e=>['r','fld'].includes(e.localName))){
        let props=Array.from(run.children).find(e=>e.localName==='rPr');
        if(!props){props=xml.createElementNS(ns,'a:rPr');run.prepend(props);}
        for(const attr of defaults.attributes)if(!props.hasAttribute(attr.name))props.setAttribute(attr.name,attr.value);
        for(const child of defaults.children)if(!Array.from(props.children).some(e=>e.localName===child.localName))props.append(child.cloneNode(true));
        edited=true;
      }
    }
    if(edited){zip.file(file.name,new XMLSerializer().serializeToString(xml));changed=true;}
  }
  return changed?zip.generateAsync({type:'arraybuffer'}):original;
}
const loadScript = path => {
  const url = new URL(path, import.meta.url).href;
  if (!scripts.has(url)) scripts.set(url, new Promise((resolve, reject) => {
    const script=document.createElement('script');script.src=url;script.onload=resolve;
    script.onerror=()=>{scripts.delete(url);reject(new Error('Sunum görüntüleyicisi yüklenemedi.'));};document.head.append(script);
  }));
  return scripts.get(url);
};

export function mountPresentation(host, item, onPage, onReady) {
  let disposed=false, pdf=null, pdfTask=null, renderTask=null, deck=null, previewer=null, revision=0;
  const abort=new AbortController(), timeout=setTimeout(()=>abort.abort(),15000);
  const canvas=document.createElement('canvas'), frame=document.createElement('div');
  frame.className='presentation-frame';host.append(frame);
  const api={page:1,count:0,ready:false,busy:false,dispose(){disposed=true;revision++;abort.abort();clearTimeout(timeout);renderTask?.cancel();pdfTask?.destroy();previewer?.destroy();observer.disconnect();}};
  function size(ratio) {
    const width=Math.max(100,Math.min(host.clientWidth,host.clientHeight/ratio));
    return {width:Math.floor(width),height:Math.floor(width*ratio)};
  }
  async function renderPage(number) {
    if(disposed||api.busy||number<1||number>api.count)return;
    api.busy=true;const own=++revision;api.page=number;
    try {
      if(pdf){const page=await pdf.getPage(number);if(disposed||own!==revision)return;
        const base=page.getViewport({scale:1}), fitted=size(base.height/base.width);
        const ratio=Math.min(Math.max(devicePixelRatio||1,1),2,Math.sqrt(8000000/(fitted.width*fitted.height)));
        const viewport=page.getViewport({scale:fitted.width/base.width});
        canvas.width=Math.round(viewport.width*ratio);canvas.height=Math.round(viewport.height*ratio);
        canvas.style.width=`${fitted.width}px`;canvas.style.height=`${fitted.height}px`;canvas.setAttribute('aria-label',`${item.baslik} · Sayfa ${number} / ${api.count}`);
        renderTask=page.render({canvas,canvasContext:canvas.getContext('2d'),viewport,transform:ratio!==1?[ratio,0,0,ratio,0,0]:null});await renderTask.promise;
      } else {
        // Native slide dimensions preserve layout; scale the finished DOM to fit the TV.
        const fitted=size(deck.ratio);frame.style.width=`${deck.width}px`;frame.style.height=`${deck.height}px`;
        frame.style.transform=`translate(-50%,-50%) scale(${fitted.width/deck.width})`;previewer.renderSingleSlide(number-1);
      }
      if(!disposed&&own===revision)onPage(api.page,api.count);
      return true;
    } catch(error){if(!disposed&&error.name!=='RenderingCancelledException')fail();}
    finally{api.busy=false;}
  }
  api.go=renderPage;
  function fail(){if(disposed)return;api.ready=false;host.replaceChildren(Object.assign(document.createElement('p'),{className:'media-failure',textContent:'Sunum açılamadı. PDF olarak kaydedip tekrar yükleyebilirsiniz. Sonraki yayın devam edecek.'}));onReady(false);}
  const observer=new ResizeObserver(()=>{if(api.ready&&!api.busy)renderPage(api.page);});observer.observe(host);
  (async()=>{
    try {
      const response=await fetch(item.url,{credentials:'same-origin',signal:abort.signal,cache:'no-store'});
      if(!response.ok)throw new Error();const bytes=await response.arrayBuffer();if(disposed)return;
      if(item.type==='pdf'){
        const pdfjs=await import('./vendor/pdfjs/build/pdf.min.mjs');if(disposed)return;
        const assets=new URL('./vendor/pdfjs/',import.meta.url);pdfjs.GlobalWorkerOptions.workerSrc=new URL('build/pdf.worker.min.mjs',assets).href;
        pdfTask=pdfjs.getDocument({data:bytes,cMapUrl:new URL('cmaps/',assets).href,cMapPacked:true,standardFontDataUrl:new URL('standard_fonts/',assets).href,wasmUrl:new URL('wasm/',assets).href,isEvalSupported:false});
        pdf=await pdfTask.promise;if(disposed)return;api.count=pdf.numPages;frame.remove();host.append(canvas);
      }else{
        await loadScript('./vendor/jszip/jszip.min.js');await loadScript('./vendor/pptx-preview/pptx-preview.umd.js');if(disposed)return;
        const zip=await window.JSZip.loadAsync(bytes);const xml=new DOMParser().parseFromString(await zip.file('ppt/presentation.xml').async('string'),'application/xml');
        const extent=xml.getElementsByTagNameNS('http://schemas.openxmlformats.org/presentationml/2006/main','sldSz')[0];
        const ratio=extent?Number(extent.getAttribute('cy'))/Number(extent.getAttribute('cx')):9/16;
        deck={ratio:Number.isFinite(ratio)&&ratio>0?ratio:9/16,width:1280};deck.height=Math.round(deck.width*deck.ratio);
        previewer=window.pptxPreview.init(frame,{width:deck.width,height:deck.height,mode:'slide'});
        const loaded=await previewer.load(await presentationBytes(zip,bytes));if(disposed)return;api.count=loaded.slides.length;
      }
      if(disposed||!api.count)throw new Error();const rendered=await renderPage(1);if(disposed||!rendered)return;
      api.ready=true;clearTimeout(timeout);onReady(true);
    }catch(error){if(!disposed)fail();}
  })();
  return api;
}
