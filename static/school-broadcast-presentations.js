// Local viewers: documents and slide assets stay on this school's server.
import {ensurePresentationPromises} from './school-broadcast-compat.mjs';
export function mountPresentation(host, item, onPage, onReady) {
  let disposed=false, failed=false, pdf=null, pdfTask=null, renderTask=null, revision=0, serverPdf=false;
  const abort=new AbortController(), timeout=setTimeout(()=>{abort.abort();fail();},60000);
  const image=document.createElement('img');image.className='presentation-image';
  const canvas=document.createElement('canvas'), frame=document.createElement('div');
  frame.className='presentation-frame';host.append(frame);
  const api={page:1,count:0,ready:false,busy:false,dispose(){disposed=true;revision++;abort.abort();clearTimeout(timeout);renderTask?.cancel();pdfTask?.destroy();observer.disconnect();}};
  function size(ratio) {
    const width=Math.max(100,Math.min(host.clientWidth,host.clientHeight/ratio));
    return {width:Math.floor(width),height:Math.floor(width*ratio)};
  }
  async function renderPage(number) {
    if(disposed||failed||api.busy||number<1||number>api.count)return;
    api.busy=true;const own=++revision;api.page=number;
    try {
      if(serverPdf){
        const url=new URL(item.page_url,location.href);url.searchParams.set('sayfa',number);
        await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(new Error('PDF sayfası yüklenemedi.'));image.src=url.href;});
        if(disposed||failed||own!==revision)return;
        image.alt=`${item.baslik} · Sayfa ${number} / ${api.count}`;
      }else if(pdf){const page=await pdf.getPage(number);if(disposed||failed||own!==revision)return;
        const base=page.getViewport({scale:1}), fitted=size(base.height/base.width);
        const ratio=Math.min(Math.max(devicePixelRatio||1,1),2,Math.sqrt(8000000/(fitted.width*fitted.height)));
        const viewport=page.getViewport({scale:fitted.width/base.width});
        canvas.width=Math.round(viewport.width*ratio);canvas.height=Math.round(viewport.height*ratio);
        canvas.style.width=`${fitted.width}px`;canvas.style.height=`${fitted.height}px`;canvas.setAttribute('aria-label',`${item.baslik} · Sayfa ${number} / ${api.count}`);
        renderTask=page.render({canvas,canvasContext:canvas.getContext('2d'),viewport,transform:ratio!==1?[ratio,0,0,ratio,0,0]:null});await renderTask.promise;

      }
      if(!disposed&&!failed&&own===revision)onPage(api.page,api.count);
      return true;
    } catch(error){if(!disposed&&error.name!=='RenderingCancelledException'){console.warn('Sunum görüntülenemedi:',error.message);fail();}}
    finally{api.busy=false;}
  }
  api.go=renderPage;
  function fail(message){if(disposed||failed)return;failed=true;clearTimeout(timeout);api.ready=false;host.replaceChildren(Object.assign(document.createElement('p'),{className:'media-failure',textContent:message||'Sunum açılamadı. Sonraki yayın devam edecek.'}));onReady(false);}
  const observer=typeof ResizeObserver==='function'?new ResizeObserver(()=>{if(api.ready&&!api.busy&&!serverPdf)renderPage(api.page);}):{observe(){},disconnect(){}};observer.observe(host);
  (async()=>{
    try {
      if(['pdf','pptx'].includes(item.type)&&item.page_url&&item.pdf_pages){
        serverPdf=true;api.count=item.pdf_pages;frame.remove();host.append(image);
        const rendered=await renderPage(1);if(disposed||failed||!rendered)return;
        api.ready=true;clearTimeout(timeout);onReady(true);return;
      }
      if(item.type==='pptx'){fail(item.presentation_status==='preparing'?'Sunum hazırlanıyor. Hazır olduğunda otomatik yayına alınacak.':'Sunum henüz hazır değil. Yayın yönetiminden hazırlama durumunu kontrol edin.');return;}
      const response=await fetch(item.url,{credentials:'same-origin',signal:abort.signal,cache:'no-store'});
      if(!response.ok)throw new Error();const bytes=await response.arrayBuffer();if(disposed)return;
      if(item.type==='pdf'){
        ensurePresentationPromises();
        const pdfjs=await import('./vendor/pdfjs/legacy/build/pdf.min.mjs');if(disposed||failed)return;
        const assets=new URL('./vendor/pdfjs/',import.meta.url);pdfjs.GlobalWorkerOptions.workerSrc=new URL('./school-broadcast-pdf-worker.mjs',import.meta.url).href;
        pdfTask=pdfjs.getDocument({data:new Uint8Array(bytes),cMapUrl:new URL('cmaps/',assets).href,cMapPacked:true,standardFontDataUrl:new URL('standard_fonts/',assets).href,wasmUrl:new URL('wasm/',assets).href,isEvalSupported:false});
        pdf=await pdfTask.promise;if(disposed)return;api.count=pdf.numPages;frame.remove();host.append(canvas);

      }
      if(disposed||failed||!api.count)throw new Error();const rendered=await renderPage(1);if(disposed||failed||!rendered)return;
      api.ready=true;clearTimeout(timeout);onReady(true);
    }catch(error){if(!disposed){console.warn('Sunum görüntülenemedi:',error.message);fail();}}
  })();
  return api;
}
