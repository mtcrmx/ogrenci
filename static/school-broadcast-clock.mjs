// Shared pure clock calculation: half-open intervals, Turkey-local day supplied by caller.
export function lessonState(data, current, sameDay=true) {
  if(!sameDay)return {ad:'Yeni gün',ders:0,hedef:null,kapali:true,aciklama:'Güncel program bekleniyor'};
  if(data.kapali)return {ad:data.aciklama||'Bugün ders yok',ders:0,hedef:null,kapali:true};
  const secs=s=>Number(s.slice(0,2))*3600+Number(s.slice(3))*60;
  let previous=0;
  for(const p of data.saatler){const start=secs(p.baslangic),end=secs(p.bitis);
    if(current<start)return {ad:p.no===1?'Dersler başlayacak':start-previous>=2700?'Öğle arası':'Teneffüs',ders:p.no,hedef:start,kalan:start-current,etiket:p.no===1?'İlk derse kalan süre':'Sonraki derse kalan süre',hours:`${p.no}. ders · ${p.baslangic}–${p.bitis}`,oran:0};
    if(current<end)return {ad:`${p.no}. ders`,ders:p.no,hedef:end,kalan:end-current,etiket:p.no===data.saatler.length?'Ders bitimine kalan süre':'Teneffüse kalan süre',hours:`${p.baslangic}–${p.bitis}`,oran:(current-start)/(end-start),inLesson:true};
    previous=end;
  }
  return {ad:'Dersler tamamlandı',ders:0,hedef:null};
}
