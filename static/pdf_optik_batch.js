(() => {
  const app=document.getElementById('batch-reader');if(!app)return;
  const pending=JSON.parse(app.dataset.pages),status=document.getElementById('batch-progress'),button=document.getElementById('batch-resume');
  let done=Number(app.dataset.done),running=false;
  async function run(){
    if(running)return;running=true;button.hidden=true;
    try{
      while(pending.length){
        const page=pending[0];status.textContent=`${done} / ${app.dataset.total} sayfa okundu. Sayfa ${page} işleniyor…`;
        const data=new FormData();data.set('csrf',app.dataset.csrf);
        const response=await fetch(app.dataset.url.replace('/oku/0',`/oku/${page}`),{method:'POST',body:data,credentials:'same-origin'});
        if(!response.ok||response.redirected)throw Error('Okuma kesildi. Oturumunuz açıksa devam edin; süresi dolmuşsa yeniden giriş yapın.');
        const result=await response.json();if(!result.ok)throw Error('Bu sayfa işlenemedi. Tekrar deneyin.');
        pending.shift();done++;
      }
      location.reload();
    }catch(error){status.textContent=error.message;button.hidden=false;}finally{running=false;}
  }
  button.addEventListener('click',run);run();
})();
