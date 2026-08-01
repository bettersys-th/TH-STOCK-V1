(function(){
const DOWNLIST = __DOWNLIST_JSON__;
const UPDATED_AT = __UPDATED_AT_JSON__;

document.getElementById('scanUpdated').textContent = 'ข้อมูลล่าสุดอัปเดตเมื่อ: ' + UPDATED_AT;

function fmtNum(n, dec=2){
  return n.toLocaleString('en-US', {minimumFractionDigits:dec, maximumFractionDigits:dec});
}

const filterInput = document.getElementById('scanFilter');
const thresholdSel = document.getElementById('scanThreshold');
const tbody = document.getElementById('scanTable');
const countEl = document.getElementById('scanCount');

function render(){
  const q = filterInput.value.trim().toUpperCase();
  const thresh = parseFloat(thresholdSel.value);
  const rows = DOWNLIST.filter(d => d.pct <= thresh && (!q || d.t.includes(q)));
  countEl.textContent = `พบ ${rows.length} หุ้น`;
  tbody.innerHTML = rows.map(d => `
    <tr class="scan-row" data-ticker="${d.t}">
      <td>${d.t}</td>
      <td>${d.pd}</td>
      <td>${fmtNum(d.pp,2)}</td>
      <td>${fmtNum(d.cp,2)}</td>
      <td class="dir-down">${fmtNum(d.pct,2)}%</td>
      <td>${d.days}</td>
    </tr>
  `).join('');
  tbody.querySelectorAll('.scan-row').forEach(row => {
    row.addEventListener('click', () => {
      const t = row.getAttribute('data-ticker');
      document.getElementById('navCycle').click();
      const cycInput = document.getElementById('cycTicker');
      cycInput.value = t;
      cycInput.dispatchEvent(new Event('change'));
      document.getElementById('analyzeBtn').click();
    });
  });
}

filterInput.addEventListener('input', render);
thresholdSel.addEventListener('change', render);
render();
})();
