/* Local search: no network requests except the same-origin published index. */
(() => {
  const form=document.getElementById('manual-search-form'); if(!form)return;
  const input=document.getElementById('manual-query'),results=document.getElementById('search-results'),status=document.getElementById('search-status');
  const lang=form.dataset.lang; let data=[], timer;
  const normalize=s=>(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const escape=s=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function run(){
    const q=normalize(input.value.trim());const words=q.split(/\s+/).filter(Boolean);
    if(!words.length){results.innerHTML='<p>'+(lang==='pt'?'Digite um termo para começar.':'Enter a term to start.')+'</p>';status.textContent='';return;}
    let found=data.filter(x=>x.lang===lang).map(x=>{
      const title=normalize(x.title),desc=normalize(x.description),txt=normalize(x.text);
      if(!words.every(w=>title.includes(w)||desc.includes(w)||txt.includes(w)))return null;
      const score=words.reduce((s,w)=>s+(title.includes(w)?8:0)+(desc.includes(w)?3:0)+(txt.includes(w)?1:0),0);
      return {...x,score};
    }).filter(Boolean).sort((a,b)=>b.score-a.score||a.title.localeCompare(b.title)).slice(0,60);
    status.textContent=found.length+' '+(lang==='pt'?'resultado(s), máximo de 60':'result(s), max 60');
    results.innerHTML=found.length?'<ol class="result-list">'+found.map(r=>'<li><a href="'+encodeURI(r.url)+'">'+escape(r.title)+'</a><small>'+escape(r.category)+'</small><p>'+escape(r.description)+'</p></li>').join('')+'</ol>':'<p>'+(lang==='pt'?'Nenhum capítulo correspondente.':'No matching articles.')+'</p>';
  }
  fetch('/search-index.json').then(r=>{if(!r.ok)throw Error('index');return r.json()}).then(rows=>{data=rows;run()}).catch(()=>{status.textContent=lang==='pt'?'Índice indisponível.':'Search index unavailable.'});
  input.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(run,80)});
  form.addEventListener('submit',e=>{e.preventDefault();history.replaceState(null,'','?q='+encodeURIComponent(input.value.trim()));run()});
  input.value=new URLSearchParams(location.search).get('q')||'';
})();
