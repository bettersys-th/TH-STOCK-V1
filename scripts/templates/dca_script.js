(function(){
const DATA=__DCA_JSON__,ticker=document.getElementById('riskTicker'),start=document.getElementById('dcaStart'),end=document.getElementById('dcaEnd');
Object.keys(DATA).sort().forEach(t=>{const o=document.createElement('option');o.value=t;document.getElementById('dcaTickerList').appendChild(o)});
const fmt=(x,d=2)=>Number(x).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=x=>`${x>=0?'+':''}${fmt(x)}`;
const pnlCell=(value,pct)=>`<td class="${value>0?'gain':value<0?'loss':'muted'}">${signed(value)}</td><td class="${pct>0?'gain':pct<0?'loss':'muted'}">${signed(pct)}%</td>`;
function stock(){return DATA[ticker.value.trim().toUpperCase()]}
function loadStock(){
 const x=stock();if(!x)return;const months=x.m.map(r=>r[0]),current=x.m.at(-1)[1],risk=x.r||{};
 start.innerHTML=months.map((m,i)=>`<option value="${m}" ${i===Math.max(0,months.length-120)?'selected':''}>${m}</option>`).join('');
 end.innerHTML=months.map((m,i)=>`<option value="${m}" ${i===months.length-1?'selected':''}>${m}</option>`).join('');
 document.getElementById('riskTarget').value=(risk.peak||current).toFixed(2);calculateRisk();
}
function calculateRisk(){
 const x=stock();if(!x)return;
 const symbol=ticker.value.trim().toUpperCase(),current=x.m.at(-1)[1],risk=x.r||{},initial=Math.max(0,+document.getElementById('riskInitial').value||0),contribution=Math.max(0,+document.getElementById('riskMonthly').value||0),months=Math.max(1,Math.round(+document.getElementById('riskMonths').value||1)),downMonths=Math.min(months,Math.max(1,Math.round(+document.getElementById('riskDeclineMonths').value||1))),frequency=document.getElementById('riskFrequency').value,periodsPerMonth=frequency==='daily'?21:frequency==='weekly'?4:1,periodsPerYear=periodsPerMonth*12,steps=months*periodsPerMonth,downSteps=downMonths*periodsPerMonth,frequencyLabel=frequency==='daily'?'ทุกวันทำการ':frequency==='weekly'?'ทุกสัปดาห์':'ทุกเดือน',drop=Math.min(.95,Math.max(0,(+document.getElementById('riskDecline').value||0)/100)),target=Math.max(.01,+document.getElementById('riskTarget').value||current),budget=Math.max(0,+document.getElementById('riskBudget').value||0),tolerance=Math.max(0,+document.getElementById('riskTolerance').value||0),withDiv=document.getElementById('riskDividend').checked,stress=current*(1-drop),annualDiv=withDiv?(risk.div12||0):0;
 let shares=initial/current,invested=initial,worstPct=0,troughValue=shares*current,usedPeriods=0,divTotal=0;
 const ledger=[];
 if(initial>0)ledger.push({period:'เริ่มต้น',phase:'ราคาปัจจุบัน',price:current,buy:initial,bought:shares,shares,invested,value:initial,pnl:0,pct:0});
 for(let i=1;i<=steps;i++){
  const price=i<=downSteps?current+(stress-current)*i/downSteps:stress+(target-stress)*(i-downSteps)/Math.max(1,steps-downSteps);
  if(annualDiv){const div=shares*(annualDiv/periodsPerYear);divTotal+=div;shares+=div/price;}
  let buy=0,bought=0;
  if(!budget||invested+contribution<=budget){buy=contribution;bought=buy/price;shares+=bought;invested+=buy;usedPeriods++;}
  const value=shares*price,pnl=value-invested,pct=invested?pnl/invested*100:0;
  if(pct/100<worstPct)worstPct=pct/100;if(i===downSteps)troughValue=value;
  if(buy>0)ledger.push({period:`${i}/${steps}`,phase:i<=downSteps?'ราคาลง':'ราคาฟื้น',price,buy,bought,shares,invested,value,pnl,pct});
 }
 const endValue=shares*target,pnl=endValue-invested,avg=shares?invested/shares:0,downside=avg?stress/avg-1:0,upside=avg?target/avg-1:0,desired=initial+contribution*steps,shortfall=budget&&desired>budget?desired-budget:0,overRisk=Math.abs(worstPct*100)>tolerance,liquid=(risk.medianValue30||0)>=1000000;
 const stats=[['ราคาปัจจุบัน',fmt(current)+' บาท'],['ราคาวิกฤต',fmt(stress)+' บาท'],['เงินที่ใช้จริง',fmt(invested)+' บาท'],['ต้นทุนเฉลี่ย',fmt(avg)+' บาท'],['มูลค่าที่จุดต่ำ',fmt(troughValue)+' บาท'],['ขาดทุนสูงสุด',`${fmt(worstPct*100)}%`],['Downside จากต้นทุน',`${fmt(downside*100)}%`],['Upside ถึงเป้าหมาย',`${upside>=0?'+':''}${fmt(upside*100)}%`],['มูลค่าเมื่อถึงเป้า',fmt(endValue)+' บาท'],['กำไร/ขาดทุนเป้า',`${pnl>=0?'+':''}${fmt(pnl)} บาท`],['เงินที่แผนต้องการ',fmt(desired)+' บาท'],['DCA ได้จริง',`${usedPeriods}/${steps} งวด`]];
 document.getElementById('riskGrid').innerHTML=stats.map(s=>`<div class="dca-stat"><small>${s[0]}</small><b>${s[1]}</b></div>`).join('');
 document.getElementById('riskLedgerBody').innerHTML=ledger.map(r=>`<tr><td>${r.period}</td><td>${r.phase}</td><td>${fmt(r.price)}</td><td>${fmt(r.buy)}</td><td>${fmt(r.bought,4)}</td><td>${fmt(r.shares,4)}</td><td>${fmt(r.invested)}</td><td>${fmt(r.invested/r.shares)}</td><td>${fmt(r.value)}</td>${pnlCell(r.pnl,r.pct)}</tr>`).join('');
 const headline=document.getElementById('riskHeadline');headline.className='risk-headline '+(overRisk?'danger':'safe');headline.textContent=overRisk?'⚠ Scenario นี้ขาดทุนเกินระดับที่คุณรับได้':'✓ Scenario นี้ยังอยู่ในกรอบขาดทุนที่กำหนด';
 document.getElementById('riskPathFill').style.width=Math.min(100,invested/(budget||desired)*100)+'%';document.getElementById('riskPathText').textContent=`ใช้งบ ${fmt(invested)} จาก ${fmt(budget||desired)} บาท`;
 const warnings=[];if(shortfall)warnings.push(`งบสูงสุดต่ำกว่าแผนที่ตั้งไว้ ${fmt(shortfall)} บาท`);if(overRisk)warnings.push(`ขาดทุนสูงสุด ${fmt(Math.abs(worstPct*100))}% มากกว่าเกณฑ์ ${fmt(tolerance)}%`);if(!liquid)warnings.push('มูลค่าซื้อขายมัธยฐานต่ำกว่า 1 ล้านบาท/วัน อาจซื้อหรือขายตามแผนได้ยาก');if(risk.trough&&stress<risk.trough)warnings.push(`ราคาวิกฤตต่ำกว่าแนวรับอ้างอิง ${fmt(risk.trough)} บาท`);
 document.getElementById('riskWarnings').innerHTML=(warnings.length?warnings:['เงื่อนไขงบประมาณ ความเสี่ยง และสภาพคล่องผ่านเกณฑ์ที่ตั้งไว้']).map(w=>`<div class="risk-warning ${warnings.length?'':'risk-ok'}">${warnings.length?'⚠ ':''}${w}</div>`).join('');
 const peakLabel=risk.peakProjected?'เป้าขาขึ้นประมาณจากรอบในอดีต':'แนวต้าน peak เดิมที่อยู่เหนือราคาปัจจุบัน',troughLabel=risk.troughProjected?'แนวรับประมาณจากรอบในอดีต':'แนวรับ trough เดิมที่อยู่ต่ำกว่าราคาปัจจุบัน';
 document.getElementById('riskDetail').textContent=`${symbol}: DCA ${frequencyLabel} งวดละ ${fmt(contribution)} บาท · สมมติราคาลง ${fmt(drop*100)}% ใน ${downMonths} เดือน แล้วฟื้นไป ${fmt(target)} บาทภายในเดือนที่ ${months} · ${peakLabel} ${fmt(risk.peak)} บาท · ${troughLabel} ${fmt(risk.trough)} บาท · ปันผลจำลองสะสม ${fmt(divTotal)} บาท`;
 document.getElementById('riskResult').classList.add('show');
}
function xirr(flows){let lo=-.99,hi=10;const npv=r=>flows.reduce((s,f)=>s+f.amount/Math.pow(1+r,f.month/12),0);if(npv(lo)*npv(hi)>0)return null;for(let i=0;i<100;i++){const mid=(lo+hi)/2;if(npv(lo)*npv(mid)<=0)hi=mid;else lo=mid;}return (lo+hi)/2;}
function calculateHistory(){
 const x=stock();if(!x)return;const rows=x.m.filter(r=>r[0]>=start.value&&r[0]<=end.value),amount=Math.max(0,+document.getElementById('dcaAmount').value||0),freq=+document.getElementById('dcaFrequency').value,reinvest=document.getElementById('dcaReinvest').checked,dv=Object.fromEntries(x.dv),flows=[];
 let shares=0,invested=0,cash=0,divTotal=0,purchases=0;const ledger=[];
 rows.forEach((r,i)=>{const div=(dv[r[0]]||0)*shares;divTotal+=div;if(reinvest&&div>0)shares+=div/r[1];else cash+=div;if(i%freq===0){const bought=amount/r[1];shares+=bought;invested+=amount;purchases++;flows.push({month:i,amount:-amount});const value=shares*r[1]+cash,pnl=value-invested,pct=invested?pnl/invested*100:0;ledger.push({date:r[0],price:r[1],buy:amount,bought,shares,invested,divTotal,avg:invested/shares,value,pnl,pct});}});
 if(!rows.length||!shares)return;const last=rows.at(-1),value=shares*last[1]+cash,ret=value/invested-1;flows.push({month:rows.length-1,amount:value});const annual=xirr(flows),stats=[['เงินลงทุนรวม',fmt(invested)+' บาท'],['มูลค่าปัจจุบัน',fmt(value)+' บาท'],['กำไร/ขาดทุน',`${value-invested>=0?'+':''}${fmt(value-invested)} บาท`],['ผลตอบแทน',`${ret>=0?'+':''}${fmt(ret*100)}%`],['ต้นทุนเฉลี่ย',fmt(invested/shares)+' บาท'],['จำนวนหุ้น',fmt(shares,3)],['ปันผลสะสม',fmt(divTotal)+' บาท'],['XIRR',annual===null?'—':`${annual>=0?'+':''}${fmt(annual*100)}%`]];
 document.getElementById('dcaGrid').innerHTML=stats.map(s=>`<div class="dca-stat"><small>${s[0]}</small><b>${s[1]}</b></div>`).join('');
 document.getElementById('historyLedgerBody').innerHTML=ledger.map(r=>`<tr><td>${r.date}</td><td>${fmt(r.price)}</td><td>${fmt(r.buy)}</td><td>${fmt(r.bought,4)}</td><td>${fmt(r.shares,4)}</td><td>${fmt(r.invested)}</td><td>${fmt(r.divTotal)}</td><td>${fmt(r.avg)}</td><td>${fmt(r.value)}</td>${pnlCell(r.pnl,r.pct)}</tr>`).join('');
 document.getElementById('dcaDetail').textContent=`${ticker.value.toUpperCase()} · ${rows[0][0]} ถึง ${last[0]} · ซื้อ ${purchases} งวด · กำไร/ขาดทุนในตารางคำนวณด้วยราคาปิดของเดือนที่ซื้อ`;document.getElementById('dcaResult').classList.add('show');
}
ticker.addEventListener('change',loadStock);ticker.addEventListener('input',()=>{if(stock())loadStock()});document.getElementById('riskCalculate').onclick=calculateRisk;
document.getElementById('riskFrequency').addEventListener('change',()=>{const el=document.getElementById('riskFrequency'),f=el.value,newPeriods=f==='daily'?21:f==='weekly'?4:1,oldPeriods=Number(el.dataset.periods||1),amount=document.getElementById('riskMonthly');amount.value=(Math.max(0,+amount.value||0)*oldPeriods/newPeriods).toFixed(2);el.dataset.periods=String(newPeriods);document.getElementById('riskContributionLabel').childNodes[0].nodeValue=f==='daily'?'DCA ต่อวันทำการ (บาท)':f==='weekly'?'DCA ต่อสัปดาห์ (บาท)':'DCA ต่อเดือน (บาท)';calculateRisk();});
document.querySelectorAll('.stress-presets button').forEach(b=>b.onclick=()=>{document.getElementById('riskDecline').value=b.dataset.drop;calculateRisk()});document.getElementById('dcaCalculate').onclick=calculateHistory;loadStock();
})();
