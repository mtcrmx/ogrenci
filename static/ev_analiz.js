(() => {
 const root=document.querySelector('.ea'); if(!root)return;
 const tabs=[...root.querySelectorAll('[data-tab]')];
 function show(key){if(!tabs.some(t=>t.dataset.tab===key))key='overview';tabs.forEach(t=>t.setAttribute('aria-pressed',String(t.dataset.tab===key)));root.querySelectorAll('[data-panel]').forEach(p=>p.hidden=p.dataset.panel!==key);const u=new URL(location.href);u.searchParams.set('tab',key);history.replaceState(null,'',u);}
 tabs.forEach(t=>t.addEventListener('click',()=>show(t.dataset.tab)));
 root.querySelectorAll('[data-question]').forEach(b=>b.addEventListener('click',()=>{show('questions');const panel=document.getElementById('ea-q-'+b.dataset.question);if(panel){panel.hidden=false;panel.open=true;panel.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'center'});panel.querySelector('summary').focus();}}));
 root.querySelectorAll('[data-members]').forEach(b=>b.addEventListener('click',()=>{const form=document.getElementById('ea-group-form');if(!form)return;show('groups');const ids=new Set(b.dataset.members.split(','));form.querySelector('[name=name]').value=b.dataset.groupName;form.querySelectorAll('[name=member]').forEach(c=>c.checked=ids.has(c.value));form.querySelector('[name=name]').focus();}));
 document.getElementById('ea-question-filter')?.addEventListener('change',e=>root.querySelectorAll('.ea-question').forEach(q=>q.hidden=e.target.value!=='all' && Number(q.dataset[e.target.value])===0));
 show(root.dataset.initial);
})();
