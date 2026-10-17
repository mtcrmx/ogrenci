(() => {
const catalog=JSON.parse(document.getElementById('outcome-catalog').textContent);
const rows=[...document.querySelectorAll('[data-question]')], status=document.getElementById('outcome-status');
function options(select,values,placeholder){select.replaceChildren(new Option(placeholder,''),...values.map(v=>new Option(v.label,v.value)));}
function count(){status.textContent=`${rows.filter(r=>r.querySelector('[data-outcome]').value).length} / ${rows.length} soru eşleştirildi`;}
function init(row,value=''){
 const course=row.querySelector('[data-course]'),topic=row.querySelector('[data-topic]'),out=row.querySelector('[data-outcome]'),description=row.querySelector('[data-description]');
 const item=catalog.find(i=>i.id===value);
 options(course,[...new Set(catalog.map(i=>i.course))].map(c=>({label:c,value:c})),'Ders seçin');course.value=item?.course||'';
 function outcomes(selected=''){options(out,catalog.filter(i=>i.course===course.value&&i.topic===topic.value).map(i=>({label:i.code+' · '+i.text,value:i.id})),'Kazanım seçilmedi');out.value=selected;describe();}
 function topics(selected='',outcome=''){options(topic,[...new Set(catalog.filter(i=>i.course===course.value).map(i=>i.topic))].map(t=>({label:t,value:t})),'Konu seçin');topic.value=selected;outcomes(outcome);}
 function describe(){description.textContent=catalog.find(i=>i.id===out.value)?.text||'Bu soru henüz kazanımla eşleştirilmedi.';count();}
 course.onchange=()=>topics();topic.onchange=()=>outcomes();out.onchange=describe;topics(item?.topic||'',value);
}
rows.forEach(r=>init(r,r.dataset.selected));count();
document.getElementById('bulk-apply').onclick=()=>{const source=Number(document.getElementById('bulk-source').value),start=Number(document.getElementById('bulk-from').value),end=Number(document.getElementById('bulk-to').value);if(![source,start,end].every(n=>Number.isInteger(n)&&n>=1&&n<=rows.length)||start>end){status.textContent='Geçerli bir soru aralığı seçin.';return;}const value=rows[source-1].querySelector('[data-outcome]').value;if(!value){status.textContent='Kaynak soruya önce bir kazanım seçin.';return;}for(let i=start;i<=end;i++)init(rows[i-1],value);count();};
})();
