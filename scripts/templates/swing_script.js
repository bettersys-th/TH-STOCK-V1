(function(){
const DATA=__SWING_JSON__, labels={triggered:'Triggered',setup:'Setup',extended:'Extended',failed:'Failed',neutral:'Neutral',illiquid:'สภาพคล่องต่ำ'};
const search=document.getElementById('swingSearch'),status=document.getElementById('swingStatus'),score=document.getElementById('swingScore'),sort=document.getElementById('swingSort'),tbody=document.getElementById('swingTable');
const n=(x,d=2)=>Number(x).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
function render(){
 const q=search.value.trim().toUpperCase(), st=status.value, min=Number(score.value);
 let rows=DATA.filter(x=>(!q||x.t.includes(q))&&x.score>=min&&(st==='all'||(st==='actionable'?['triggered','setup'].includes(x.status):x.status===st)));
 const rules={score:(a,b)=>b.score-a.score,breakout:(a,b)=>Math.abs(a.breakoutPct)-Math.abs(b.breakoutPct),volume:(a,b)=>b.volumeRatio-a.volumeRatio,rr:(a,b)=>b.rr-a.rr}; rows=rows.slice().sort(rules[sort.value]);
 document.getElementById('swingCount').textContent=`พบ ${rows.length} หุ้น · Triggered ${rows.filter(x=>x.status==='triggered').length} · Setup ${rows.filter(x=>x.status==='setup').length}`;
 tbody.innerHTML=rows.map(x=>`<tr class="swing-row" data-t="${x.t}"><td class="swing-symbol">${x.t}<small>${x.date}</small></td><td><span class="swing-pill ${x.status}">${labels[x.status]}</span></td><td class="swing-score">${x.score}</td><td>${n(x.price)}</td><td>${n(x.ma20)} / ${n(x.ma50)} / ${n(x.ma200)}</td><td class="${x.breakoutPct>=0?'dir-up':''}">${x.breakoutPct>=0?'+':''}${n(x.breakoutPct)}%</td><td>${n(x.volumeRatio)}x</td><td class="${x.momentum20>=0?'dir-up':'dir-down'}">${x.momentum20>=0?'+':''}${n(x.momentum20)}%</td><td>${n(x.stop)} / ${n(x.target)}</td><td>${n(x.rr)}x</td><td class="swing-reason">${x.reasons.join(' · ')||'—'}</td></tr>`).join('');
 tbody.querySelectorAll('.swing-row').forEach(row=>row.onclick=()=>{document.getElementById('navCycle').click();const input=document.getElementById('cycTicker');input.value=row.dataset.t;input.dispatchEvent(new Event('change'));document.getElementById('analyzeBtn').click();});
}
[search,status,score,sort].forEach(x=>x.addEventListener(x===search?'input':'change',render));render();
})();
