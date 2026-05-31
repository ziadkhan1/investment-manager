'use strict';

// ── Configuration ─────────────────────────────────────────────────────────────
// Replace CLIENT_ID with your Google OAuth 2.0 Web client ID.
// Create one at: https://console.cloud.google.com → APIs & Services → Credentials
// Authorized JavaScript origins must include: https://ziadkhan1.github.io
const CFG = {
  CLIENT_ID:      '1087293102882-70tfiu2m7a21klc764rnu679fh79k5i3.apps.googleusercontent.com',
  SPREADSHEET_ID: '1jWXEWCwbgHggMLEU01Cgcg0fd0Ey4kL7PulBlgCQ3LE',
  SCOPES:         'https://www.googleapis.com/auth/spreadsheets.readonly',
  DATA_ROW:       67,   // 1-indexed sheet row where dashboard data tables start
};

// ── State ─────────────────────────────────────────────────────────────────────
let tokenClient = null;
let accessToken = null;
const charts    = {};

// ── Utility ───────────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

function fmtPKR(v) {
  const n = Math.abs(parseFloat(v) || 0);
  if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(0) + 'K';
  return n.toFixed(0);
}

function fmtPKRFull(v) {
  const n = parseFloat(v) || 0;
  return 'PKR ' + n.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function fmtMonth(s) {
  if (!s || !s.includes('-')) return s;
  const [y, m] = s.split('-');
  return new Date(+y, +m - 1).toLocaleDateString('en', { month: 'short', year: '2-digit' });
}

function setLoading(on) {
  $('loading').classList.toggle('hidden', !on);
}

function showToast(msg, durationMs = 3500) {
  const el = $('error-toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), durationMs);
}

// ── Google Auth ───────────────────────────────────────────────────────────────
function initAuth() {
  tokenClient = google.accounts.oauth2.initTokenClient({
    client_id: CFG.CLIENT_ID,
    scope:     CFG.SCOPES,
    callback:  (response) => {
      if (response.error) {
        showToast('Sign-in failed: ' + response.error);
        return;
      }
      accessToken = response.access_token;
      $('signin-screen').classList.remove('active');
      $('dashboard-screen').classList.add('active');
      fetchAndRender();
    },
  });

  $('signin-btn').addEventListener('click', () => {
    tokenClient.requestAccessToken({ prompt: 'consent' });
  });

  $('refresh-btn').addEventListener('click', () => {
    if (accessToken) fetchAndRender();
    else tokenClient.requestAccessToken({ prompt: '' });
  });
}

// ── Sheets API ────────────────────────────────────────────────────────────────
async function batchGet(ranges) {
  const params = new URLSearchParams();
  ranges.forEach((r) => params.append('ranges', r));
  const url =
    `https://sheets.googleapis.com/v4/spreadsheets/${CFG.SPREADSHEET_ID}` +
    `/values:batchGet?${params}`;

  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (res.status === 401) {
    // Token expired — silently refresh
    accessToken = null;
    tokenClient.requestAccessToken({ prompt: '' });
    throw new Error('TOKEN_EXPIRED');
  }
  if (!res.ok) throw new Error(`Sheets API ${res.status}`);
  return res.json();
}

function parseBlock(valueRange) {
  const rows = valueRange?.values || [];
  if (rows.length < 2) return { headers: [], rows: [] };
  return {
    headers: rows[0],
    rows: rows.slice(1).filter((r) => r[0] !== undefined && r[0] !== ''),
  };
}

// ── Chart helpers ─────────────────────────────────────────────────────────────
const COLORS = {
  blue:   'rgba(59,130,246,',
  green:  'rgba(16,185,129,',
  red:    'rgba(239,68,68,',
  yellow: 'rgba(245,158,11,',
  purple: 'rgba(139,92,246,',
  orange: 'rgba(249,115,22,',
};

const c = (name, alpha) => COLORS[name] + alpha + ')';

function killChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

function mkChart(id, config) {
  killChart(id);
  charts[id] = new Chart($(id).getContext('2d'), config);
}

const GRID_X = { color: 'rgba(255,255,255,.03)' };
const GRID_Y = { color: 'rgba(255,255,255,.06)' };
const TICK   = { color: '#475569', font: { size: 10 } };

function xAxis(extra = {}) {
  return { ticks: { ...TICK, maxRotation: 45, maxTicksLimit: 8 }, grid: GRID_X, ...extra };
}
function yAxis(extra = {}) {
  return {
    ticks: { ...TICK, callback: (v) => fmtPKR(v) },
    grid: GRID_Y,
    ...extra,
  };
}
function legend(position = 'bottom') {
  return { position, labels: { color: '#94A3B8', font: { size: 10 }, boxWidth: 10, padding: 12 } };
}

// ── Chart 1: Real vs Nominal Net Worth ────────────────────────────────────────
function renderNW(vr) {
  const { rows } = parseBlock(vr);
  if (!rows.length) return;

  const labels  = rows.map((r) => fmtMonth(r[0]));
  const nominal = rows.map((r) => parseFloat(r[1]) || 0);
  const real    = rows.map((r) => parseFloat(r[2]) || 0);

  // Update header
  const latest = nominal[nominal.length - 1];
  $('nw-pkr').textContent = fmtPKRFull(latest);

  const latestMonth = rows[rows.length - 1]?.[0] || '';
  $('last-updated').textContent = 'As of\n' + latestMonth;

  mkChart('chart-nw', {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Nominal NW',
          data: nominal,
          borderColor: c('blue', '.9'),
          backgroundColor: c('blue', '.08'),
          fill: true, tension: .35, pointRadius: 2, pointHoverRadius: 5,
        },
        {
          label: 'Real NW (Inflation-Adj)',
          data: real,
          borderColor: c('green', '.9'),
          backgroundColor: 'transparent',
          borderDash: [5, 4], tension: .35, pointRadius: 2, pointHoverRadius: 5,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: legend() },
      scales: { x: xAxis(), y: yAxis() },
    },
  });
}

// ── Chart 2: Monthly Income vs Expenses ───────────────────────────────────────
function renderCashFlow(vr) {
  const { rows } = parseBlock(vr);
  if (!rows.length) return;

  const labels   = rows.map((r) => fmtMonth(r[0]));
  const income   = rows.map((r) => parseFloat(r[1]) || 0);
  const expenses = rows.map((r) => parseFloat(r[2]) || 0);
  const savings  = rows.map((r) => parseFloat(r[3]) || 0);

  mkChart('chart-cashflow', {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Income',   data: income,   borderColor: c('green', '.9'),  backgroundColor: 'transparent', tension: .35, pointRadius: 2 },
        { label: 'Expenses', data: expenses, borderColor: c('red', '.9'),    backgroundColor: 'transparent', tension: .35, pointRadius: 2 },
        { label: 'Net Savings', data: savings, borderColor: c('blue', '.9'), backgroundColor: c('blue', '.07'), fill: true, tension: .35, pointRadius: 2 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: legend() },
      scales: { x: xAxis(), y: yAxis() },
    },
  });
}

// ── Chart 3: Asset Allocation (stacked bars) ──────────────────────────────────
function renderAllocation(vr) {
  const { rows } = parseBlock(vr);
  if (!rows.length) return;

  const labels = rows.map((r) => fmtMonth(r[0]));
  const cats   = ['Cash/PKR', 'Investments', 'Fgn Currency', 'Gold', 'Receivables'];
  const colors = ['blue', 'purple', 'green', 'yellow', 'orange'];

  const datasets = cats.map((cat, i) => ({
    label: cat,
    data: rows.map((r) => parseFloat(r[i + 1]) || 0),
    backgroundColor: c(colors[i], '.82'),
    borderColor: 'transparent',
    borderRadius: i === cats.length - 1 ? { topLeft: 3, topRight: 3 } : 0,
    stack: 'alloc',
  }));

  mkChart('chart-allocation', {
    type: 'bar',
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: legend() },
      scales: {
        x: { ...xAxis(), stacked: true },
        y: { ...yAxis(), stacked: true },
      },
    },
  });
}

// ── Chart 4: Currency Exposure (stacked bars: Hard vs PKR) ───────────────────
function renderExposure(vr) {
  const { rows } = parseBlock(vr);
  if (!rows.length) return;

  const labels = rows.map((r) => fmtMonth(r[0]));
  const hard   = rows.map((r) => parseFloat(r[1]) || 0);
  const pkrA   = rows.map((r) => parseFloat(r[2]) || 0);

  mkChart('chart-exposure', {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Hard Currency (GBP/USD/Gold)', data: hard, backgroundColor: c('purple', '.82'), stack: 'exp' },
        { label: 'PKR Assets',                   data: pkrA, backgroundColor: c('blue', '.6'),    stack: 'exp' },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: legend() },
      scales: {
        x: { ...xAxis(), stacked: true },
        y: { ...yAxis(), stacked: true },
      },
    },
  });
}

// ── Chart 5: Growth Attribution (NW line vs Savings baseline) ────────────────
function renderGrowth(vr) {
  const { rows } = parseBlock(vr);
  if (!rows.length) return;

  const labels  = rows.map((r) => fmtMonth(r[0]));
  const nw      = rows.map((r) => parseFloat(r[1]) || 0);
  const savings = rows.map((r) => parseFloat(r[2]) || 0);

  // Show investment returns contribution in header badge
  const latestNW  = nw[nw.length - 1] || 0;
  const latestSav = savings[savings.length - 1] || 0;
  const retPct    = latestSav > 0 ? (((latestNW - latestSav) / latestSav) * 100).toFixed(0) : 0;
  $('nw-usd').textContent = `Returns: +${retPct}% on invested`;

  mkChart('chart-growth', {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Net Worth (PKR)',
          data: nw,
          borderColor: c('blue', '.9'),
          backgroundColor: c('blue', '.10'),
          fill: true, tension: .35, pointRadius: 2,
        },
        {
          label: 'Savings Invested (Real)',
          data: savings,
          borderColor: c('yellow', '.8'),
          backgroundColor: 'transparent',
          borderDash: [5, 4], tension: .35, pointRadius: 2,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: legend(),
        tooltip: {
          callbacks: {
            afterBody: (items) => {
              const nwVal  = items.find((i) => i.datasetIndex === 0)?.raw || 0;
              const savVal = items.find((i) => i.datasetIndex === 1)?.raw || 0;
              const ret    = nwVal - savVal;
              return ret >= 0
                ? `Return component: +${fmtPKR(ret)}`
                : `Below savings: ${fmtPKR(ret)}`;
            },
          },
        },
      },
      scales: { x: xAxis(), y: yAxis() },
    },
  });
}

// ── Chart 6: Return vs Contribution (horizontal stacked bar) ──────────────────
function renderContribution(vr) {
  const { rows } = parseBlock(vr);
  if (!rows.length) return;

  const labels  = rows.map((r) => r[0]);
  const contrib = rows.map((r) => parseFloat(r[1]) || 0);
  const returns = rows.map((r) => parseFloat(r[2]) || 0);

  mkChart('chart-contribution', {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Contribution (Real Cost Basis)', data: contrib, backgroundColor: c('blue', '.75'),  stack: 'rc' },
        { label: 'Investment Return',              data: returns, backgroundColor: c('green', '.75'), stack: 'rc' },
      ],
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: legend('top') },
      scales: {
        x: {
          stacked: true,
          ticks: { ...TICK, callback: (v) => fmtPKR(v) },
          grid: GRID_Y,
        },
        y: {
          stacked: true,
          ticks: { color: '#94A3B8', font: { size: 10 } },
          grid: GRID_X,
        },
      },
    },
  });
}

// ── Main fetch & render ───────────────────────────────────────────────────────
async function fetchAndRender() {
  setLoading(true);
  try {
    const R = CFG.DATA_ROW;

    // Fetch all 5 time-series blocks in one call
    const batch1 = await batchGet([
      `Dashboard!A${R}:C`,   // Block A: NW timeline
      `Dashboard!E${R}:I`,   // Block B: Cash flow
      `Dashboard!K${R}:P`,   // Block C: Asset allocation
      `Dashboard!R${R}:T`,   // Block D: Currency exposure
      `Dashboard!V${R}:X`,   // Block E: Growth attribution
    ]);

    const [vrA, vrB, vrC, vrD, vrE] = batch1.valueRanges;

    // Block F row = DATA_ROW + n_months + 3 (mirrors Python BLOCK2_ROW calculation)
    const nMonths  = Math.max((vrA.values?.length || 1) - 1, 1);
    const blockFRow = R + nMonths + 3;

    const batch2 = await batchGet([`Dashboard!A${blockFRow}:C`]);
    const vrF    = batch2.valueRanges[0];

    renderNW(vrA);
    renderCashFlow(vrB);
    renderAllocation(vrC);
    renderExposure(vrD);
    renderGrowth(vrE);
    renderContribution(vrF);

  } catch (err) {
    if (err.message !== 'TOKEN_EXPIRED') {
      console.error(err);
      showToast('Error loading data — check console');
    }
  } finally {
    setLoading(false);
  }
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
window.addEventListener('load', () => {
  // GIS loads async — poll until ready
  const wait = setInterval(() => {
    if (window.google?.accounts?.oauth2) {
      clearInterval(wait);
      initAuth();
    }
  }, 100);
});
