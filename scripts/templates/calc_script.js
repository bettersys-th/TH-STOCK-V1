
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
// split that happened earlier that same year). SPLITS[ticker] = [{date, ratio}].
function splitMultiplier(ticker, buyYear, sellYear){
  const events = SPLITS[ticker];
  if(!events) return 1;
  let mult = 1;
  for(const ev of events){
    const y = Number(ev.date.slice(0,4));
    if(y > Number(buyYear) && y <= Number(sellYear)){
      mult *= ev.ratio;
    }
  }
  return mult;
}

// Same idea but date-precise (YYYY-MM-DD strings) — used for dividend share
// counts, where getting the split boundary right down to the day matters
// (a dividend paid a month before a same-year split must NOT get the
// post-split share count).
function splitMultiplierByDate(ticker, fromDate, toDate){
  const events = SPLITS[ticker];
  if(!events) return 1;
  let mult = 1;
  for(const ev of events){
    if(ev.date > fromDate && ev.date <= toDate){
      mult *= ev.ratio;
    }
  }
  return mult;
}

// Sums dividends received between buyYear and sellYear (inclusive), scaling
// the share count held at each dividend's date by any splits that already
// happened between the purchase and that date. (No reinvestment — dividends
// are just summed as cash.)
function totalDividends(ticker, buyYear, sellYear, initialShares){
  return walkDividends(ticker, buyYear, sellYear, initialShares, false).cashPile;
}

// Walks splits + dividends in chronological order (exact ex-dividend dates).
// reinvest=true: each dividend buys more shares at that year's closing price
// (approximation — real purchases would happen on the ex-dividend date, not
// year-end, since we only have annual price granularity). reinvest=false:
// dividends just accumulate as cash. Always returns the per-event `rows` so
// the UI can render a verifiable line-by-line table either way.
function walkDividends(ticker, buyYear, sellYear, initialShares, reinvest){
  buyYear = Number(buyYear); sellYear = Number(sellYear);
  const buyBound = buyYear + '-12-31';   // exclude split ที่เกิดในปีที่ซื้อเอง (ราคาปีนั้นสะท้อนแล้ว)
  const sellBound = sellYear + '-12-31';
  let events = [];
  (SPLITS[ticker]||[]).forEach(ev => {
    if(ev.date > buyBound && ev.date <= sellBound) events.push({date: ev.date, order:0, type:'split', ratio:ev.ratio});
  });
  (DIVIDENDS[ticker]||[]).forEach(ev => {
    const y = Number(ev.date.slice(0,4));
    if(y >= buyYear && y <= sellYear) events.push({date: ev.date, order:1, type:'div', amount:ev.amount});
  });
  events.sort((a,b) => a.date.localeCompare(b.date) || a.order - b.order);

  let shares = initialShares;
  let cashPile = 0;
  const rows = [];
  for(const ev of events){
    if(ev.type === 'split'){
      shares *= ev.ratio;
      continue;
    }
    const y = Number(ev.date.slice(0,4));
    const sharesAtTime = shares;
    const cashReceived = ev.amount * sharesAtTime;
    let sharesBought = 0, refPrice = null, note = '';
    if(reinvest){
      refPrice = tickers[ticker][y];
      if(refPrice && refPrice > 0){
        sharesBought = cashReceived / refPrice;
        shares += sharesBought;
      } else {
        cashPile += cashReceived;
        note = 'ไม่มีราคาปีนี้ — เก็บเป็นเงินสดแทน';
      }
    } else {
      cashPile += cashReceived;
    }
    rows.push({ date: ev.date, amount: ev.amount, sharesAtTime, cash: cashReceived, sharesBought, refPrice, note });
  }
  return { rows, finalShares: shares, cashPile };
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
    if(hasDivData) parts.push('ปันผล ✓ (' + DIVIDENDS[t].length + ' ครั้ง)');
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
  let combinedVal, extraSharesFromReinvest = 0, cashDivTotal = 0, divRows = [];
  const hasDiv = !!DIVIDENDS[t];
  if(hasDiv){
    const walk = walkDividends(t, buyYear, sellYear, initialShares, reinvest);
    divRows = walk.rows;
    if(reinvest){
      extraSharesFromReinvest = walk.finalShares - finalShares;
      combinedVal = walk.finalShares * sellPrice + walk.cashPile;
    } else {
      cashDivTotal = walk.cashPile;
      combinedVal = capitalOnlyVal + cashDivTotal;
    }
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

  // --- ตารางปันผลรายครั้ง (ไว้ตรวจสอบกับข้อมูลจริง) ---
  const divTableSection = document.getElementById('divTableSection');
  const divTableBody = document.getElementById('divTableBody');
  const divTableReinvestCols = document.querySelectorAll('.div-table-reinvest-col');
  if(hasDiv && divRows.length){
    divTableSection.style.display = 'block';
    divTableReinvestCols.forEach(el => el.style.display = reinvest ? '' : 'none');
    let running = 0;
    divTableBody.innerHTML = divRows.map(r => {
      running += r.cash;
      const reinvestCells = reinvest ? `
        <td class="div-table-reinvest-col">${r.refPrice ? fmtNum(r.refPrice,2) : '—'}</td>
        <td class="div-table-reinvest-col">${r.sharesBought ? '+'+fmtNum(r.sharesBought,2) : (r.note || '—')}</td>
      ` : '';
      return `
        <tr>
          <td>${r.date}</td>
          <td>${fmtNum(r.amount,4)} บ./หุ้น</td>
          <td>${fmtNum(r.sharesAtTime,2)} หุ้น</td>
          <td class="pos">+${fmtNum(r.cash,2)} บ.</td>
          ${reinvestCells}
          <td>${fmtNum(running,2)} บ.</td>
        </tr>
      `;
    }).join('');
  } else {
    divTableSection.style.display = 'none';
  }

  resultPanel.classList.add('show');
  resultPanel.scrollIntoView({behavior:'smooth', block:'nearest'});
});

// default example
tickerInput.value = 'PTT';
populateYears();
