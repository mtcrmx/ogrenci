// Local viewers: documents and slide assets stay on this school's server.
import {ensurePresentationPromises} from './school-broadcast-compat.mjs';
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
  let disposed=false, failed=false, pdf=null, pdfTask=null, deck=null, previewer=null, revision=0, serverPdf=false;
  const abort=new AbortController(), timeout=setTimeout(()=>{abort.abort();fail();},60000);
  const pageImages=new Map();
  function pageImage(number){
    if(!pageImages.has(number)){
      const element=document.createElement('img');element.className='presentation-image';
      const url=new URL(item.page_url,location.href);url.searchParams.set('sayfa',number);
      const loaded=new Promise((resolve,reject)=>{element.onload=resolve;element.onerror=()=>reject(new Error('Sunum sayfası yüklenemedi.'));});
      // A prefetched page may fail before navigation. Keep its rejection handled.
      loaded.catch(()=>{});element.src=url.href;pageImages.set(number,{element,loaded});
    }
    return pageImages.get(number);
  }
  const pdfCanvases=new Map(),canvasTasks=new Set(),frame=document.createElement('div');
  frame.className='presentation-frame';host.append(frame);
  const api={page:1,count:0,ready:false,busy:false,dispose(){disposed=true;revision++;abort.abort();clearTimeout(timeout);for(const task of canvasTasks)task.cancel();pdfTask?.destroy();previewer?.destroy();observer.disconnect();pageImages.clear();pdfCanvases.clear();}};
  function size(ratio) {
    const width=Math.max(100,Math.min(host.clientWidth,host.clientHeight/ratio));
    return {width,height:width*ratio};
  }
  function pdfCanvas(number){
    if(!pdfCanvases.has(number)){
      const canvas=document.createElement('canvas');
      const loaded=(async()=>{
        const page=await pdf.getPage(number);if(disposed)return;
        const base=page.getViewport({scale:1}),fitted=size(base.height/base.width);
        const ratio=Math.min(Math.max(devicePixelRatio||1,1),2,Math.sqrt(8000000/(fitted.width*fitted.height)));
        const viewport=page.getViewport({scale:fitted.width/base.width});
        canvas.width=Math.round(viewport.width*ratio);canvas.height=Math.round(viewport.height*ratio);
        canvas.style.width=`${fitted.width}px`;canvas.style.height=`${fitted.height}px`;
        canvas.setAttribute('aria-label',`${item.baslik} · Sayfa ${number} / ${api.count}`);
        const task=page.render({canvas,canvasContext:canvas.getContext('2d'),viewport,transform:ratio!==1?[ratio,0,0,ratio,0,0]:null});
        canvasTasks.add(task);try{await task.promise;}finally{canvasTasks.delete(task);}
      })();
      loaded.catch(()=>{});pdfCanvases.set(number,{canvas,loaded});
    }
    return pdfCanvases.get(number);
  }
  async function renderPage(number) {
    if(disposed||failed||api.busy||number<1||number>api.count)return;
    api.busy=true;const own=++revision;api.page=number;
    try {
      if(serverPdf){
        const {element,loaded}=pageImage(number);await loaded;
        if(disposed||failed||own!==revision)return;
        element.alt=`${item.baslik} · Sayfa ${number} / ${api.count}`;host.replaceChildren(element);
        if(number<api.count)pageImage(number+1);
        // Keep only the current, preceding and following page in memory.
        for(const page of pageImages.keys())if(Math.abs(page-number)>1)pageImages.delete(page);
      }else if(pdf){
        const {canvas,loaded}=pdfCanvas(number);await loaded;if(disposed||failed||own!==revision)return;
        host.replaceChildren(canvas);if(number<api.count)pdfCanvas(number+1);
        for(const page of pdfCanvases.keys())if(Math.abs(page-number)>1)pdfCanvases.delete(page);
      } else {
        // Native slide dimensions preserve layout; scale the finished DOM to fit the TV.
        const scale=Math.min(host.clientWidth/deck.width,host.clientHeight/deck.height);frame.style.width=`${deck.width}px`;frame.style.height=`${deck.height}px`;
        frame.style.transform=`translate(-50%,-50%) scale(${scale})`;previewer.renderSingleSlide(number-1);
      }
      if(!disposed&&!failed&&own===revision)onPage(api.page,api.count);
      return true;
    } catch(error){if(!disposed&&error.name!=='RenderingCancelledException'){console.warn('Sunum görüntülenemedi:',error.message);fail();}}
    finally{api.busy=false;}
  }
  api.go=renderPage;
  function fail(message){if(disposed||failed)return;failed=true;clearTimeout(timeout);api.ready=false;host.replaceChildren(Object.assign(document.createElement('p'),{className:'media-failure',textContent:message||'Sunum açılamadı. PDF olarak kaydedip tekrar yükleyebilirsiniz. Sonraki yayın devam edecek.'}));onReady(false);}
  const observer=typeof ResizeObserver==='function'?new ResizeObserver(()=>{if(api.ready&&!api.busy&&!serverPdf){pdfCanvases.clear();renderPage(api.page);}}):{observe(){},disconnect(){}};observer.observe(host);
  (async()=>{
    try {
      if(['pdf','pptx'].includes(item.type)&&item.page_url&&item.pdf_pages){
        serverPdf=true;api.count=item.pdf_pages;frame.remove();
        const rendered=await renderPage(1);if(disposed||failed||!rendered)return;
        api.ready=true;clearTimeout(timeout);onReady(true);return;
      }
      if(item.type==='pptx'&&item.presentation_status==='preparing'){
        fail('PowerPoint slaytları sunucuda hazırlanıyor. Hazır olunca otomatik yayına alınacak.');return;
      }
      const response=await fetch(item.url,{credentials:'same-origin',signal:abort.signal,cache:'no-store'});
      if(!response.ok)throw new Error();const bytes=await response.arrayBuffer();if(disposed)return;
      if(item.type==='pdf'){
        ensurePresentationPromises();
        const pdfjs=await import('./vendor/pdfjs/legacy/build/pdf.min.mjs');if(disposed||failed)return;
        const assets=new URL('./vendor/pdfjs/',import.meta.url);pdfjs.GlobalWorkerOptions.workerSrc=new URL('./school-broadcast-pdf-worker.mjs',import.meta.url).href;
        pdfTask=pdfjs.getDocument({data:new Uint8Array(bytes),cMapUrl:new URL('cmaps/',assets).href,cMapPacked:true,standardFontDataUrl:new URL('standard_fonts/',assets).href,wasmUrl:new URL('wasm/',assets).href,isEvalSupported:false});
        pdf=await pdfTask.promise;if(disposed)return;api.count=pdf.numPages;frame.remove();
      }else{
        await loadScript('./vendor/jszip/jszip.min.js');await loadScript('./vendor/pptx-preview/pptx-preview.umd.js');if(disposed)return;
        const zip=await window.JSZip.loadAsync(bytes);const xml=new DOMParser().parseFromString(await zip.file('ppt/presentation.xml').async('string'),'application/xml');
        const extent=xml.getElementsByTagNameNS('http://schemas.openxmlformats.org/presentationml/2006/main','sldSz')[0];
        const ratio=extent?Number(extent.getAttribute('cy'))/Number(extent.getAttribute('cx')):9/16;
        deck={ratio:Number.isFinite(ratio)&&ratio>0?ratio:9/16,width:1280};deck.height=Math.round(deck.width*deck.ratio);
        previewer=window.pptxPreview.init(frame,{width:deck.width,height:deck.height,mode:'slide'});
        const loaded=await previewer.load(await presentationBytes(zip,bytes));if(disposed)return;api.count=loaded.slides.length;
      }
      if(disposed||failed||!api.count)throw new Error();const rendered=await renderPage(1);if(disposed||failed||!rendered)return;
      api.ready=true;clearTimeout(timeout);onReady(true);
    }catch(error){if(!disposed){console.warn('Sunum görüntülenemedi:',error.message);fail();}}
  })();
  return api;
}
