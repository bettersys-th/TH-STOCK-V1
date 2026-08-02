(function(){
const DATA=__DCA_JSON__,ticker=document.getElementById('riskTicker'),start=document.getElementById('dcaStart'),end=document.getElementById('dcaEnd');
const PLAN_FIELDS=['riskInitial','riskBudget','riskFrequency','riskMonths','riskDecline','riskDeclineMonths','riskUseCycleTime','riskTarget','riskTolerance','riskDividend'];
const plans=new Map();let activePlan=null;
Object.keys(DATA).sort().forEach(t=>{const o=document.createElement('option');o.value=t;document.getElementById('dcaTickerList').appendChild(o)});
const fmt=(x,d=2)=>Number(x).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=x=>`${x>=0?'+':''}${fmt(x)}`;
const pnlCell=(value,pct)=>`<td class="${value>0?'gain':value<0?'loss':'muted'}">${signed(value)}</td><td class="${pct>0?'gain':pct<0?'loss':'muted'}">${signed(pct)}%</td>`;
function stock(){return DATA[ticker.value.trim().toUpperCase()]}
function capturePlan(){const values={};PLAN_FIELDS.forEach(id=>{const el=document.getElementById(id);values[id]=el.type==='checkbox'?el.checked:el.value});return values;}
function restorePlan(values){if(!values)return;PLAN_FIELDS.forEach(id=>{if(!(id in values))return;const el=document.getElementById(id);if(el.type==='checkbox')el.checked=Boolean(values[id]);else el.value=values[id]});}
function saveActivePlan(){if(activePlan&&plans.has(activePlan))plans.get(activePlan).values=capturePlan();}
function renderPlanTabs(){
 saveActivePlan();let total=0;plans.forEach(p=>total+=Math.max(0,Number(p.values?.riskBudget)||0));
 document.getElementById('dcaPlanTabs').innerHTML=[...plans.entries()].map(([symbol,p])=>`<div class="dca-plan-tab ${symbol===activePlan?'active':''}" data-symbol="${symbol}"><b>${symbol}</b><small>${fmt(Number(p.values?.riskBudget)||0,0)} บ.</small>${plans.size>1?'<button type="button" title="ลบแผน">×</button>':''}</div>`).join('');
 document.getElementById('dcaBatchNote').innerHTML=`งบของแต่ละหุ้นเป็นคนละแผน · งบรวมทุกแท็บ <span class="dca-plan-total">${fmt(total,0)} บาท</span>`;
 document.querySelectorAll('.dca-plan-tab').forEach(tab=>{tab.addEventListener('click',()=>activatePlan(tab.dataset.symbol));const remove=tab.querySelector('button');if(remove)remove.addEventListener('click',e=>{e.stopPropagation();removePlan(tab.dataset.symbol)})});
}
function activatePlan(symbol){
 symbol=symbol.toUpperCase();if(!DATA[symbol])return false;if(activePlan!==symbol)saveActivePlan();if(!plans.has(symbol))plans.set(symbol,{values:null});activePlan=symbol;ticker.value=symbol;loadStock(plans.get(symbol).values);renderPlanTabs();return true;
}
function removePlan(symbol){if(!plans.has(symbol))return;plans.delete(symbol);if(activePlan===symbol){const next=plans.keys().next().value;if(next)activatePlan(next)}else renderPlanTabs();}
function applyCycleTime(){
 const x=stock(),check=document.getElementById('riskUseCycleTime'),input=document.getElementById('riskDeclineMonths'),note=document.getElementById('cycleTimeNote'),mean=x?.r?.downDays,median=x?.r?.downDaysMedian,days=median||mean,samples=x?.r?.downCycles||0;
 if(!days||samples<2){check.checked=false;check.disabled=true;note.textContent=samples===1?'มีเพียง 1 Cycle จึงยังไม่ใช้เป็นค่าอัตโนมัติ':'ไม่มี Cycle ขาลงเพียงพอ กรุณากำหนดเอง';return;}
 check.disabled=false;note.textContent=`Median ${median||'—'} วัน · เฉลี่ย ${mean||'—'} วัน จาก ${samples} รอบ · ใช้ ${days} วัน`;
 if(check.checked)input.value=Math.min(120,Math.max(1,Math.round(days/30.44)));
}
function updateContribution(){
 const frequency=document.getElementById('riskFrequency').value,periodsPerMonth=frequency==='daily'?21:frequency==='weekly'?4:1,months=Math.max(1,Math.round(+document.getElementById('riskMonths').value||1)),steps=months*periodsPerMonth,initial=Math.max(0,+document.getElementById('riskInitial').value||0),budget=Math.max(0,+document.getElementById('riskBudget').value||0),contribution=Math.max(0,(budget-initial)/steps);
 document.getElementById('riskMonthly').value=contribution.toFixed(2);return contribution;
}
function simulateScenario({current,bottom,target,steps,downSteps,initial,contribution,budget,annualDiv,periodsPerYear}){
 let shares=initial/current,invested=initial,worst=0;
 for(let i=1;i<=steps;i++){const price=i<=downSteps?current+(bottom-current)*i/downSteps:bottom+(target-bottom)*(i-downSteps)/Math.max(1,steps-downSteps);if(annualDiv)shares+=shares*(annualDiv/periodsPerYear)/price;if(contribution>0&&invested+contribution<=budget+.01){shares+=contribution/price;invested+=contribution;}const pct=invested?shares*price/invested-1:0;worst=Math.min(worst,pct);}
 const value=shares*target,pnl=value-invested;return{invested,value,pnl,pct:invested?pnl/invested*100:0,worst:worst*100};
}
function loadStock(savedValues=null){
 const x=stock();if(!x)return;const months=x.m.map(r=>r[0]),current=x.m.at(-1)[1],risk=x.r||{};
 start.innerHTML=months.map((m,i)=>`<option value="${m}" ${i===Math.max(0,months.length-120)?'selected':''}>${m}</option>`).join('');
 end.innerHTML=months.map((m,i)=>`<option value="${m}" ${i===months.length-1?'selected':''}>${m}</option>`).join('');
 restorePlan(savedValues);if(!savedValues||savedValues.riskTarget==null)document.getElementById('riskTarget').value=(risk.peak||current).toFixed(2);if(!savedValues||savedValues.riskDeclineMonths==null)document.getElementById('riskUseCycleTime').checked=true;applyCycleTime();calculateRisk();
}
function calculateRisk(){
 const x=stock();if(!x)return;
 const symbol=ticker.value.trim().toUpperCase(),current=x.m.at(-1)[1],risk=x.r||{},initial=Math.max(0,+document.getElementById('riskInitial').value||0),months=Math.max(1,Math.round(+document.getElementById('riskMonths').value||1)),downMonths=Math.min(months,Math.max(1,Math.round(+document.getElementById('riskDeclineMonths').value||1))),frequency=document.getElementById('riskFrequency').value,periodsPerMonth=frequency==='daily'?21:frequency==='weekly'?4:1,periodsPerYear=periodsPerMonth*12,steps=months*periodsPerMonth,downSteps=downMonths*periodsPerMonth,frequencyLabel=frequency==='daily'?'ทุกวันทำการ':frequency==='weekly'?'ทุกสัปดาห์':'ทุกเดือน',drop=Math.min(.95,Math.max(0,(+document.getElementById('riskDecline').value||0)/100)),target=Math.max(.01,+document.getElementById('riskTarget').value||current),budget=Math.max(0,+document.getElementById('riskBudget').value||0),contribution=updateContribution(),tolerance=Math.max(0,+document.getElementById('riskTolerance').value||0),withDiv=document.getElementById('riskDividend').checked,stress=current*(1-drop),annualDiv=withDiv?(risk.div12||0):0;
 let shares=initial/current,invested=initial,worstPct=0,troughValue=shares*current,usedPeriods=0,divTotal=0;
 const ledger=[];
 if(initial>0)ledger.push({period:'เริ่มต้น',phase:'ราคาปัจจุบัน',price:current,buy:initial,bought:shares,shares,invested,value:initial,pnl:0,pct:0});
 for(let i=1;i<=steps;i++){
  const price=i<=downSteps?current+(stress-current)*i/downSteps:stress+(target-stress)*(i-downSteps)/Math.max(1,steps-downSteps);
  if(annualDiv){const div=shares*(annualDiv/periodsPerYear);divTotal+=div;shares+=div/price;}
  let buy=0,bought=0;
  if(contribution>0&&invested+contribution<=budget+.01){buy=contribution;bought=buy/price;shares+=bought;invested+=buy;usedPeriods++;}
  const value=shares*price,pnl=value-invested,pct=invested?pnl/invested*100:0;
  if(pct/100<worstPct)worstPct=pct/100;if(i===downSteps)troughValue=value;
  if(buy>0)ledger.push({period:`${i}/${steps}`,phase:i<=downSteps?'ราคาลง':'ราคาฟื้น',price,buy,bought,shares,invested,value,pnl,pct});
 }
 const endValue=shares*target,pnl=endValue-invested,avg=shares?invested/shares:0,downside=avg?stress/avg-1:0,upside=avg?target/avg-1:0,desired=budget,shortfall=Math.max(0,initial-budget),overRisk=Math.abs(worstPct*100)>tolerance,liquid=(risk.medianValue30||0)>=1000000;
 const stats=[['ราคาปัจจุบัน',fmt(current)+' บาท'],['ราคาวิกฤต',fmt(stress)+' บาท'],['เงินที่ใช้จริง',fmt(invested)+' บาท'],['ต้นทุนเฉลี่ย',fmt(avg)+' บาท'],['มูลค่าที่จุดต่ำ',fmt(troughValue)+' บาท'],['ขาดทุนสูงสุด',`${fmt(worstPct*100)}%`],['Downside จากต้นทุน',`${fmt(downside*100)}%`],['Upside ถึงเป้าหมาย',`${upside>=0?'+':''}${fmt(upside*100)}%`],['มูลค่าเมื่อถึงเป้า',fmt(endValue)+' บาท'],['กำไร/ขาดทุนเป้า',`${pnl>=0?'+':''}${fmt(pnl)} บาท`],['เงินที่แผนต้องการ',fmt(desired)+' บาท'],['DCA ได้จริง',`${usedPeriods}/${steps} งวด`]];
 document.getElementById('riskGrid').innerHTML=stats.map(s=>`<div class="dca-stat"><small>${s[0]}</small><b>${s[1]}</b></div>`).join('');
 document.getElementById('riskLedgerBody').innerHTML=ledger.map(r=>`<tr><td>${r.period}</td><td>${r.phase}</td><td>${fmt(r.price)}</td><td>${fmt(r.buy)}</td><td>${fmt(r.bought,4)}</td><td>${fmt(r.shares,4)}</td><td>${fmt(r.invested)}</td><td>${fmt(r.invested/r.shares)}</td><td>${fmt(r.value)}</td>${pnlCell(r.pnl,r.pct)}</tr>`).join('');
 const common={current,steps,initial,contribution,budget,annualDiv,periodsPerYear},scenarios=[
  ['ฟื้นเร็ว','ลงน้อยกว่าและใช้เวลาครึ่งหนึ่ง',current*(1-drop*.75),target,Math.max(1,Math.round(downSteps*.5))],
  ['ตาม Cycle','ค่ากลางของแผนปัจจุบัน',stress,target,downSteps],
  ['ขาลงยาว','ลงลึกขึ้นและใช้เวลานาน 1.5 เท่า',current*(1-Math.min(.95,drop*1.25)),target,Math.min(steps,Math.max(1,Math.round(downSteps*1.5)))],
  ['ไม่ฟื้น','ลงลึกแล้วทรงตัวถึงจบแผน',current*(1-Math.min(.95,drop*1.25)),current*(1-Math.min(.95,drop*1.25)),downSteps]
 ].map(s=>({name:s[0],desc:s[1],...simulateScenario({...common,bottom:s[2],target:s[3],downSteps:s[4]})}));
 document.getElementById('dcaScenarioGrid').innerHTML=scenarios.length?scenarios.map(s=>`<div class="scenario-card"><small>${s.name}</small><b class="${s.pnl>=0?'gain':'loss'}">${signed(s.pnl)} บาท</b><small>ผลตอบแทน ${signed(s.pct)}%<br>ขาดทุนสูงสุด ${fmt(s.worst)}%<br>${s.desc}</small></div>`).join(''):'<div class="scenario-placeholder">ไม่สามารถคำนวณสถานการณ์ได้ กรุณาตรวจค่าที่กรอก</div>';
 const safety=[];const addSafety=(level,text)=>safety.push({level,text});
 if(current<=Number(risk.low252||0)*1.02)addSafety('danger',`ราคาอยู่ใกล้จุดต่ำสุด 52 สัปดาห์ ${fmt(risk.low252)} บาท`);else addSafety('ok',`ราคายังเหนือจุดต่ำสุด 52 สัปดาห์ ${fmt(risk.low252)} บาท`);
 if(risk.return60<=-20)addSafety('danger',`ราคาลด ${fmt(Math.abs(risk.return60))}% ใน 60 วันทำการ`);else if(risk.return60<=-10)addSafety('watch',`Momentum 60 วันยังติดลบ ${fmt(risk.return60)}%`);else addSafety('ok',`Momentum 60 วัน ${signed(risk.return60||0)}%`);
 if((risk.medianValue30||0)<1000000)addSafety('danger','สภาพคล่องต่ำกว่า 1 ล้านบาท/วัน');else if(risk.liquidityTrend30<=-30)addSafety('watch',`สภาพคล่อง 30 วันลดลง ${fmt(Math.abs(risk.liquidityTrend30))}%`);else addSafety('ok',`สภาพคล่อง 30 วัน ${signed(risk.liquidityTrend30||0)}% จากช่วงก่อนหน้า`);
 const normalDown=risk.downDaysMedian||risk.downDays;if(normalDown&&risk.daysSinceHigh252>normalDown*1.5)addSafety('watch',`ห่างจากจุดสูง 52 สัปดาห์ ${risk.daysSinceHigh252} วัน นานกว่า Cycle ปกติ`);else if(normalDown)addSafety('ok',`ห่างจากจุดสูง 52 สัปดาห์ ${risk.daysSinceHigh252} วัน เทียบ Cycle ${normalDown} วัน`);
 document.getElementById('safetyMonitor').innerHTML=safety.map(s=>`<div class="safety-item ${s.level}">${s.level==='danger'?'⚠':s.level==='watch'?'•':'✓'} ${s.text}</div>`).join('');
 const headline=document.getElementById('riskHeadline');headline.className='risk-headline '+(overRisk?'danger':'safe');headline.textContent=overRisk?'⚠ Scenario นี้ขาดทุนเกินระดับที่คุณรับได้':'✓ Scenario นี้ยังอยู่ในกรอบขาดทุนที่กำหนด';
 document.getElementById('riskPathFill').style.width=Math.min(100,invested/(budget||desired)*100)+'%';document.getElementById('riskPathText').textContent=`ใช้งบ ${fmt(invested)} จาก ${fmt(budget||desired)} บาท`;
 const warnings=[];if(shortfall)warnings.push(`เงินซื้อครั้งแรกสูงกว่างบรวม ${fmt(shortfall)} บาท กรุณาปรับงบ`);if(overRisk)warnings.push(`ขาดทุนสูงสุด ${fmt(Math.abs(worstPct*100))}% มากกว่าเกณฑ์ ${fmt(tolerance)}%`);if(!liquid)warnings.push('มูลค่าซื้อขายมัธยฐานต่ำกว่า 1 ล้านบาท/วัน อาจซื้อหรือขายตามแผนได้ยาก');if(risk.trough&&stress<risk.trough)warnings.push(`ราคาวิกฤตต่ำกว่าแนวรับอ้างอิง ${fmt(risk.trough)} บาท`);
 document.getElementById('riskWarnings').innerHTML=(warnings.length?warnings:['เงื่อนไขงบประมาณ ความเสี่ยง และสภาพคล่องผ่านเกณฑ์ที่ตั้งไว้']).map(w=>`<div class="risk-warning ${warnings.length?'':'risk-ok'}">${warnings.length?'⚠ ':''}${w}</div>`).join('');
 const peakLabel=risk.peakProjected?'เป้าขาขึ้นประมาณจากรอบในอดีต':'แนวต้าน peak เดิมที่อยู่เหนือราคาปัจจุบัน',troughLabel=risk.troughProjected?'แนวรับประมาณจากรอบในอดีต':'แนวรับ trough เดิมที่อยู่ต่ำกว่าราคาปัจจุบัน';
 const cycleTimeText=document.getElementById('riskUseCycleTime').checked&&risk.downDays?`ใช้ระยะขาลงเฉลี่ยจาก Cycle ${risk.downDays} วัน (ประมาณ ${downMonths} เดือน)`:`กำหนดระยะขาลงเอง ${downMonths} เดือน`;
 document.getElementById('riskDetail').textContent=`${symbol}: DCA ${frequencyLabel} งวดละ ${fmt(contribution)} บาท · ${cycleTimeText} · สมมติราคาลง ${fmt(drop*100)}% แล้วฟื้นไป ${fmt(target)} บาทภายในเดือนที่ ${months} · ${peakLabel} ${fmt(risk.peak)} บาท · ${troughLabel} ${fmt(risk.trough)} บาท · ปันผลจำลองสะสม ${fmt(divTotal)} บาท`;
 document.getElementById('riskResult').classList.add('show');
 if(activePlan&&plans.has(activePlan))plans.get(activePlan).values=capturePlan();
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
ticker.addEventListener('change',()=>activatePlan(ticker.value.trim().toUpperCase()));ticker.addEventListener('input',()=>{const symbol=ticker.value.trim().toUpperCase();if(DATA[symbol])activatePlan(symbol)});document.getElementById('riskCalculate').onclick=()=>{calculateRisk();renderPlanTabs()};
document.getElementById('riskFrequency').addEventListener('change',()=>{const f=document.getElementById('riskFrequency').value;document.getElementById('riskContributionLabel').childNodes[0].nodeValue=f==='daily'?'DCA ต่อวันทำการ — คำนวณอัตโนมัติ (บาท)':f==='weekly'?'DCA ต่อสัปดาห์ — คำนวณอัตโนมัติ (บาท)':'DCA ต่อเดือน — คำนวณอัตโนมัติ (บาท)';calculateRisk();});
['riskInitial','riskBudget','riskMonths'].forEach(id=>document.getElementById(id).addEventListener('input',()=>{updateContribution();if(activePlan&&plans.has(activePlan))plans.get(activePlan).values=capturePlan();renderPlanTabs()}));
document.getElementById('riskUseCycleTime').addEventListener('change',()=>{applyCycleTime();calculateRisk();});document.getElementById('riskDeclineMonths').addEventListener('input',()=>{document.getElementById('riskUseCycleTime').checked=false;});
document.querySelectorAll('.stress-presets button').forEach(b=>b.onclick=()=>{document.getElementById('riskDecline').value=b.dataset.drop;calculateRisk();renderPlanTabs()});document.getElementById('dcaCalculate').onclick=calculateHistory;
document.getElementById('dcaBatchCreate').addEventListener('click',()=>{const raw=document.getElementById('dcaBatchTickers').value.toUpperCase(),symbols=[...new Set(raw.split(/[\s,;]+/).filter(Boolean))],valid=symbols.filter(s=>DATA[s]),invalid=symbols.filter(s=>!DATA[s]);if(!valid.length){document.getElementById('dcaBatchNote').textContent='ไม่พบ Ticker ที่กรอกในฐานข้อมูล';return;}saveActivePlan();const base=capturePlan();valid.slice(0,12).forEach(s=>{if(!plans.has(s))plans.set(s,{values:{...base,riskTarget:null,riskDeclineMonths:null,riskUseCycleTime:true}})});activatePlan(valid[0]);document.getElementById('dcaBatchTickers').value='';if(invalid.length)document.getElementById('dcaBatchNote').innerHTML+=` · ไม่พบ: ${invalid.join(', ')}`;});
plans.set(ticker.value.trim().toUpperCase(),{values:null});activatePlan(ticker.value.trim().toUpperCase());
})();
