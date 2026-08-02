
let CYCLES = __CYCLES_JSON__;

const tickerListEl = document.getElementById('cycTickerList');
const cycleSourceStatus = document.getElementById('cycleSourceStatus');
function renderCycleTickerOptions(){
  tickerListEl.innerHTML = '';
  for(const t of Object.keys(CYCLES).sort()){
    const opt = document.createElement('option');
    opt.value = t;
    tickerListEl.appendChild(opt);
  }
}
renderCycleTickerOptions();

const tickerInput = document.getElementById('cycTicker');
const tickerInfo = document.getElementById('cycTickerInfo');
const adjBadge = document.getElementById('adjBadge');
const analyzeBtn = document.getElementById('analyzeBtn');
const resultPanel = document.getElementById('cycResultPanel');
let cycleCloudPromise = null;

async function loadCloudCycles(){
  if(cycleCloudPromise) return cycleCloudPromise;
  cycleCloudPromise = (async()=>{
    cycleSourceStatus.className = 'cycle-source-status loading';
    cycleSourceStatus.textContent = 'Cycle: กำลังโหลดข้อมูล Cloud…';
    const controller = new AbortController();
    const timer = setTimeout(()=>controller.abort(), 30000);
    let cloudError = null;
    try{
      const manifest = await window.marketManifestReady;
      if(manifest && !manifest.summaries?.includes('cycles')) throw new Error('Cycle summary unavailable');
      const response = await fetch(`${MARKET_API_BASE}/v1/summaries/cycles`, {headers:{Accept:'application/json'}, cache:'no-store', signal:controller.signal});
      if(!response.ok) throw new Error(`Cycle API HTTP ${response.status}`);
      const payload = await response.json();
      if(payload.name !== 'cycles' || !payload.summary || Array.isArray(payload.summary)) throw new Error('invalid Cycle response');
      CYCLES = payload.summary;
      renderCycleTickerOptions();
      if(!CYCLES[tickerInput.value.trim().toUpperCase()]) tickerInput.value = CYCLES.PTT ? 'PTT' : Object.keys(CYCLES).sort()[0];
      checkTicker();
      if(resultPanel.classList.contains('show')) analyzeBtn.click();
      cycleSourceStatus.className = 'cycle-source-status online';
      cycleSourceStatus.textContent = `Cycle Cloud ${formatMarketDate(payload.dataAsOf)} · ${Object.keys(CYCLES).length.toLocaleString('en-US')} หุ้น`;
      return true;
    }catch(error){
      cloudError = error;
    }
    try{
      const response = await fetch(new URL('data/cycles_compact.json', document.baseURI), {headers:{Accept:'application/json'}, cache:'no-store'});
      if(!response.ok) throw new Error(`Cycle fallback HTTP ${response.status}`);
      const fallback = await response.json();
      if(!fallback || Array.isArray(fallback) || !Object.keys(fallback).length) throw new Error('invalid Cycle fallback');
      CYCLES = fallback;
      renderCycleTickerOptions();
      if(!CYCLES[tickerInput.value.trim().toUpperCase()]) tickerInput.value = CYCLES.PTT ? 'PTT' : Object.keys(CYCLES).sort()[0];
      checkTicker();
      cycleSourceStatus.className = 'cycle-source-status fallback';
      cycleSourceStatus.textContent = `Cycle: ข้อมูลสำรอง ${Object.keys(CYCLES).length.toLocaleString('en-US')} หุ้น`;
      cycleSourceStatus.title = `Cloud unavailable: ${cloudError?.message || 'unknown error'}`;
      return false;
    }catch(fallbackError){
      cycleSourceStatus.className = 'cycle-source-status error';
      cycleSourceStatus.textContent = 'Cycle: โหลดข้อมูลไม่สำเร็จ';
      cycleSourceStatus.title = `${cloudError?.message || 'Cloud unavailable'}; ${fallbackError.message}`;
      return false;
    }finally{
      clearTimeout(timer);
    }
  })();
  return cycleCloudPromise;
}

function fmtNum(n, dec=2){
  return n.toLocaleString('en-US', {minimumFractionDigits:dec, maximumFractionDigits:dec});
}

function checkTicker(){
  const t = tickerInput.value.trim().toUpperCase();
  if(!CYCLES[t]){
    tickerInfo.textContent = tickerInput.value ? 'ไม่พบสัญลักษณ์หุ้นนี้ในฐานข้อมูล (หรือมีจุดข้อมูลน้อยเกินไปในการหา cycle)' : '';
    tickerInfo.className = 'ticker-info err';
    adjBadge.className = 'badge';
    analyzeBtn.disabled = true;
    return;
  }
  const c = CYCLES[t];
  tickerInfo.textContent = `พบ ${c.e.length} จุด (peak/trough) ตลอดช่วงข้อมูล`;
  tickerInfo.className = 'ticker-info ok';
  analyzeBtn.disabled = false;
  if(c.sa){
    adjBadge.textContent = '✓ ปรับราคาตาม split ที่ยืนยันแล้วก่อนวิเคราะห์';
    adjBadge.className = 'badge show';
  } else {
    adjBadge.textContent = '⚠ ไม่มีข้อมูล split ยืนยัน — ใช้ราคาดิบ (อาจมี cycle ปลอมถ้าหุ้นนี้เคยแตกพาร์)';
    adjBadge.className = 'badge warn';
  }
}
tickerInput.addEventListener('input', checkTicker);
tickerInput.addEventListener('change', checkTicker);

function buildCycles(events){
  const cycles = [];
  for(let i=1;i<events.length;i++){
    const prev = events[i-1], cur = events[i];
    const [pd,pp,,prevPreDays] = prev, [cd,cp] = cur;
    const days = Math.round((new Date(cd) - new Date(pd)) / 86400000);
    const pct = ((cp - pp) / pp) * 100;
    cycles.push({
      from: pd, to: cd, days,
      direction: cp > pp ? 'up' : 'down',
      pct,
      preDays: prevPreDays || 0   // วันที่ราคานิ่ง+volume ขึ้น ก่อนเริ่ม cycle นี้ (0 = ไม่เจอ)
    });
  }
  return cycles;
}

function renderChart(events){
  const svg = document.getElementById('waveChart');
  svg.innerHTML = '';
  const W = 900, H = 380, padL = 55, padR = 20, padT = 20, padB = 30;
  const dates = events.map(e => new Date(e[0]).getTime());
  const prices = events.map(e => e[1]);
  const logPrices = prices.map(p => Math.log10(Math.max(p, 0.001)));
  const minD = Math.min(...dates), maxD = Math.max(...dates);
  const minLP = Math.min(...logPrices), maxLP = Math.max(...logPrices);

  const x = d => padL + (maxD>minD ? (d - minD)/(maxD-minD) : 0.5) * (W-padL-padR);
  const y = lp => padT + (1 - (maxLP>minLP ? (lp - minLP)/(maxLP-minLP) : 0.5)) * (H-padT-padB);

  const ns = 'http://www.w3.org/2000/svg';
  // gridlines + y-axis price labels (5 ticks)
  for(let i=0;i<=4;i++){
    const lp = minLP + (maxLP-minLP)*i/4;
    const priceVal = Math.pow(10, lp);
    const yy = y(lp);
    const line = document.createElementNS(ns,'line');
    line.setAttribute('x1',padL); line.setAttribute('x2',W-padR);
    line.setAttribute('y1',yy); line.setAttribute('y2',yy);
    line.setAttribute('stroke','#223040'); line.setAttribute('stroke-width','1');
    svg.appendChild(line);
    const txt = document.createElementNS(ns,'text');
    txt.setAttribute('x', padL-8); txt.setAttribute('y', yy+3);
    txt.setAttribute('text-anchor','end'); txt.setAttribute('class','axis-label');
    txt.textContent = priceVal >= 100 ? priceVal.toFixed(0) : priceVal.toFixed(2);
    svg.appendChild(txt);
  }
  // x-axis year labels (~6 ticks)
  const nTicks = 6;
  for(let i=0;i<=nTicks;i++){
    const dd = minD + (maxD-minD)*i/nTicks;
    const xx = x(dd);
    const txt = document.createElementNS(ns,'text');
    txt.setAttribute('x', xx); txt.setAttribute('y', H-padB+18);
    txt.setAttribute('text-anchor','middle'); txt.setAttribute('class','axis-label');
    txt.textContent = new Date(dd).getFullYear();
    svg.appendChild(txt);
  }

  // wave polyline
  const pts = events.map((e,i) => `${x(dates[i])},${y(logPrices[i])}`).join(' ');
  const poly = document.createElementNS(ns,'polyline');
  poly.setAttribute('points', pts);
  poly.setAttribute('class','wave-line');
  svg.appendChild(poly);

  // points
  events.forEach((e,i) => {
    const cx = x(dates[i]), cy = y(logPrices[i]);
    const circ = document.createElementNS(ns,'circle');
    circ.setAttribute('cx',cx); circ.setAttribute('cy',cy); circ.setAttribute('r', 4);
    circ.setAttribute('class', e[2]===1 ? 'point-peak' : 'point-trough');
    const title = document.createElementNS(ns,'title');
    title.textContent = `${e[0]} · ${e[2]===1?'Peak':'Trough'} · ${fmtNum(e[1],2)}`;
    circ.appendChild(title);
    svg.appendChild(circ);
  });
}

function renderSummary(cycles){
  const ups = cycles.filter(c => c.direction === 'up');
  const downs = cycles.filter(c => c.direction === 'down');
  const avg = arr => arr.length ? arr.reduce((s,c)=>s+c.days,0)/arr.length : 0;
  const grid = document.getElementById('summaryGrid');
  grid.innerHTML = `
    <div class="stat"><div class="stat-label">รอบขาขึ้น เฉลี่ย (วัน)</div><div class="stat-value up">${fmtNum(avg(ups),0)}</div></div>
    <div class="stat"><div class="stat-label">รอบขาลง เฉลี่ย (วัน)</div><div class="stat-value down">${fmtNum(avg(downs),0)}</div></div>
    <div class="stat"><div class="stat-label">จำนวนรอบขาขึ้น/ขาลง</div><div class="stat-value">${ups.length} / ${downs.length}</div></div>
    <div class="stat"><div class="stat-label">รอบยาวที่สุด (วัน)</div><div class="stat-value">${cycles.length ? Math.max(...cycles.map(c=>c.days)) : 0}</div></div>
  `;
}

function renderScenario(stock, events, cycles){
  const latest = stock.l || [events[events.length-1][0], events[events.length-1][1]];
  const [latestDate,currentPrice] = latest;
  const amountInput = document.getElementById('scenarioInvestment');
  const amount = Math.max(0, Number(amountInput.value) || 0);
  const past = events.filter(e => e[0] < latestDate);
  const ups = cycles.filter(c => c.direction === 'up');
  const downs = cycles.filter(c => c.direction === 'down');
  const avgDays = arr => arr.length ? arr.reduce((sum,c)=>sum+c.days,0)/arr.length : 0;
  const avgUpDays = avgDays(ups), avgDownDays = avgDays(downs);
  const median = values => { if(!values.length) return 0; const a=values.slice().sort((x,y)=>x-y),m=Math.floor(a.length/2); return a.length%2?a[m]:(a[m-1]+a[m])/2; };
  const medianUpPct = median(ups.map(c=>c.pct));
  const medianDownPct = Math.abs(median(downs.map(c=>c.pct)));
  const higherPeaks = past.filter(e=>e[2]===1 && e[1]>currentPrice).sort((a,b)=>a[1]-b[1]);
  const lowerTroughs = past.filter(e=>e[2]===0 && e[1]<currentPrice).sort((a,b)=>b[1]-a[1]);
  const upsidePoint = higherPeaks.length
    ? {price:higherPeaks[0][1],date:higherPeaks[0][0],method:'แนวต้านจาก peak ในอดีตที่อยู่เหนือราคาปัจจุบันใกล้ที่สุด'}
    : {price:currentPrice*(1+Math.max(.05,medianUpPct/100)),date:null,method:`ประมาณจากค่ามัธยฐานรอบขาขึ้น +${fmtNum(medianUpPct,2)}% (ไม่มี peak เดิมอยู่เหนือราคา)`};
  const downsidePoint = lowerTroughs.length
    ? {price:lowerTroughs[0][1],date:lowerTroughs[0][0],method:'แนวรับจาก trough ในอดีตที่อยู่ต่ำกว่าราคาปัจจุบันใกล้ที่สุด'}
    : {price:currentPrice*(1-Math.min(.80,Math.max(.05,medianDownPct/100))),date:null,method:`ประมาณจากค่ามัธยฐานรอบขาลง -${fmtNum(medianDownPct,2)}% (ไม่มี trough เดิมอยู่ต่ำกว่าราคา)`};
  const shares = currentPrice > 0 ? amount/currentPrice : 0;
  document.getElementById('scenarioCurrent').innerHTML = `ราคาซื้อล่าสุด <b>${fmtNum(currentPrice,2)} บาท</b> ณ ${latestDate} · เงินลงทุน ${fmtNum(amount,0)} บาท · ประมาณ ${fmtNum(shares,2)} หุ้น`;
  function card(point, kind){
    if(!point) return `<div class="scenario-card"><div class="scenario-title">ไม่มีข้อมูลอ้างอิงเพียงพอ</div></div>`;
    const target = point.price, pct = (target/currentPrice-1)*100, pnl = shares*(target-currentPrice);
    const positive = pnl >= 0;
    const isPeak = kind === 'peak';
    const travelDays = isPeak ? avgUpDays : avgDownDays;
    return `<div class="scenario-card ${isPeak?'up':'down'}">
      <div class="scenario-title">${isPeak?'แนวต้าน / เป้าหมายขาขึ้นถัดไป':'แนวรับ / ความเสี่ยงขาลงถัดไป'}</div>
      <div class="scenario-target">${fmtNum(target,2)} บาท</div>
      <div class="scenario-result ${positive?'positive':'negative'}">${pnl>=0?'+':''}${fmtNum(pnl,2)} บาท (${pct>=0?'+':''}${fmtNum(pct,2)}%)</div>
      <div class="scenario-meta">${point.date?'จุดอ้างอิงวันที่ '+point.date:'ระดับประมาณการ ไม่มีวันที่ในอดีต'}<br>${point.method}<br>${isPeak?'Upside':'Downside'} ${pct>=0?'+':''}${fmtNum(pct,2)}%<br>เวลาเฉลี่ยในอดีต ${isPeak?'trough → peak':'peak → trough'}: ${fmtNum(travelDays,0)} วัน (${isPeak?ups.length:downs.length} รอบ)</div>
    </div>`;
  }
  document.getElementById('scenarioGrid').innerHTML = card(upsidePoint,'peak') + card(downsidePoint,'trough');
}

function renderTable(cycles){
  const tbody = document.getElementById('cycleTable');
  tbody.innerHTML = cycles.slice().reverse().map(c => `
    <tr>
      <td class="dir-${c.direction}">${c.direction === 'up' ? '▲ ขาขึ้น' : '▼ ขาลง'}</td>
      <td>${c.from}</td>
      <td>${c.to}</td>
      <td>${c.days}</td>
      <td class="dir-${c.direction}">${c.pct>=0?'+':''}${fmtNum(c.pct,2)}%</td>
      <td>${c.preDays > 0 ? c.preDays + ' วัน' : '—'}</td>
    </tr>
  `).join('');
}

analyzeBtn.addEventListener('click', () => {
  const t = tickerInput.value.trim().toUpperCase();
  if(!CYCLES[t]) return;
  const events = CYCLES[t].e; // [date, price, isPeak]
  const cycles = buildCycles(events);
  renderSummary(cycles);
  renderScenario(CYCLES[t], events, cycles);
  renderChart(events);
  renderTable(cycles);
  resultPanel.classList.add('show');
  resultPanel.scrollIntoView({behavior:'smooth', block:'nearest'});
});
document.getElementById('scenarioInvestment').addEventListener('input', () => {
  const t = tickerInput.value.trim().toUpperCase();
  if(!CYCLES[t] || !resultPanel.classList.contains('show')) return;
  const events = CYCLES[t].e;
  renderScenario(CYCLES[t], events, buildCycles(events));
});

// default example
document.getElementById('navCycle').addEventListener('click', loadCloudCycles);
tickerInput.value = 'PTT';
checkTicker();
