
const CYCLES = __CYCLES_JSON__;

const tickerListEl = document.getElementById('tickerList');
const tickerNames = Object.keys(CYCLES).sort();
for(const t of tickerNames){
  const opt = document.createElement('option');
  opt.value = t;
  tickerListEl.appendChild(opt);
}

const tickerInput = document.getElementById('ticker');
const tickerInfo = document.getElementById('tickerInfo');
const adjBadge = document.getElementById('adjBadge');
const analyzeBtn = document.getElementById('analyzeBtn');
const resultPanel = document.getElementById('resultPanel');

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
    const [pd,pp] = prev, [cd,cp] = cur;
    const days = Math.round((new Date(cd) - new Date(pd)) / 86400000);
    const pct = ((cp - pp) / pp) * 100;
    cycles.push({
      from: pd, to: cd, days,
      direction: cp > pp ? 'up' : 'down',
      pct
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

function renderTable(cycles){
  const tbody = document.getElementById('cycleTable');
  tbody.innerHTML = cycles.slice().reverse().map(c => `
    <tr>
      <td class="dir-${c.direction}">${c.direction === 'up' ? '▲ ขาขึ้น' : '▼ ขาลง'}</td>
      <td>${c.from}</td>
      <td>${c.to}</td>
      <td>${c.days}</td>
      <td class="dir-${c.direction}">${c.pct>=0?'+':''}${fmtNum(c.pct,2)}%</td>
    </tr>
  `).join('');
}

analyzeBtn.addEventListener('click', () => {
  const t = tickerInput.value.trim().toUpperCase();
  if(!CYCLES[t]) return;
  const events = CYCLES[t].e; // [date, price, isPeak]
  const cycles = buildCycles(events);
  renderSummary(cycles);
  renderChart(events);
  renderTable(cycles);
  resultPanel.classList.add('show');
  resultPanel.scrollIntoView({behavior:'smooth', block:'nearest'});
});

// default example
tickerInput.value = 'PTT';
checkTicker();
