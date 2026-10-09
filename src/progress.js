/* Only local browser state; cross-language article IDs share progress. */
(() => {
  const root=document.querySelector('[data-track]');if(!root)return;
  const key='engineering-manual/v1/track/'+root.dataset.track;
  const inputs=[...root.querySelectorAll('input[data-topic]')],label=document.getElementById('progress-label'),fill=document.getElementById('progress-fill'),bar=root.querySelector('[role="progressbar"]');
  let state=[];try{state=JSON.parse(localStorage.getItem(key)||'[]');if(!Array.isArray(state))state=[];}catch{state=[];}
  const update=()=>{const checked=inputs.filter(i=>i.checked).length;label.textContent=checked+' / '+inputs.length;const pct=inputs.length?Math.round(100*checked/inputs.length):0;fill.style.width=pct+'%';bar.setAttribute('aria-valuenow',String(pct));};
  inputs.forEach(i=>{i.checked=state.includes(i.dataset.topic);i.addEventListener('change',()=>{const next=inputs.filter(x=>x.checked).map(x=>x.dataset.topic);try{localStorage.setItem(key,JSON.stringify(next));}catch{} update();});});
  root.querySelector('#progress-reset').addEventListener('click',()=>{inputs.forEach(x=>x.checked=false);try{localStorage.removeItem(key);}catch{} update();}); update();
})();
