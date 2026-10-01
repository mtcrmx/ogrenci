import assert from 'node:assert/strict';
import {lessonState} from '../static/school-broadcast-clock.mjs';
const periods=[['08:15','08:55'],['09:15','09:55'],['10:10','10:50'],['11:05','11:45'],['12:55','13:35'],['13:50','14:30'],['14:45','15:25']];
const data={saatler:periods.map(([baslangic,bitis],i)=>({no:i+1,baslangic,bitis}))};
const time=s=>{const [h,m,sec=0]=s.split(':').map(Number);return h*3600+m*60+sec;};
for(const [stamp,title,lesson] of [['07:00','Dersler başlayacak',1],['08:15','1. ders',1],['08:54:59','1. ders',1],['08:55','Teneffüs',2],['09:15','2. ders',2],['11:45','Öğle arası',5],['12:55','5. ders',5],['15:24:59','7. ders',7],['15:25','Dersler tamamlandı',0]]){
  const state=lessonState(data,time(stamp));assert.equal(state.ad,title);assert.equal(state.ders,lesson);
}
assert.equal(lessonState(data,time('08:54:59')).kalan,1);
assert.equal(lessonState(data,time('08:35')).oran,.5);
assert.equal(lessonState({...data,kapali:true,aciklama:'Ara tatil'},time('09:30')).ad,'Ara tatil');
assert.equal(lessonState(data,time('00:00'),false).ders,0);
const friday={saatler:[...data.saatler.slice(0,4),{no:5,baslangic:'13:30',bitis:'14:00'},{no:6,baslangic:'14:00',bitis:'14:50'},{no:7,baslangic:'14:50',bitis:'15:40'}]};
assert.equal(lessonState(friday,time('14:00')).ders,6);
assert.equal(lessonState(friday,time('14:50')).ders,7);
assert.equal(lessonState(friday,time('15:40')).hedef,null);
console.log('PASS: 16 school-clock boundary and Friday/holiday/midnight checks');
