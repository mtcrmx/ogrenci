(function(root){
  function bind(doc, remaining, clock, schedule){
    const expires=clock()+Math.max(0,remaining)*1000;
    let locked=false;
    function check(event){
      if(clock()<expires)return false;
      if(event)event.preventDefault();
      doc.querySelectorAll('[data-home-test] input,[data-home-test] button').forEach(el=>{el.disabled=true;});
      if(!locked){
        const message=doc.createElement('p');message.setAttribute('role','status');
        message.textContent='Süre sona erdi. Cevap gönderimi kapalı; soru belgesi okunabilir.';
        doc.querySelector('[data-home-test]')?.prepend(message);locked=true;
      }
      return true;
    }
    doc.querySelectorAll('[data-home-test]').forEach(form=>form.addEventListener('submit',check));
    doc.addEventListener('visibilitychange',check);schedule(check,1000);check();
    return check;
  }
  if(typeof module==='object')module.exports={bind};
  else{const script=document.querySelector('script[data-remaining]');if(script)bind(document,Number(script.dataset.remaining),()=>performance.now(),setInterval);}
})(typeof window==='undefined'?globalThis:window);
