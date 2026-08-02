(function(){
let SIGNALS = __ACCUMULATION_JSON__;
const UPDATED_AT = __UPDATED_AT_JSON__;
let DIVIDENDS = __SCAN_DIVIDENDS_JSON__;
const LABELS = {confirmed:'Confirmed',building:'Building Base',watch:'Watch',invalidated:'Invalidated',neutral:'Neutral',illiquid:'สภาพคล่องต่ำ'};

document.getElementById('scanUpdated').textContent = 'ข้อมูลล่าสุดอัปเดตเมื่อ: ' + UPDATED_AT;
const filterInput = document.getElementById('scanFilter');
const statusSelect = document.getElementById('scanStatus');
const minScoreSelect = document.getElementById('scanMinScore');
const sortSelect = document.getElementById('scanSort');
const tbody = document.getElementById('scanTable');
const countEl = document.getElementById('scanCount');
const errorEl = document.getElementById('scanFilterError');
const liquidityWarningSelect = document.getElementById('scanLiquidityWarning');
const dividendModeSelect = document.getElementById('scanDividendMode');
const dividendYearsEl = document.getElementById('scanDividendYears');
const dividendStopMonthsEl = document.getElementById('scanDividendStopMonths');
let referenceDate = new Date();
const numericFilters = {
  setupMin:'scanSetupMin', demandMin:'scanDemandMin', confirmationMin:'scanConfirmationMin',
  drawdownMin:'scanDrawdownMin', drawdownMax:'scanDrawdownMax', rangeMax:'scanRangeMax',
  demandRatioMin:'scanDemandRatioMin', liquidityMin:'scanLiquidityMin'
};
const numericEls = Object.fromEntries(Object.entries(numericFilters).map(([key,id]) => [key,document.getElementById(id)]));

function statusMatches(status, selected){
  if(selected === 'all') return true;
  if(selected === 'actionable') return ['confirmed','building','watch'].includes(status);
  return status === selected;
}
function scoreBar(value, max){
  const pct = Math.min(100, value / max * 100);
  return `<span class="mini-score"><b>${value}</b><i><em style="width:${pct}%"></em></i></span>`;
}
function compactNumber(value){
  if(value >= 1e9) return (value/1e9).toFixed(1)+'B';
  if(value >= 1e6) return (value/1e6).toFixed(1)+'M';
  if(value >= 1e3) return (value/1e3).toFixed(1)+'K';
  return Math.round(value).toString();
}
function optionalNumber(el){
  return el.value.trim() === '' ? null : Number(el.value);
}
function readAdvancedFilters(){
  return Object.fromEntries(Object.entries(numericEls).map(([key,el]) => [key,optionalNumber(el)]));
}
function dividendInfo(ticker){
  const events=(DIVIDENDS[ticker]||[]).filter(e=>new Date(e.date+'T00:00:00')<=referenceDate).sort((a,b)=>a.date.localeCompare(b.date));
  if(!events.length)return{has:false,continuous:false,stopped:false,last:null,monthsSince:null};
  const years=new Set(events.map(e=>Number(e.date.slice(0,4)))),required=Math.max(1,Number(dividendYearsEl.value)||3),last=events.at(-1).date,lastDate=new Date(last+'T00:00:00'),monthsSince=Math.max(0,(referenceDate-lastDate)/(86400000*30.44)),stopMonths=Math.max(1,Number(dividendStopMonthsEl.value)||12);
  let continuous=true;for(let i=1;i<=required;i++)if(!years.has(referenceDate.getFullYear()-i)){continuous=false;break;}
  return{has:true,continuous,stopped:monthsSince>=stopMonths,last,monthsSince,required};
}
function dividendMatches(ticker){const info=dividendInfo(ticker),mode=dividendModeSelect.value;return mode==='all'||(mode==='continuous'&&info.continuous)||(mode==='stopped'&&info.has&&info.stopped);}
function advancedMatches(s, f){
  const depth = Math.max(0, -s.drawdown52);
  return (f.setupMin === null || s.setup >= f.setupMin) &&
    (f.demandMin === null || s.demand >= f.demandMin) &&
    (f.confirmationMin === null || s.confirmation >= f.confirmationMin) &&
    (f.drawdownMin === null || depth >= f.drawdownMin) &&
    (f.drawdownMax === null || depth <= f.drawdownMax) &&
    (f.rangeMax === null || s.range20 <= f.rangeMax) &&
    (f.demandRatioMin === null || s.demandRatio >= f.demandRatioMin) &&
    (f.liquidityMin === null || (s.medianValue30||s.medianValue20) >= f.liquidityMin * 1000000) &&
    (liquidityWarningSelect.value === 'all' || (liquidityWarningSelect.value === 'only' ? s.lowLiquidity30 : !s.lowLiquidity30));
}
function sortRows(rows, mode){
  const sorted = rows.slice();
  const rules = {
    scoreDesc:(a,b)=>b.score-a.score || b.confirmation-a.confirmation,
    confirmationDesc:(a,b)=>b.confirmation-a.confirmation || b.score-a.score,
    demandDesc:(a,b)=>b.demand-a.demand || b.score-a.score,
    drawdownDesc:(a,b)=>a.drawdown52-b.drawdown52,
    liquidityDesc:(a,b)=>(b.medianValue30||b.medianValue20)-(a.medianValue30||a.medianValue20),
    tickerAsc:(a,b)=>a.t.localeCompare(b.t)
  };
  return sorted.sort(rules[mode] || rules.scoreDesc);
}
function render(){
  const q = filterInput.value.trim().toUpperCase();
  const selected = statusSelect.value;
  const minScore = Number(minScoreSelect.value);
  const advanced = readAdvancedFilters();
  const invalidRange = advanced.drawdownMin !== null && advanced.drawdownMax !== null && advanced.drawdownMin > advanced.drawdownMax;
  errorEl.textContent = invalidRange ? 'ระยะลงขั้นต่ำต้องไม่มากกว่าระยะลงสูงสุด' : '';
  const filtered = invalidRange ? [] : SIGNALS.filter(s => statusMatches(s.status, selected) && s.score >= minScore && (!q || s.t.includes(q)) && advancedMatches(s, advanced) && dividendMatches(s.t));
  const rows = sortRows(filtered, sortSelect.value);
  const summary = rows.reduce((a,s) => (a[s.status]=(a[s.status]||0)+1,a), {});
  const lowLiquidityCount = rows.filter(s => s.lowLiquidity30).length;
  countEl.textContent = `พบ ${rows.length} หุ้น · Confirmed ${summary.confirmed||0} · Building ${summary.building||0} · Watch ${summary.watch||0} · เตือนสภาพคล่อง 30 วัน ${lowLiquidityCount}`;
  tbody.innerHTML = rows.map(s => {const div=dividendInfo(s.t),dividendHtml=!div.has?'<span class="dividend-pill">ไม่มีข้อมูล</span>':div.continuous?`<span class="dividend-pill continuous">ต่อเนื่อง ${div.required} ปี</span><small>ล่าสุด ${div.last}</small>`:div.stopped?`<span class="dividend-pill stopped">หยุด ${Math.floor(div.monthsSince)} เดือน</span><small>ล่าสุด ${div.last}</small>`:`<span class="dividend-pill">มีการจ่าย</span><small>ล่าสุด ${div.last}</small>`;return `
    <tr class="scan-row" data-ticker="${s.t}">
      <td>${s.t}<small>${s.date}</small></td>
      <td><span class="status-pill ${s.status}">${LABELS[s.status]}</span></td>
      <td><strong class="total-score">${s.score}</strong></td>
      <td>${scoreBar(s.setup,40)}</td><td>${scoreBar(s.demand,30)}</td><td>${scoreBar(s.confirmation,30)}</td>
      <td class="${s.drawdown52 < 0 ? 'dir-down' : ''}">${s.drawdown52.toFixed(2)}%</td>
      <td class="liquidity-cell"><b>${compactNumber(s.avgVolume30||0)} หุ้น/วัน</b><small>มัธยฐาน ${(s.medianValue30||s.medianValue20)/1000000 < 0.01 ? '<0.01' : ((s.medianValue30||s.medianValue20)/1000000).toFixed(2)} ลบ./วัน</small>${s.lowLiquidity30 ? '<span class="liquidity-warning">⚠ ต่ำมากต่อเนื่อง 30 วัน</span>' : ''}</td>
      <td class="dividend-cell">${dividendHtml}</td>
      <td class="reason-cell">${s.reasons.length ? s.reasons.join(' · ') : 'ยังไม่มีเงื่อนไขเด่น'}</td>
    </tr>`}).join('');
  tbody.querySelectorAll('.scan-row').forEach(row => row.addEventListener('click', () => {
    document.getElementById('navCycle').click();
    const input = document.getElementById('cycTicker');
    input.value = row.dataset.ticker;
    input.dispatchEvent(new Event('change'));
    document.getElementById('analyzeBtn').click();
  }));
}
[filterInput,statusSelect,minScoreSelect,sortSelect,liquidityWarningSelect,dividendModeSelect,dividendYearsEl,dividendStopMonthsEl,...Object.values(numericEls)].forEach(el => el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', render));
document.querySelectorAll('.filter-preset').forEach(button => button.addEventListener('click', () => {
  Object.values(numericEls).forEach(el => el.value = '');
  statusSelect.value = 'actionable'; minScoreSelect.value = '40'; liquidityWarningSelect.value='all';dividendModeSelect.value='all';
  if(button.dataset.preset === 'nearConfirm'){ numericEls.confirmationMin.value='18'; numericEls.setupMin.value='18'; }
  if(button.dataset.preset === 'tightBase'){ numericEls.setupMin.value='20'; numericEls.rangeMax.value='12'; }
  if(button.dataset.preset === 'strongDemand'){ numericEls.demandMin.value='18'; numericEls.demandRatioMin.value='1.2'; }
  render();
}));
document.getElementById('scanReset').addEventListener('click', () => {
  filterInput.value=''; statusSelect.value='actionable'; minScoreSelect.value='40'; sortSelect.value='scoreDesc';
  liquidityWarningSelect.value='all';
  dividendModeSelect.value='all';dividendYearsEl.value='3';dividendStopMonthsEl.value='12';
  Object.values(numericEls).forEach(el => el.value=''); render();
});
let scanLoadPromise=null;
async function loadScanData(){if(scanLoadPromise)return scanLoadPromise;const badge=document.getElementById('scanSourceStatus');scanLoadPromise=(async()=>{badge.className='feature-source-status loading';badge.textContent='สะสม: กำลังโหลดข้อมูล Cloud…';let cloudError;try{const [a,d]=await Promise.all(['accumulation','dividends'].map(async name=>{const r=await fetch(`${MARKET_API_BASE}/v1/summaries/${name}`,{headers:{Accept:'application/json'},cache:'no-store'});if(!r.ok)throw Error(`${name} HTTP ${r.status}`);return r.json()}));SIGNALS=a.summary;DIVIDENDS=d.summary;referenceDate=new Date((SIGNALS.map(s=>s.date).sort().at(-1)||new Date().toISOString().slice(0,10))+'T00:00:00');badge.className='feature-source-status online';badge.textContent=`สะสม Cloud ${formatMarketDate(a.dataAsOf)} · ${SIGNALS.length.toLocaleString('en-US')} หุ้น`;render();return true}catch(e){cloudError=e}try{const [a,d]=await Promise.all(['accumulation_signals.json','dividends.json'].map(async name=>{const r=await fetch(new URL(`data/${name}`,document.baseURI),{cache:'no-store'});if(!r.ok)throw Error(`${name} HTTP ${r.status}`);return r.json()}));SIGNALS=a;DIVIDENDS=d;referenceDate=new Date((SIGNALS.map(s=>s.date).sort().at(-1)||new Date().toISOString().slice(0,10))+'T00:00:00');badge.className='feature-source-status fallback';badge.textContent=`สะสม: ข้อมูลสำรอง ${SIGNALS.length.toLocaleString('en-US')} หุ้น`;badge.title=cloudError.message;render();return false}catch(e){badge.className='feature-source-status error';badge.textContent='สะสม: โหลดข้อมูลไม่สำเร็จ';badge.title=`${cloudError.message}; ${e.message}`;return false}})();return scanLoadPromise}
document.getElementById('navScan').addEventListener('click',loadScanData);
render();
})();
