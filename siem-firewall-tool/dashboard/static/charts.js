/* Global helpers */
const $$ = (sel, root = document) => root.querySelector(sel);
const api = (path, opts = {}) => fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });

function setLastRefresh() {
  const el = document.getElementById('last-refresh');
  if (el) el.textContent = 'Last refresh: ' + new Date().toLocaleString();
}
function setConn(on) {
  const el = document.getElementById('conn-indicator');
  if (!el) return;
  el.innerHTML = `<i class="bi bi-circle-fill me-1"></i>${on ? 'Live' : 'Offline'}`;
  el.className = 'badge ' + (on ? 'bg-success-subtle text-success-emphasis' : 'bg-danger-subtle text-danger-emphasis');
}

/* ---------------- Dashboard ---------------- */
let trafficChart, topTalkersChart;

async function initDashboard() {
  await Promise.all([refreshStats(), refreshTraffic(), refreshTopTalkers()]);
  setInterval(refreshStats, 4000);
  setInterval(refreshTraffic, 6000);
  setInterval(refreshTopTalkers, 8000);
}

async function refreshStats() {
  try {
    const res = await api('/api/stats'); const data = await res.json();
    $$('#kpi-total').textContent = data.total ?? 0;
    $$('#kpi-allow').textContent = data.allowed ?? 0;
    $$('#kpi-block').textContent = data.blocked ?? 0;
    $$('#kpi-alerts').textContent = data.open_alerts ?? 0;
    setConn(true); setLastRefresh();
  } catch (e) { setConn(false); }
}

async function refreshTraffic() {
  try {
    const res = await api('/api/traffic'); const data = await res.json();
    const labels = data.map(d => d.minute);
    const counts = data.map(d => d.count);
    if (!trafficChart) {
      trafficChart = new Chart($$('#trafficChart'), {
        type: 'line',
        data: { labels, datasets: [{ label: 'Events/min', data: counts, tension: .35, borderWidth: 2, fill: true }] },
        options: baseChartOptions('Traffic')
      });
    } else {
      trafficChart.data.labels = labels;
      trafficChart.data.datasets[0].data = counts;
      trafficChart.update();
    }
    setConn(true); setLastRefresh();
  } catch (e) { setConn(false); }
}

async function refreshTopTalkers() {
  try {
    const res = await api('/api/top-talkers'); const data = await res.json();
    const labels = data.map(d => `${d.src} → ${d.dst}`);
    const counts = data.map(d => d.count);
    if (!topTalkersChart) {
      topTalkersChart = new Chart($$('#topTalkersChart'), {
        type: 'bar',
        data: { labels, datasets: [{ label: 'Flows', data: counts, borderWidth: 1 }] },
        options: baseChartOptions('Top Talkers', true)
      });
    } else {
      topTalkersChart.data.labels = labels;
      topTalkersChart.data.datasets[0].data = counts;
      topTalkersChart.update();
    }
    setConn(true); setLastRefresh();
  } catch (e) { setConn(false); }
}

function baseChartOptions(title, horizontal = false) {
  const gridColor = 'rgba(255,255,255,.08)';
  return {
    indexAxis: horizontal ? 'y' : 'x',
    plugins: {
      legend: { labels: { color: getTextColor() } },
      title: { display: false, text: title, color: getTextColor() }
    },
    scales: {
      x: { grid: { color: gridColor }, ticks: { color: getTextColor() } },
      y: { grid: { color: gridColor }, ticks: { color: getTextColor() } }
    }
  };
}
function getTextColor() {
  const theme = document.documentElement.getAttribute('data-theme') || 'dark';
  return theme === 'dark' ? '#e6e6e6' : '#1c1c1c';
}

/* ---------------- Logs ---------------- */
let logsPage = 1, logsPageSize = 50;

function resetLogFilters() {
  ['filter-q','filter-action','filter-proto','filter-port'].forEach(id => $$('#'+id).value = '');
  logsPage = 1; reloadLogs();
}
function logsPrev(){ if (logsPage>1){ logsPage--; reloadLogs(); } }
function logsNext(){ logsPage++; reloadLogs(); }

async function initLogs(){ reloadLogs(); setInterval(reloadLogs, 6000); }

async function reloadLogs() {
  try {
    const params = new URLSearchParams();
    const q = $$('#filter-q').value.trim(); if (q) params.set('q', q);
    const action = $$('#filter-action').value; if (action) params.set('action', action);
    const proto = $$('#filter-proto').value; if (proto) params.set('proto', proto);
    const port = $$('#filter-port').value; if (port) params.set('port', port);
    params.set('page', logsPage); params.set('page_size', logsPageSize);

    const res = await api('/api/logs?'+params.toString());
    const data = await res.json();
    const tbody = $$('#logs-body');
    tbody.innerHTML = '';
    if (!data.rows || !data.rows.length) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted-2">No results</td></tr>`;
    } else {
      data.rows.forEach(r => {
        const cls = (r.action === 'ALLOW') ? 'text-allow' : (r.action === 'BLOCK' || r.action === 'DENY') ? 'text-block' : '';
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${r.id}</td>
          <td>${r.timestamp ?? ''}</td>
          <td>${r.src_ip ?? ''}</td>
          <td>${r.dst_ip ?? ''}</td>
          <td>${r.proto ?? ''}</td>
          <td>${r.port ?? ''}</td>
          <td class="${cls} fw-bold">${r.action ?? ''}</td>
        `;
        tbody.appendChild(tr);
      });
    }
    $$('#logs-total').textContent = `${data.total ?? 0} results`;
    setConn(true); setLastRefresh();
  } catch (e) { setConn(false); }
}

/* ---------------- Alerts ---------------- */
async function loadAlerts() {
  try {
    const status = $$('#alert-status-filter').value;
    const url = status ? `/api/alerts?status=${encodeURIComponent(status)}` : '/api/alerts';
    const res = await api(url); const data = await res.json();
    const tbody = $$('#alerts-body'); tbody.innerHTML = '';
    if (!data.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-muted-2">No alerts</td></tr>`;
    } else {
      data.forEach(a => {
        const sevBadge = severityBadge(a.severity);
        const statusBadge = statusBadgeEl(a.status);
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${a.id}</td>
          <td>${a.timestamp ?? ''}</td>
          <td>${sevBadge}</td>
          <td>${escapeHtml(a.message ?? '')}</td>
          <td>${statusBadge}</td>
          <td class="text-end">
            <div class="btn-group btn-group-sm">
              <button class="btn btn-outline-cyan" onclick="alertAck(${a.id})">Ack</button>
              <button class="btn btn-outline-cyan" onclick="alertClose(${a.id})">Close</button>
            </div>
          </td>
        `;
        $$('#alerts-body').appendChild(tr);
      });
    }
    setConn(true); setLastRefresh();
  } catch (e) { setConn(false); }
}
function severityBadge(sev){
  const map = { CRITICAL:'bg-danger', HIGH:'bg-danger', MEDIUM:'bg-warning text-dark', LOW:'bg-success', INFO:'bg-secondary' };
  const cls = map[sev?.toUpperCase()] || 'bg-secondary';
  return `<span class="badge ${cls}">${sev ?? 'INFO'}</span>`;
}
function statusBadgeEl(st){
  const map = { OPEN:'bg-danger-subtle', ACK:'bg-warning', CLOSED:'bg-success' };
  const cls = map[st?.toUpperCase()] || 'bg-secondary';
  return `<span class="badge ${cls}">${st ?? 'OPEN'}</span>`;
}
async function alertAck(id){ await updateAlert(id, 'ACK'); }
async function alertClose(id){ await updateAlert(id, 'CLOSED'); }
async function updateAlert(id, status) {
  // Prefer PATCH /api/alerts/<id> with JSON {status}, fallback to legacy endpoints.
  try {
    let res = await api(`/api/alerts/${id}`, { method:'PATCH', body: JSON.stringify({ status }) });
    if (!res.ok) res = await api(`/api/alerts/${id}/${status.toLowerCase()}`, { method:'POST' });
    await loadAlerts();
  } catch (e) {}
}

/* ---------------- Graph ---------------- */
let cy;
async function buildGraph() {
  try {
    const res = await api('/api/top-talkers'); const data = await res.json();
    const limit = parseInt(($$('#graph-limit')?.value || '60'), 10);
    const pruned = data.slice(0, limit);

    // Build nodes & edges
    const nodes = new Map();
    const elements = [];
    pruned.forEach((r, idx) => {
      if (!nodes.has(r.src)) nodes.set(r.src, { data: { id: 's_'+r.src, label: r.src, type: 'src' } });
      if (!nodes.has(r.dst)) nodes.set(r.dst, { data: { id: 'd_'+r.dst, label: r.dst, type: 'dst' } });
      elements.push({
        data: { id: 'e_'+idx, source: 's_'+r.src, target: 'd_'+r.dst, weight: r.count }
      });
    });

    const container = $$('#cy');
    if (!cy) {
      cy = cytoscape({
        container,
        style: [
          { selector: 'node[type="src"]', style: { 'background-color': '#00bcd4', 'label': 'data(label)', 'color': '#fff', 'font-size': 10 } },
          { selector: 'node[type="dst"]', style: { 'background-color': '#3f51b5', 'label': 'data(label)', 'color': '#fff', 'font-size': 10 } },
          { selector: 'edge', style: { 'width': 'mapData(weight, 1, 100, 1, 10)', 'line-color': '#8bc34a', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#8bc34a', 'curve-style': 'bezier' } }
        ],
        layout: { name: 'cose', animate: true }
      });
    }
    cy.json({ elements: [ ...nodes.values(), ...elements ] });
    cy.layout({ name: 'cose', animate: true }).run();
    setConn(true); setLastRefresh();
  } catch (e) { setConn(false); }
}
function graphFit(){ if (cy) cy.fit(); }

/* ---------------- Compliance ---------------- */
function refreshCompliance(){
  // Placeholder client refresh (real logic should call an API).
  setLastRefresh();
}

/* ---------------- Utils ---------------- */
function escapeHtml(s){ return (s||'').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }
