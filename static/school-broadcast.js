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
  let presentation=null, announcementKey='';
  let calendarIndex=0, calendarDeadline=0, calendarKey='';
  const now=()=>new Date(Date.now()+offset);
  function state(){
    const [h,m,s]=timeFmt.format(now()).split(':').map(Number);
    return lessonState(data,h*3600+m*60+s,dateFmt.format(now())===data.tarih);
  }
  const node=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
  function slides(){
    const day=dateFmt.format(now()), published=data.icerikler.filter(i=>i.baslangic<=day&&i.bitis>=day);
    const media=published.filter(i=>i.tur!=='metin').map(i=>({...i,type:i.tur,title:i.baslik,kicker:i.tur==='video'?'ÖĞRETMENLERİMİZDEN · VİDEO':i.tur==='pdf'||i.tur==='pptx'?'ÖĞRETMENLERİMİZDEN · SUNUM':'ÖĞRETMENLERİMİZDEN · GÖRSEL'}));
    return media.length?media:[{type:'welcome',title:'Birlikte öğreniyor, birlikte büyüyoruz.',kicker:'SUNUM VE VİDEO ALANI',sure:18}];
  }
  function classNames(){return data.siniflar;}
  function render(){
    if(revoked)return;
    presentation?.dispose();presentation=null;$('presentation-controls').hidden=true;
    const list=slides();playlistKey=list.map(i=>i.id||i.type).join(':');index=(index+list.length)%list.length;const item=list[index],body=$('slide-body');
    body.replaceChildren();body.classList.remove('slide-body');void body.offsetWidth;body.classList.add('slide-body');
    txt('slide-title',item.title);txt('slide-kicker',item.kicker);txt('slide-count',`${String(index+1).padStart(2,'0')} / ${String(list.length).padStart(2,'0')}`);
    const dots=$('slide-dots');dots.replaceChildren(...list.map((_,i)=>node('span','dot'+(i===index?' active':''))));
    deadline=Date.now()+item.sure*1000;
    if(item.type==='pdf'||item.type==='pptx'){
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
    updateCalendar();
    const st=state(),sameDay=dateFmt.format(now())===data.tarih;
    txt('lesson-state',st.ad);txt('lesson-hours',st.hours||'');txt('countdown',st.hedef!==null?`${String(Math.floor(st.kalan/60)).padStart(2,'0')}:${String(st.kalan%60).padStart(2,'0')}`:'—');txt('countdown-label',st.etiket||st.aciklama||'Yarın yeni bir gün.');$('lesson-progress').style.width=`${Math.round((st.oran||0)*100)}%`;
    const following=data.saatler.find(p=>p.no===(st.inLesson?st.ders+1:st.ders));txt('next-lesson',following&&!st.kapali?`Sıradaki · ${following.no}. ders ${following.baslangic}`:st.kapali?'İyi dinlenmeler.':st.inLesson?'Günün son dersi':'Günün dersleri tamamlandı.');
    const key=`${data.tarih}:${sameDay}:${st.ad}:${st.ders}:${st.inLesson}`;
    if(key!==periodKey){periodKey=key;const p=$('periods');p.replaceChildren();for(const hour of data.saatler){const row=node('div','period-row'+(hour.no===st.ders&&!st.kapali?' active':''));row.append(node('span','',`${hour.no}. ders`),node('span','',`${hour.baslangic} – ${hour.bitis}`));p.append(row);}renderTeacherTable(st,sameDay);}
    for(let i=0;i<3;i++)txt(`duty-${i}`,!sameDay?'Güncelleniyor':data.kapali?'Bugün nöbet yok':data.nobet[i]||'Çizelge bekleniyor');
    const lgs=data.lgs;if(lgs.durum==='sayiyor'){const days=Math.max(0,Math.ceil((Date.parse(lgs.hedef)-now())/86400000));txt('lgs-days',`LGS hedefine ${days} gün`);txt('lgs-caption',`${lgs.tarih}${lgs.kesin?'':' · Planlama hedefi'}`);}else{txt('lgs-days',lgs.durum==='bugun'?'LGS bugün · Başarılar!':'Her gün bir adım ileri');txt('lgs-caption','Birlikte başaracağız.');}
    if(!paused&&Date.now()>=deadline){if(presentation?.ready&&presentation.page<presentation.count){presentation.go(presentation.page+1);deadline=Date.now()+slides()[index].sure*1000;}else{index++;render();}}
  }
  function renderTeacherTable(st,sameDay){
    const body=$('teacher-table-body');body.replaceChildren();txt('teacher-table-times','');
    if(!sameDay||st.kapali){txt('teacher-table-status',!sameDay?'Yeni günün programı bekleniyor':st.ad);body.append(node('p','teacher-empty','Bugün için aktif ders yok.'));return;}
    const period=data.saatler.find(p=>p.no===st.ders),next=data.saatler.find(p=>p.no===st.ders+1);
    txt('teacher-table-status',period?(st.inLesson?`${period.no}. ders · Şu an sınıfta`:`${period.no}. ders · Sıradaki ders`):'Günün dersleri tamamlandı');
    if(!period){body.append(node('p','teacher-empty','İyi dinlenmeler.'));return;}
    const table=node('table','teacher-table'),head=node('thead'),heading=node('tr');
    heading.append(node('th','','Sınıf'),node('th','',`${period.no}. ders`),node('th','',next?`${next.no}. ders`:'Sonraki'));head.append(heading);table.append(head);
    const rows=node('tbody');
    for(const name of classNames()){
      const row=node('tr'),label=node('th','',name);label.scope='row';row.append(label);
      for(const hour of [period,next]){
        const teachers=hour?data.program.filter(r=>r.sinif_adi===name&&r.ders_no===hour.no).map(r=>r.ogretmen_adi):[];
        row.append(node('td',hour===period?'teacher-current':'',teachers.join(' / ')||(hour?'Kayıt yok':'—')));
      }
      rows.append(row);
    }
    table.append(rows);body.append(table);
    txt('teacher-table-times',`${period.no}. ders ${period.baslangic}–${period.bitis}${next?`\n${next.no}. ders ${next.baslangic}–${next.bitis}`:''}`);
  }
  function updateAnnouncements(){
    const day=dateFmt.format(now()), items=data.icerikler.filter(i=>i.tur==='metin'&&i.baslangic<=day&&i.bitis>=day), key=JSON.stringify(items);
    if(key===announcementKey)return;
    announcementKey=key;const ticker=$('ticker-text');ticker.replaceChildren();
    if(!items.length){ticker.className='ticker-text static';ticker.textContent='Henüz duyuru yok · Öğretmenlerimizin paylaştığı okul duyuruları burada kayan yazı olarak gösterilir.';return;}
    items.forEach((item,i)=>{
      if(i)ticker.append(node('span','ticker-sep','✦'));
      const text=(item.metin||'').replace(/\s+/g,' ').trim();
      ticker.append(node('b','',item.baslik));if(text)ticker.append(document.createTextNode(text));
    });
    ticker.className='ticker-text';ticker.style.animation='none';void ticker.offsetWidth;ticker.style.animation='';
    ticker.style.animationDuration=`${Math.max(12,ticker.scrollWidth/(innerWidth*.06))}s`;
  }
  function updateCalendar(){
    const day=dateFmt.format(now()), source=data.takvim||{bugun:[],yaklasan:[]};
    const all=[...source.bugun,...source.yaklasan].filter(i=>i.aktif&&i.bitis>=day);
    const active=all.filter(i=>i.baslangic<=day),items=active.length?active:all.filter(i=>i.baslangic>day),key=day+JSON.stringify(items);
    if(key!==calendarKey){calendarKey=key;calendarIndex=0;calendarDeadline=0;}
    if(!items.length){txt('calendar-state','');txt('calendar-title','Birlikte öğreniyoruz');txt('calendar-dates','Okulun belirli gün ve hafta etkinlikleri burada gösterilir.');return;}
    if(Date.now()>=calendarDeadline){if(calendarDeadline)calendarIndex=(calendarIndex+1)%items.length;calendarDeadline=Date.now()+15000;}
    const item=items[calendarIndex],isActive=item.baslangic<=day;
    const short=new Intl.DateTimeFormat('tr-TR',{timeZone:'UTC',day:'numeric',month:'long',...(item.baslangic.slice(0,4)!==day.slice(0,4)?{year:'numeric'}:{})});
    const range=short.format(new Date(item.baslangic))+ (item.baslangic!==item.bitis?' – '+short.format(new Date(item.bitis)):'');
    const remaining=Math.round((Date.parse(item.baslangic)-Date.parse(day))/86400000);
    txt('calendar-state',isActive?(item.baslangic===item.bitis?'Bugün':item.baslik.toLocaleLowerCase('tr-TR').includes('hafta')?'Bu hafta':'Devam ediyor'):'Yaklaşıyor');
    txt('calendar-title',item.baslik);
    txt('calendar-dates',range+(!isActive?` · ${remaining===1?'Yarın':remaining+' gün kaldı'}`:'')+(item.planlama?' · Planlama aralığı':''));
  }
  async function refresh(){if(fetching||revoked)return;fetching=true;const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
    try{const r=await fetch(endpoint,{cache:'no-store',signal:controller.signal,credentials:'same-origin'});
      if(r.status===404||r.status===403||r.redirected){revoked=true;presentation?.dispose();$('slide-body').replaceChildren(node('div','message-slide','Yayın bağlantısı kapatıldı. Yönetimden yeni ekran bağlantısını açın.'));$('teacher-table-body').replaceChildren();['duty-0','duty-1','duty-2','lesson-hours','next-lesson','teacher-table-status','teacher-table-times','calendar-state','calendar-title','calendar-dates'].forEach(id=>txt(id,'—'));$('ticker-text').className='ticker-text static';txt('ticker-text','—');txt('connection','Yayın erişimi kapatıldı');$('connection').className='error';return;}
      if(!r.ok)throw new Error();const updated=await r.json();if(!updated.saatler||!updated.program)throw new Error();
      offset=Date.parse(updated.simdi)-Date.now();const nextSig=JSON.stringify({...updated,simdi:null,lgs:null});data=updated;
      if(signature!==nextSig){signature=nextSig;periodKey='';render();}txt('connection','Güncel · Türkiye saati');$('connection').className='';tick();
    }catch{txt('connection','Bağlantı bekleniyor · Son alınan bilgiler');$('connection').className='offline';}finally{clearTimeout(timer);fetching=false;}
  }
  async function keepAwake(){try{if(document.fullscreenElement&&navigator.wakeLock&&!wake)wake=await navigator.wakeLock.request('screen');if(wake)wake.addEventListener('release',()=>{wake=null;});}catch{/* Browser support is optional. */}}
  $('fullscreen').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.querySelector('.screen-shell').requestFullscreen();await keepAwake();}catch{txt('connection','Tam ekran için tarayıcınızda F11 tuşunu kullanın.');}});
  document.addEventListener('fullscreenchange',()=>{txt('fullscreen',document.fullscreenElement?'⛶ Tam ekrandan çık':'⛶ Tam ekran');if(!document.fullscreenElement&&wake)wake.release();});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden){refresh();keepAwake();}});window.addEventListener('online',refresh);window.addEventListener('resize',()=>{announcementKey='';});
  $('previous').addEventListener('click',()=>{index--;render();});$('next').addEventListener('click',()=>{index++;render();});
  for(const [id,delta] of [['presentation-prev',-1],['presentation-next',1]])$(id).addEventListener('click',()=>{if(presentation?.ready)presentation.go(presentation.page+delta);deadline=Date.now()+slides()[index].sure*1000;});
  $('pause').addEventListener('click',()=>{paused=!paused;txt('pause',paused?'▶':'Ⅱ');$('pause').setAttribute('aria-label',paused?'Yayını devam ettir':'Yayını duraklat');deadline=Date.now()+slides()[index].sure*1000;const video=$('slide-body').querySelector('video');if(video){if(paused)video.pause();else{if(Number.isFinite(video.duration))deadline=Date.now()+(video.duration-video.currentTime+10)*1000;video.play().catch(()=>{});}}});
  signature=JSON.stringify({...data,simdi:null,lgs:null});render();tick();txt('connection','Güncel · Türkiye saati');setInterval(tick,1000);setInterval(refresh,30000);
})();
