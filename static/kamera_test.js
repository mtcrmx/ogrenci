(() => {
  document.querySelectorAll('[data-loading-form]').forEach(form => form.addEventListener('submit', () => {
    form.querySelector('button').disabled = true;
    form.querySelector('.kt-loading').hidden = false;
  }));
  const app = document.querySelector('#camera-app');
  if (!app) return;
  const $ = id => document.getElementById(id);
  let stream = null, current = null, busy = false;
  const status = (message, error=false) => { $('scan-status').textContent=message; $('scan-status').classList.toggle('error',error); };
  const stop = () => { if(stream) stream.getTracks().forEach(t=>t.stop());stream=null;$('camera-box').hidden=true;$('stop-camera').hidden=true;$('start-camera').hidden=false; };
  const lock = value => { busy=value; ['capture','scan-photo','save-scan','start-camera'].forEach(id=>$(id).disabled=value); };
  async function post(action, data) {
    data.set('csrf',app.dataset.csrf);
    const res=await fetch(`/yaprak-kamera/${app.dataset.exam}/${action}`,{method:'POST',body:data,credentials:'same-origin'});
    const body=await res.json().catch(()=>({error:'İşlem tamamlanamadı. Bağlantınızı ve oturumunuzu kontrol edin.'}));
    if(!res.ok) throw Error(body.error || 'İşlem tamamlanamadı.');
    return body;
  }
  function showReview(result) {
    current=result; $('scan-review').hidden=false;
    $('scan-student').textContent=`${result.student.ad_soyad} · ${result.student.sinif_adi} · No ${result.student.ogr_no}`;
    $('scan-preview').src=result.preview;
    $('scan-warning').textContent=result.existing ? 'Bu öğrenci için sonuç var. Değiştirmek istiyorsanız cevapları ve değiştirme seçeneğini onaylayın.' : `${result.uncertain.length} soruda belirsiz işaret var. Sarı alanları fotoğrafla karşılaştırın; boş cevap için “Boş” seçin.`;
    $('replace-label').hidden=!result.existing;
    $('replace-confirm').checked=false;$('review-confirm').checked=false;
    $('scan-answers').replaceChildren();
    result.answers.forEach((a,i)=>{
      const label=document.createElement('label');label.textContent=`${i+1}. soru`;
      if(result.uncertain.includes(i+1)) label.className='uncertain';
      const select=document.createElement('select');select.dataset.no=i;
      for(const answer of ['',...app.dataset.choices]) { const op=document.createElement('option');op.value=answer;op.textContent=answer || 'Boş';op.selected=a===answer;select.append(op); }
      label.append(select);$('scan-answers').append(label);
    });
  }
  async function save(reviewed) {
    if(!current) return;
    const answers=reviewed ? [...$('scan-answers').querySelectorAll('select')].map(s=>s.value) : current.answers;
    const data=new FormData(); data.set('ticket',current.ticket);data.set('answers',JSON.stringify(answers));
    if(reviewed && $('review-confirm').checked) data.set('reviewed','yes');
    if(reviewed && $('replace-confirm').checked) data.set('replace','yes');
    const result=await post('kaydet',data);
    const badge=app.querySelector('.kt-badge');badge.textContent=`${result.count} / ${badge.dataset.total} kayıt`;
    const row=document.getElementById(`scan-result-${current.student.id}`);
    if(row) row.textContent=`${result.dogru} D · ${result.yanlis} Y · ${result.bos} B · ${result.net} net`;
    status(`${current.student.ad_soyad}: ${result.dogru} doğru · ${result.yanlis} yanlış · ${result.bos} boş · ${result.net} net — Kaydedildi. Sıradaki kâğıdı okutabilirsiniz.`);
    $('scan-review').hidden=true;current=null;
    if(navigator.vibrate) navigator.vibrate(100);
  }
  async function preparePhoto(blob) {
    // Limit upload size, while retaining about 7 pixels/mm on an A4 sheet.
    if (!window.createImageBitmap) return blob;
    let bitmap;
    try {
      bitmap=await createImageBitmap(blob, {imageOrientation:'from-image'});
      const scale=Math.min(1,2200/Math.max(bitmap.width,bitmap.height));
      const canvas=document.createElement('canvas');
      canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);
      const context=canvas.getContext('2d');
      context.fillStyle='#fff';context.fillRect(0,0,canvas.width,canvas.height);
      context.drawImage(bitmap,0,0,canvas.width,canvas.height);
      const encoded=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.9));
      return encoded && encoded.size<blob.size ? encoded : blob;
    } catch (_) { return blob; }
    finally { if(bitmap) bitmap.close(); }
  }
  async function phoneRead(blob) {
    if(!window.Worker||!window.createImageBitmap)throw Error('Telefon okuyucusu desteklenmiyor.');
    const bitmap=await createImageBitmap(blob,{imageOrientation:'from-image'});
    const canvas=document.createElement('canvas'),scale=Math.min(1,1600/Math.max(bitmap.width,bitmap.height));
    canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);
    const ctx=canvas.getContext('2d');ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();
    const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;
    const result=await new Promise((resolve,reject)=>{
      const worker=new Worker(app.dataset.worker);
      const timer=setTimeout(()=>{worker.terminate();reject(Error('Telefon okuması zaman aşımına uğradı.'));},6000);
      const finish=()=>{clearTimeout(timer);worker.terminate();};
      worker.onmessage=({data})=>{finish();data.error?reject(Error(data.error)):resolve(data.result);};
      worker.onerror=()=>{finish();reject(Error('Telefon okuyucusu başlatılamadı.'));};
      worker.postMessage({pixels,width:canvas.width,height:canvas.height,count:Number(app.dataset.count),choices:app.dataset.choices},[pixels.buffer]);
    });
    canvas.width=result.width;canvas.height=result.height;
    ctx.putImageData(new ImageData(result.pixels,result.width,result.height),0,0);
    return {reading:{token:result.token,answers:result.answers,uncertain:result.uncertain},preview:canvas.toDataURL('image/jpeg',.8)};
  }
  async function scan(blob) {
    if(busy) return;lock(true);current=null;$('scan-review').hidden=true;
    const started=performance.now();
    status('Fotoğraf hazırlanıyor…');
    try {
      let local;
      status('Optik telefonda okunuyor…');
      try { local=await phoneRead(blob); }
      catch(error) { status(`${error.message} Sunucuda deneniyor…`); }
      let result;
      if(local){
        const data=new FormData();data.set('reading',JSON.stringify(local.reading));
        result=await post('telefonda-oku',data);result.preview=local.preview;
      }else{
        const photo=await preparePhoto(blob),data=new FormData();data.set('image',photo,'scan.jpg');
        result=await post('tara',data);
      }
      showReview(result);
      if(!result.local && !result.uncertain.length && !result.existing) await save(false);
      else status('Okuma tamamlandı. Cevapları kontrol edip onaylayın.');
    } catch(e) {status(e.message,true);} finally {lock(false);$('scan-photo').value='';$('scan-status').textContent+=` (${((performance.now()-started)/1000).toFixed(1)} sn)`;}
  }
  $('start-camera').addEventListener('click',async()=>{
    try {
      if(!navigator.mediaDevices?.getUserMedia) throw Error('Bu tarayıcıda kamera açılamıyor. Fotoğraf yükle / çek seçeneğini kullanın.');
      stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1920},height:{ideal:2560}},audio:false});
      $('camera-video').srcObject=stream;await $('camera-video').play();
      $('camera-box').hidden=false;$('stop-camera').hidden=false;$('start-camera').hidden=true;
      status('Optik sayfanın tamamını gösterin ve Görüntüyü oku düğmesine basın.');
    } catch(e) {stop();status(e.name==='NotAllowedError'?'Kamera izni verilmedi. Tarayıcıdan izin verin veya fotoğraf yükleyin.':e.message,true);}
  });
  $('stop-camera').addEventListener('click',stop);
  $('capture').addEventListener('click',()=>{
    const video=$('camera-video');if(!video.videoWidth || busy) return;
    const canvas=document.createElement('canvas');canvas.width=video.videoWidth;canvas.height=video.videoHeight;
    canvas.getContext('2d').drawImage(video,0,0);canvas.toBlob(blob=>blob && scan(blob),'image/jpeg',.94);
  });
  $('scan-photo').addEventListener('change',e=>{if(e.target.files[0]) scan(e.target.files[0]);});
  $('save-scan').addEventListener('click',async()=>{
    if(busy || !current) return;
    if(!$('review-confirm').checked || (current.existing && !$('replace-confirm').checked)) {status('Kontrol ve gerekiyorsa değiştirme onayını işaretleyin.',true);return;}
    lock(true);try {await save(true);}catch(e){status(e.message,true);}finally{lock(false);}
  });
  $('cancel-scan').addEventListener('click',()=>{current=null;$('scan-review').hidden=true;status('Kayıt yapılmadı. Kâğıdı yeniden okutabilirsiniz.');});
  window.addEventListener('pagehide',stop);
})();
