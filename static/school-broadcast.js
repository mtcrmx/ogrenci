import {lessonState} from './school-broadcast-clock.mjs';
import {mountPresentation} from './school-broadcast-presentations.js';
/* No student or parent data enters this screen. Times use Europe/Istanbul. */
(() => {
  'use strict';
  let data=JSON.parse(document.getElementById('broadcast-data').textContent);
  const endpoint=JSON.parse(document.getElementById('broadcast-url').textContent);
  const $=id=>document.getElementById(id), txt=(id,value)=>{$(id).textContent=value;};
  const timeFmt=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Istanbul',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
  const dateFmt=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Istanbul',year:'numeric',month:'2-digit',day:'2-digit'});
  const longDate=new Intl.DateTimeFormat('tr-TR',{timeZone:'Europe/Istanbul',weekday:'long',day:'numeric',month:'long',year:'numeric'});
  let offset=Date.parse(data.simdi)-Date.now(), index=0, paused=false, deadline=0, signature='', periodKey='', playlistKey='', fetching=false, revoked=false, wake=null;
  let presentation=null, programMode=false, announcementIndex=0, announcementDeadline=0, announcementKey='';
  const now=()=>new Date(Date.now()+offset);
  function state(){
    const [h,m,s]=timeFmt.format(now()).split(':').map(Number);
    return lessonState(data,h*3600+m*60+s,dateFmt.format(now())===data.tarih);
  }
  const node=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
  function slides(){
    const list=[{type:'classes',title:'Sınıflarımızın öğretmenleri',kicker:'BUGÜN OKULDA',sure:24},{type:'table',title:'Bugünün ders programı',kicker:'BİR BAKIŞTA · TÜM SINIFLAR',sure:30}];
    const day=dateFmt.format(now()), published=data.icerikler.filter(i=>i.baslangic<=day&&i.bitis>=day);
    const media=published.filter(i=>i.tur!=='metin').map(i=>({...i,type:i.tur,title:i.baslik,kicker:i.tur==='video'?'ÖĞRETMENLERİMİZDEN · VİDEO':i.tur==='pdf'||i.tur==='pptx'?'ÖĞRETMENLERİMİZDEN · SUNUM':'ÖĞRETMENLERİMİZDEN · GÖRSEL'}));
    if(media.length&&!programMode)return media;
    if(!programMode)list.push({type:'welcome',title:'Birlikte öğreniyor, birlikte büyüyoruz.',kicker:'SUNUM VE VİDEO ALANI',sure:18});
    return list;
  }
  function classNames(){return data.siniflar;}
  function render(){
    if(revoked)return;
    presentation?.dispose();presentation=null;$('presentation-controls').hidden=true;
    const list=slides();playlistKey=list.map(i=>i.id||i.type).join(':');index=(index+list.length)%list.length;const item=list[index],body=$('slide-body'),st=state();
    body.replaceChildren();body.classList.remove('slide-body');void body.offsetWidth;body.classList.add('slide-body');
    txt('slide-title',item.title);txt('slide-kicker',item.kicker);txt('slide-count',`${String(index+1).padStart(2,'0')} / ${String(list.length).padStart(2,'0')}`);
    const dots=$('slide-dots');dots.replaceChildren(...list.map((_,i)=>node('span','dot'+(i===index?' active':''))));
    deadline=Date.now()+item.sure*1000;
    if(item.type==='classes'){
      const names=classNames(),grid=node('div','classes-grid');
      if(st.kapali||!names.length){const box=node('div','message-slide');box.append(node('span','message-mark','✦'),node('p','',st.kapali?st.ad:'Bugün için ders programı bulunamadı.'));body.append(box);return;}
      for(const name of names){const card=node('article','class-card');const rows=data.program.filter(r=>r.sinif_adi===name&&r.ders_no===st.ders);
        card.append(node('div','class-name',name),node('div','class-course',st.ders?(rows.map(r=>r.ogretmen_adi).join(' / ')||'Program kaydı yok'):'Dersler tamamlandı'),node('div','class-teacher',st.ders?(st.inLesson?'Şu an sınıfta':'Sıradaki ders'):'İyi dinlenmeler'));
        if(st.ders)card.append(node('small','',st.inLesson?'Şu anki ders':`${st.ders}. ders · sıradaki`));grid.append(card);
      }body.append(grid);
    }else if(item.type==='table'){
      const names=classNames();if(st.kapali||!names.length){body.append(node('div','message-slide',st.kapali?st.ad:'Program henüz eklenmedi.'));return;}
      const table=node('table','day-table'),head=node('thead'),hr=node('tr');hr.append(node('th','','Ders / saat'));names.forEach(n=>hr.append(node('th','',n)));head.append(hr);table.append(head);const tb=node('tbody');
      for(const p of data.saatler){const row=node('tr',p.no===st.ders?'current':'');const th=node('th','',`${p.no}. ders`);th.append(node('small','',`${p.baslangic}–${p.bitis}`));row.append(th);
        for(const name of names){const lessons=data.program.filter(r=>r.sinif_adi===name&&r.ders_no===p.no);const td=node('td','',lessons.map(r=>r.ogretmen_adi).join(' / ')||'—');row.append(td);}tb.append(row);
      }table.append(tb);body.append(table);
    }else if(item.type==='pdf'||item.type==='pptx'){
      const wrap=node('div','presentation-wrap');body.append(wrap);wrap.append(node('p','presentation-loading','Sunum hazırlanıyor…'));deadline=Date.now()+20000;
      presentation=mountPresentation(wrap,item,(page,count)=>{txt('presentation-page',`${page} / ${count}`);$('presentation-prev').disabled=page<=1;$('presentation-next').disabled=page>=count;},ready=>{$('presentation-controls').hidden=!ready;deadline=Date.now()+item.sure*1000;wrap.querySelector('.presentation-loading')?.remove();});
      if(item.metin)body.append(node('p','media-caption',item.metin));
    }else if(item.type==='gorsel'||item.type==='video'){
      const wrap=node('div','media-wrap'),media=node(item.type==='video'?'video':'img');media.src=item.url;
      if(item.type==='gorsel')media.alt=item.baslik;
      else{media.muted=true;media.autoplay=!paused;media.playsInline=true;media.preload='auto';media.loop=false;media.setAttribute('aria-label',item.baslik);
        media.addEventListener('loadedmetadata',()=>{if(media.isConnected&&Number.isFinite(media.duration))deadline=Date.now()+(media.duration+10)*1000;});
        media.addEventListener('ended',()=>{if(media.isConnected&&!paused){index++;render();}});
      }
      media.addEventListener('error',()=>{wrap.replaceChildren(node('p','media-failure','İçerik açılamadı. Sonraki yayın devam edecek.'));});wrap.append(media);body.append(wrap);
      if(item.metin)body.append(node('p','media-caption',item.metin));
      if(item.type==='video'){const attempt=()=>media.play().catch(()=>{wrap.replaceChildren(node('p','media-failure','Videoyu oynatmak için tam ekran düğmesine basın.'));});if(!paused)attempt();}
    }else{const box=node('div','message-slide');box.append(node('span','message-mark','✦'),node('p','',item.metin||'Merak et. Soru sor. Birlikte keşfet.\nHer gün yeni bir şey öğrenmek için güzel bir gün.'),node('small','','ERENLER CUMHURİYET ORTAOKULU · İSKİLİP'));body.append(box);}
  }
  function tick(){
    const [hm1,hm2,s]=timeFmt.format(now()).split(':');txt('clock',`${hm1}:${hm2}`);txt('seconds',s);txt('school-date',longDate.format(now()));
    if(revoked)return;
    if(playlistKey!==slides().map(i=>i.id||i.type).join(':')){index=0;render();}
    updateAnnouncements();
    const st=state(),sameDay=dateFmt.format(now())===data.tarih;
    txt('lesson-state',st.ad);txt('lesson-hours',st.hours||'');txt('countdown',st.hedef!==null?`${String(Math.floor(st.kalan/60)).padStart(2,'0')}:${String(st.kalan%60).padStart(2,'0')}`:'—');txt('countdown-label',st.etiket||st.aciklama||'Yarın yeni bir gün.');$('lesson-progress').style.width=`${Math.round((st.oran||0)*100)}%`;
    const following=data.saatler.find(p=>p.no===(st.inLesson?st.ders+1:st.ders));txt('next-lesson',following&&!st.kapali?`Sıradaki · ${following.no}. ders ${following.baslangic}`:st.kapali?'İyi dinlenmeler.':'Günün dersleri tamamlandı.');
    const key=`${data.tarih}:${st.ad}:${st.ders}`;
    if(key!==periodKey){periodKey=key;const p=$('periods');p.replaceChildren();for(const hour of data.saatler){const row=node('div','period-row'+(hour.no===st.ders&&!st.kapali?' active':''));row.append(node('span','',`${hour.no}. ders`),node('span','',`${hour.baslangic} – ${hour.bitis}`));p.append(row);}if(['classes','table'].includes(slides()[index]?.type))render();}
    for(let i=0;i<3;i++)txt(`duty-${i}`,!sameDay?'Güncelleniyor':data.kapali?'Bugün nöbet yok':data.nobet[i]||'Çizelge bekleniyor');
    const lgs=data.lgs;if(lgs.durum==='sayiyor'){const days=Math.max(0,Math.ceil((Date.parse(lgs.hedef)-now())/86400000));txt('lgs-days',`LGS hedefine ${days} gün`);txt('lgs-caption',`${lgs.tarih}${lgs.kesin?'':' · Planlama hedefi'}`);}else{txt('lgs-days',lgs.durum==='bugun'?'LGS bugün · Başarılar!':'Her gün bir adım ileri');txt('lgs-caption','Birlikte başaracağız.');}
    if(!paused&&Date.now()>=deadline){if(presentation?.ready&&presentation.page<presentation.count){presentation.go(presentation.page+1);deadline=Date.now()+slides()[index].sure*1000;}else{index++;render();}}
  }
  function updateAnnouncements(){
    const day=dateFmt.format(now()), items=data.icerikler.filter(i=>i.tur==='metin'&&i.baslangic<=day&&i.bitis>=day), key=JSON.stringify(items);
    if(key!==announcementKey){announcementKey=key;announcementIndex=0;announcementDeadline=0;}
    if(!items.length){txt('announcement-title','Henüz duyuru yok');txt('announcement-message','Öğretmenlerimizin paylaştığı okul duyuruları burada gösterilir.');txt('announcement-count','');return;}
    if(Date.now()>=announcementDeadline){if(announcementDeadline)announcementIndex=(announcementIndex+1)%items.length;announcementDeadline=Date.now()+Math.max(12,items[announcementIndex].sure)*1000;}
    const item=items[announcementIndex];txt('announcement-title',item.baslik);txt('announcement-message',item.metin);txt('announcement-count',`${announcementIndex+1} / ${items.length}`);
  }
  async function refresh(){if(fetching||revoked)return;fetching=true;const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
    try{const r=await fetch(endpoint,{cache:'no-store',signal:controller.signal,credentials:'same-origin'});
      if(r.status===404||r.status===403||r.redirected){revoked=true;presentation?.dispose();$('slide-body').replaceChildren(node('div','message-slide','Yayın bağlantısı kapatıldı. Yönetimden yeni ekran bağlantısını açın.'));['duty-0','duty-1','duty-2','lesson-hours','next-lesson','announcement-title','announcement-message','announcement-count'].forEach(id=>txt(id,'—'));txt('connection','Yayın erişimi kapatıldı');$('connection').className='error';return;}
      if(!r.ok)throw new Error();const updated=await r.json();if(!updated.saatler||!updated.program)throw new Error();
      offset=Date.parse(updated.simdi)-Date.now();const nextSig=JSON.stringify({...updated,simdi:null,lgs:null});data=updated;
      if(signature!==nextSig){signature=nextSig;periodKey='';render();}txt('connection','Güncel · Türkiye saati');$('connection').className='';tick();
    }catch{txt('connection','Bağlantı bekleniyor · Son alınan bilgiler');$('connection').className='offline';}finally{clearTimeout(timer);fetching=false;}
  }
  async function keepAwake(){try{if(document.fullscreenElement&&navigator.wakeLock&&!wake)wake=await navigator.wakeLock.request('screen');if(wake)wake.addEventListener('release',()=>{wake=null;});}catch{/* Browser support is optional. */}}
  $('fullscreen').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.querySelector('.screen-shell').requestFullscreen();await keepAwake();}catch{txt('connection','Tam ekran için tarayıcınızda F11 tuşunu kullanın.');}});
  document.addEventListener('fullscreenchange',()=>{txt('fullscreen',document.fullscreenElement?'⛶ Tam ekrandan çık':'⛶ Tam ekran');if(!document.fullscreenElement&&wake)wake.release();});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden){refresh();keepAwake();}});window.addEventListener('online',refresh);
  $('previous').addEventListener('click',()=>{index--;render();});$('next').addEventListener('click',()=>{index++;render();});
  $('program-toggle').addEventListener('click',()=>{programMode=!programMode;index=0;render();$('program-toggle').setAttribute('aria-label',programMode?'Sunum ve videoları göster':'Ders programını göster');});
  for(const [id,delta] of [['presentation-prev',-1],['presentation-next',1]])$(id).addEventListener('click',()=>{if(presentation?.ready)presentation.go(presentation.page+delta);deadline=Date.now()+slides()[index].sure*1000;});
  $('pause').addEventListener('click',()=>{paused=!paused;txt('pause',paused?'▶':'Ⅱ');$('pause').setAttribute('aria-label',paused?'Yayını devam ettir':'Yayını duraklat');deadline=Date.now()+slides()[index].sure*1000;const video=$('slide-body').querySelector('video');if(video){if(paused)video.pause();else{if(Number.isFinite(video.duration))deadline=Date.now()+(video.duration-video.currentTime+10)*1000;video.play().catch(()=>{});}}});
  signature=JSON.stringify({...data,simdi:null,lgs:null});render();tick();txt('connection','Güncel · Türkiye saati');setInterval(tick,1000);setInterval(refresh,30000);
})();
