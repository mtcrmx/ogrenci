(() => {
  const form=document.getElementById('result-form'); if(!form)return;
  const rows=document.getElementById('result-rows'), kind=document.getElementById('result-kind'), add=document.getElementById('add-result-row');
  function update(){
    const items=[...rows.querySelectorAll('.result-row')];
    add.hidden=kind.value==='ders'; add.disabled=items.length>=rows.querySelector('[name=ders]').options.length;
    items.forEach((row,i)=>{
      row.querySelector('legend').textContent='Ders sonucu '+(i+1);
      row.querySelector('[data-remove-row]').hidden=items.length===1;
      const count=row.querySelector('[name=soru_sayisi]'), c=row.querySelector('[name=dogru]'), w=row.querySelector('[name=yanlis]'), rule=row.querySelector('[name=yanlis_goturme]'), preview=row.querySelector('.result-preview');
      const total=Number(count.value), correct=Number(c.value), wrong=Number(w.value), penalty=Number(rule.value), invalid=correct+wrong>total;
      w.setCustomValidity(invalid?'Doğru ve yanlış toplamı soru sayısını geçemez.':'');
      preview.classList.toggle('result-error',invalid);
      preview.textContent=invalid?'Doğru ve yanlış toplamı soru sayısını geçemez.':(!c.value||!w.value?'Doğru ve yanlışı yazın (yoksa 0).':(total-correct-wrong)+' boş · '+(correct-(penalty?wrong/penalty:0)).toLocaleString('tr-TR',{maximumFractionDigits:2})+' net');
    });
    kind.setCustomValidity(kind.value==='ders'&&items.length>1?'Ders testinde tek ders olmalı. Ek dersleri kaldırın veya Deneme seçin.':'');
  }
  add.addEventListener('click',()=>{
    const copy=rows.querySelector('.result-row').cloneNode(true);
    copy.querySelectorAll('[name=dogru],[name=yanlis]').forEach(input=>input.value='');
    const used=[...rows.querySelectorAll('[name=ders]')].map(s=>s.value), select=copy.querySelector('[name=ders]');
    const next=[...select.options].find(o=>!used.includes(o.value));if(next)select.value=next.value;
    rows.append(copy);update();select.focus();
  });
  rows.addEventListener('click',e=>{if(e.target.closest('[data-remove-row]')){e.target.closest('.result-row').remove();update();}});
  form.addEventListener('input',update);form.addEventListener('change',update);update();
})();
