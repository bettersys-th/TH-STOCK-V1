
const STOCK_DATA = __DATA_JSON__;
const SPLITS = __SPLITS_JSON__;
const DIVIDENDS = __DIVIDENDS_JSON__;

const tickers = STOCK_DATA.tickers;
const tickerListEl = document.getElementById('tickerList');
const tickerNames = Object.keys(tickers).sort();
for(const t of tickerNames){
  const opt = document.createElement('option');
  opt.value = t;
  tickerListEl.appendChild(opt);
}

const tickerInput = document.getElementById('ticker');
const tickerInfo = document.getElementById('tickerInfo');
const splitBadge = document.getElementById('splitBadge');
const buyYearSel = document.getElementById('buyYear');
const sellYearSel = document.getElementById('sellYear');
const calcBtn = document.getElementById('calcBtn');
const resultPanel = document.getElementById('resultPanel');

function fmtNum(n, dec=2){
  return n.toLocaleString('en-US', {minimumFractionDigits:dec, maximumFractionDigits:dec});
}

// Returns the cumulative share multiplier for splits strictly after buyYear
// and up to and including sellYear (a year-end price already reflects any
// split that happened earlier that same year).
function splitMultiplier(ticker, buyYear, sellYear){
  const events = SPLITS[ticker];
  if(!events) return 1;
  let mult = 1;
  for(const ev of events){
    if(ev.year > Number(buyYear) && ev.year <= Number(sellYear)){
      mult *= ev.ratio;
    }
  }
  return mult;
}

// Sums dividends received between buyYear and sellYear (inclusive), scaling
// the share count held at each dividend's year by any splits that already
// happened between the purchase and that dividend's year. (No reinvestment —
// dividends are just summed as cash.)
function totalDividends(ticker, buyYear, sellYear, initialShares){
  const events = DIVIDENDS[ticker];
  if(!events) return 0;
  let total = 0;
  for(const ev of events){
    if(ev.year >= Number(buyYear) && ev.year <= Number(sellYear)){
      const sharesAtTime = initialShares * splitMultiplier(ticker, buyYear, ev.year);
      total += ev.amount * sharesAtTime;
    }
  }
  return total;
}

// Walks splits + dividends in chronological order. Each dividend buys more
// shares at that year's closing price (approximation — real purchases would
// happen on the ex-dividend date, not year-end). Returns final share count
// plus any "stray" cash that couldn't be reinvested because no price exists
// for that year.
function reinvestWalk(ticker, buyYear, sellYear, initialShares){
  buyYear = Number(buyYear); sellYear = Number(sellYear);
  let events = [];
  (SPLITS[ticker]||[]).forEach(ev => {
    if(ev.year > buyYear && ev.year <= sellYear) events.push({year:ev.year, order:0, type:'split', ratio:ev.ratio});
  });
  (DIVIDENDS[ticker]||[]).forEach(ev => {
    if(ev.year >= buyYear && ev.year <= sellYear) events.push({year:ev.year, order:1, type:'div', amount:ev.amount});
  });
  events.sort((a,b) => a.year - b.year || a.order - b.order);

  let shares = initialShares;
  let strayCash = 0;
  for(const ev of events){
    if(ev.type === 'split'){
      shares *= ev.ratio;
    } else {
      const cash = ev.amount * shares;
      const price = tickers[ticker][ev.year];
      if(price && price > 0){
        shares += cash / price;
      } else {
        strayCash += cash;
      }
    }
  }
  return { shares, strayCash };
}

function populateYears(){
  const t = tickerInput.value.trim().toUpperCase();
  buyYearSel.innerHTML = '';
  sellYearSel.innerHTML = '';
  if(!tickers[t]){
    tickerInfo.textContent = tickerInput.value ? 'ไม่พบสัญลักษณ์หุ้นนี้ในฐานข้อมูล' : '';
    tickerInfo.className = 'ticker-info err';
    splitBadge.className = 'split-badge';
    calcBtn.disabled = true;
    return;
  }
  const years = Object.keys(tickers[t]).map(Number).sort((a,b)=>a-b);
  tickerInfo.textContent = `พบข้อมูล ${years.length} ปี (${years[0]}–${years[years.length-1]})`;
  tickerInfo.className = 'ticker-info ok';
  calcBtn.disabled = false;

  const hasSplitData = !!SPLITS[t];
  const hasDivData = !!DIVIDENDS[t];
  if(hasSplitData || hasDivData){
    let parts = [];
    if(hasSplitData) parts.push('split ✓ (' + SPLITS[t].length + ' ครั้ง)');
    else parts.push('split: ไม่พบ (สันนิษฐานว่าไม่เคยแตกพาร์)');
    if(hasDivData) parts.push('ปันผล ✓ (' + DIVIDENDS[t].length + ' ปีที่มีจ่าย)');
    else parts.push('ปันผล: ไม่มีข้อมูล');
    splitBadge.textContent = '✓ ' + parts.join(' · ');
    splitBadge.className = 'split-badge adjusted';
  } else {
    splitBadge.textContent = '⚠ ยังไม่มีข้อมูล split/ปันผลสำหรับหุ้นนี้ — ตัวเลขเป็นราคาดิบล้วนๆ';
    splitBadge.className = 'split-badge unadjusted';
  }

  for(const y of years){
    const o1 = document.createElement('option');
    o1.value = y; o1.textContent = y;
    buyYearSel.appendChild(o1);
    const o2 = document.createElement('option');
    o2.value = y; o2.textContent = y;
    sellYearSel.appendChild(o2);
  }
  buyYearSel.value = years[0];
  sellYearSel.value = years[years.length-1];
}

tickerInput.addEventListener('input', populateYears);
tickerInput.addEventListener('change', populateYears);

document.getElementById('reinvestToggle').addEventListener('change', () => {
  if(resultPanel.classList.contains('show')) calcBtn.click();
});

calcBtn.addEventListener('click', () => {
  const t = tickerInput.value.trim().toUpperCase();
  if(!tickers[t]) return;
  const buyYear = buyYearSel.value;
  const sellYear = sellYearSel.value;
  const initialShares = parseFloat(document.getElementById('shares').value) || 0;
  const reinvest = document.getElementById('reinvestToggle').checked;

  const buyPrice = tickers[t][buyYear];
  const sellPrice = tickers[t][sellYear];
  const yrs = Math.abs(Number(sellYear) - Number(buyYear));

  const mult = splitMultiplier(t, buyYear, sellYear);
  const finalShares = initialShares * mult;
  const investAmt = buyPrice * initialShares;

  // Capital-gain-only figures (price return, ignoring dividends entirely)
  const capitalOnlyVal = sellPrice * finalShares;
  const totalReturnPct = ((capitalOnlyVal - investAmt) / investAmt) * 100;
  const cagr = yrs > 0 ? (Math.pow(capitalOnlyVal / investAmt, 1/yrs) - 1) * 100 : 0;

  // Combined (price + dividend) figures — mode depends on the reinvest checkbox
  let combinedVal, extraSharesFromReinvest = 0, cashDivTotal = 0;
  const hasDiv = !!DIVIDENDS[t];
  if(hasDiv && reinvest){
    const { shares, strayCash } = reinvestWalk(t, buyYear, sellYear, initialShares);
    extraSharesFromReinvest = shares - finalShares;
    combinedVal = shares * sellPrice + strayCash;
  } else if(hasDiv){
    cashDivTotal = totalDividends(t, buyYear, sellYear, initialShares);
    combinedVal = capitalOnlyVal + cashDivTotal;
  } else {
    combinedVal = capitalOnlyVal;
  }
  const totalReturnDivPct = ((combinedVal - investAmt) / investAmt) * 100;
  const cagrDiv = yrs > 0 ? (Math.pow(combinedVal / investAmt, 1/yrs) - 1) * 100 : 0;
  const divContribution = combinedVal - capitalOnlyVal;

  // --- Render ---
  document.getElementById('finalValue').innerHTML = fmtNum(combinedVal,2) + ' <span>บาท</span>';
  document.getElementById('heroNote').textContent = !hasDiv
    ? 'หุ้นนี้ไม่มีข้อมูลปันผล — เป็น capital gain ล้วนๆ'
    : (reinvest ? '(ปันผลถูกนำไปซื้อหุ้นเพิ่มทุกปีที่จ่าย)' : '(ปันผลสะสมเป็นเงินสด ไม่ reinvest)');

  const trdEl = document.getElementById('totalReturnDiv');
  trdEl.textContent = (totalReturnDivPct>=0?'+':'') + fmtNum(totalReturnDivPct,2) + '%';
  trdEl.className = 'stat-value ' + (totalReturnDivPct>=0?'pos':'neg');

  const trEl = document.getElementById('totalReturn');
  trEl.textContent = (totalReturnPct>=0?'+':'') + fmtNum(totalReturnPct,2) + '%';
  trEl.className = 'stat-value ' + (totalReturnPct>=0?'pos':'neg');

  document.getElementById('years').textContent = yrs + ' ปี';

  const cagrdEl = document.getElementById('cagrDiv');
  cagrdEl.textContent = (cagrDiv>=0?'+':'') + fmtNum(cagrDiv,2) + '%';
  cagrdEl.className = 'stat-value ' + (cagrDiv>=0?'pos':'neg');

  const cagrEl = document.getElementById('cagr');
  cagrEl.textContent = (cagr>=0?'+':'') + fmtNum(cagr,2) + '%';
  cagrEl.className = 'stat-value ' + (cagr>=0?'pos':'neg');

  document.getElementById('divContribution').textContent = (hasDiv ? '+' : '') + fmtNum(divContribution,2) + ' บาท';

  document.getElementById('buyPrice').textContent = fmtNum(buyPrice,2) + ' บาท (' + buyYear + ')';
  document.getElementById('investAmt').textContent = fmtNum(investAmt,2) + ' บาท';
  document.getElementById('sellPrice').textContent = fmtNum(sellPrice,2) + ' บาท (' + sellYear + ')';
  document.getElementById('shareCountInitial').textContent = fmtNum(initialShares,0) + ' หุ้น';

  const adjRow = document.getElementById('shareCountAdjRow');
  if(mult !== 1){
    adjRow.style.display = 'flex';
    document.getElementById('shareCountAdj').textContent = fmtNum(finalShares,0) + ' หุ้น (x' + mult + ' จาก split)';
  } else {
    adjRow.style.display = 'none';
  }

  const divCashRow = document.getElementById('divCashRow');
  const reinvestRow = document.getElementById('reinvestSharesRow');
  const capOnlyRow = document.getElementById('capitalOnlyRow');
  if(hasDiv && reinvest){
    divCashRow.style.display = 'none';
    reinvestRow.style.display = 'flex';
    document.getElementById('reinvestShares').textContent = '+' + fmtNum(extraSharesFromReinvest,1) + ' หุ้น';
    capOnlyRow.style.display = 'flex';
    document.getElementById('capitalOnlyVal').textContent = fmtNum(capitalOnlyVal,2) + ' บาท';
  } else if(hasDiv){
    divCashRow.style.display = 'flex';
    document.getElementById('divCash').textContent = '+' + fmtNum(cashDivTotal,2) + ' บาท';
    reinvestRow.style.display = 'none';
    capOnlyRow.style.display = 'flex';
    document.getElementById('capitalOnlyVal').textContent = fmtNum(capitalOnlyVal,2) + ' บาท';
  } else {
    divCashRow.style.display = 'none';
    reinvestRow.style.display = 'none';
    capOnlyRow.style.display = 'none';
  }

  resultPanel.classList.add('show');
  resultPanel.scrollIntoView({behavior:'smooth', block:'nearest'});
});

// default example
tickerInput.value = 'PTT';
populateYears();
