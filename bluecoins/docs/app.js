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
let guestMode   = false;   // true = no auth, render synthetic anonymised data
let demoCache   = null;    // cached synthetic dataset for the current guest session
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

// Full integer with thousand separators — no K/M abbreviation
const fmtN = (v) => Math.round(parseFloat(v) || 0).toLocaleString('en-US');

function fmtMonth(s) {
  if (!s || !s.includes('-')) return s;
  const [y, m] = s.split('-');
  return new Date(+y, +m - 1).toLocaleDateString('en', { month: 'short', year: '2-digit' });
}

// Add k calendar months to a "YYYY-MM" string → "YYYY-MM"
function addMonths(ym, k) {
  const [y, m] = ym.split('-').map(Number);
  const d = new Date(y, m - 1 + k, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
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
    if (guestMode) { demoCache = null; fetchAndRender(); return; }  // reshuffle sample data
    if (accessToken) fetchAndRender();
    else tokenClient.requestAccessToken({ prompt: '' });
  });
}

// ── Guest mode entry (no Google auth) ───────────────────────────────────────────
function enterGuestMode() {
  guestMode   = true;
  accessToken = null;
  demoCache   = null;
  $('signin-screen').classList.remove('active');
  $('dashboard-screen').classList.add('active');
  $('guest-badge').classList.remove('hidden');
  fetchAndRender();
}

// ── Sheets API ────────────────────────────────────────────────────────────────
async function batchGet(ranges) {
  // Guests never hold an access token, so no real Sheet is ever contacted —
  // serve a structurally identical synthetic dataset instead.
  if (guestMode) return demoBatchGet(ranges);

  const params = new URLSearchParams();
  ranges.forEach((r) => params.append('ranges', r));
  const url =
    `https://sheets.googleapis.com/v4/spreadsheets/${CFG.SPREADSHEET_ID}` +
    `/values:batchGet?${params}`;

  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: 'no-store',   // never serve a stale Sheets response (would show last month's NW)
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

// Current month cap: "YYYY-MM" — never show data beyond the month we're in
const NOW_MONTH = (() => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
})();

const IS_MONTH = (v) => /^\d{4}-\d{2}$/.test(v);

function parseBlock(valueRange, monthOnly = false) {
  const rows = valueRange?.values || [];
  if (rows.length < 2) return { headers: [], rows: [] };
  return {
    headers: rows[0],
    rows: rows.slice(1).filter((r) => {
      if (r[0] === undefined || r[0] === '') return false;
      if (monthOnly) return IS_MONTH(r[0]) && r[0] <= NOW_MONTH;
      return true;
    }),
  };
}

// ── Guest mode: synthetic anonymised data ──────────────────────────────────────
// Builds a full, internally consistent fake portfolio with the SAME shape as the
// real Sheet blocks, so every chart renders normally — but with fictional numbers.
// Net worth ≈ allocation total ≈ exposure total ≈ growth NW across blocks.
function buildDemoData() {
  const rint = (lo, hi) => Math.round(lo + Math.random() * (hi - lo));

  const N      = 18;                                            // months of history
  const months = Array.from({ length: N }, (_, i) => addMonths(NOW_MONTH, i - (N - 1)));

  let nw         = rint(1600000, 2000000);   // starting nominal net worth (fake PKR)
  let realFloor  = nw - rint(20000, 60000);  // inflation-adjusted floor
  let cumSavings = nw - rint(150000, 300000);// cumulative savings invested baseline

  const A = [], B = [], C = [], D = [], E = [];
  months.forEach((m) => {
    const income      = rint(300000, 430000);
    const expenses    = rint(170000, 270000);
    const savings     = income - expenses;
    const ret         = rint(-35000, 95000);                   // monthly market move
    nw         += savings + ret;
    cumSavings += savings;
    realFloor  += Math.round(savings * 0.82) + rint(-8000, 4000);
    const savingsRate = Math.round((savings / income) * 100);

    A.push([m, nw, realFloor]);
    B.push([m, income, expenses, savings, savingsRate]);

    // Asset allocation — split NW into 5 categories that sum back to NW
    const inv  = Math.round(nw * (0.40 + Math.random() * 0.06));
    const fx   = Math.round(nw * (0.14 + Math.random() * 0.04));
    const gold = Math.round(nw * (0.07 + Math.random() * 0.03));
    const recv = Math.round(nw * 0.04);
    const cash = nw - inv - fx - gold - recv;
    C.push([m, cash, inv, fx, gold, recv]);

    const hard = fx + gold;                                    // hard-currency exposure
    D.push([m, hard, nw - hard]);

    E.push([m, nw, cumSavings]);
  });

  // Portfolio Health — fake accounts: [name, invested, return(signed), floor, _, _, kind]
  const F = [
    ['Account',      'Invested', 'Return', 'Floor', '', '', 'Kind'],
    ['Equity Fund',     900000,   182000,  965000, '', '', 'invest'],
    ['Index Fund',      540000,   124000,  560000, '', '', 'invest'],
    ['Gold Holding',    300000,    96000,  331000, '', '', 'invest'],
    ['Bond Fund',       650000,    71000,  694000, '', '', 'invest'],
    ['FX Savings',      420000,   -26000,  468000, '', '', 'invest'],
    ['Main Bank',       360000,        0,  409000, '', '', 'bank'],
    ['Savings Bank',    220000,        0,  251000, '', '', 'bank'],
    ['Wallet',           62000,        0,   71000, '', '', 'bank'],
  ];

  return { A, B, C, D, E, F };
}

// Returns the same { valueRanges: [...] } shape as the live Sheets batchGet,
// matching each requested A1 range to the right synthetic block by its columns.
function demoBatchGet(ranges) {
  if (!demoCache) demoCache = buildDemoData();
  const d = demoCache;

  const HDR = {
    A: ['Month', 'Nominal', 'Real'],
    B: ['Month', 'Income', 'Expenses', 'Savings', 'Rate'],
    C: ['Month', 'Cash/PKR', 'Investments', 'Foreign', 'Gold', 'Receivables'],
    D: ['Month', 'Hard', 'PKR'],
    E: ['Month', 'Net Worth', 'Savings Invested'],
  };

  const valueRanges = ranges.map((r) => {
    const m     = r.match(/![A-Z$]*?([A-Z]+)\d+(?::\$?([A-Z]+)\d*)?/);
    const start = m?.[1] || '';
    const end   = m?.[2] || start;
    if (start === 'A' && end === 'C') return { values: [HDR.A, ...d.A] };
    if (start === 'E')                return { values: [HDR.B, ...d.B] };
    if (start === 'K')                return { values: [HDR.C, ...d.C] };
    if (start === 'R')                return { values: [HDR.D, ...d.D] };
    if (start === 'V')                return { values: [HDR.E, ...d.E] };
    if (start === 'Y')                return { values: [['CAGR', ''], ['Nominal', 18.4], ['Real', 6.1]] };
    if (start === 'A' && end === 'G') return { values: d.F };
    return { values: [] };
  });

  return Promise.resolve({ valueRanges });
}

// ── Chart helpers ─────────────────────────────────────────────────────────────
const COLORS = {
  blue:   'rgba(59,130,246,',
  green:  'rgba(16,185,129,',
  red:    'rgba(239,68,68,',
  yellow: 'rgba(245,158,11,',
  purple: 'rgba(139,92,246,',
  orange: 'rgba(249,115,22,',
  teal:   'rgba(45,212,191,',
  slate:  'rgba(100,116,139,',
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

// Disable datalabels globally; enable per-dataset where needed
if (Chart.defaults.plugins?.datalabels) Chart.defaults.plugins.datalabels.display = false;

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
function legend(position = 'bottom', useLines = false) {
  const labels = { color: '#94A3B8', font: { size: 10 }, boxWidth: 10, padding: 12 };
  if (useLines) {
    labels.usePointStyle = true;
    labels.pointStyleWidth = 18;
    // Mirror each dataset's dash pattern onto its legend marker so dashed lines
    // (Forecast, Inflation Floor, Savings Invested) read as dashed in the legend.
    labels.generateLabels = (chart) => {
      const items = Chart.defaults.plugins.legend.labels.generateLabels(chart);
      items.forEach((it) => {
        const ds = chart.data.datasets[it.datasetIndex];
        if (ds && ds.borderDash && ds.borderDash.length) it.lineDash = ds.borderDash;
      });
      return items;
    };
  }
  return { position, labels };
}

// ── Chart 1: Real vs Nominal Net Worth ────────────────────────────────────────
function renderNW(vr) {
  const { rows } = parseBlock(vr, true);
  if (!rows.length) return;

  const months  = rows.map((r) => r[0]);
  const nominal = rows.map((r) => parseFloat(r[1]) || 0);
  const real    = rows.map((r) => parseFloat(r[2]) || 0);

  const n      = nominal.length;
  const latest = nominal[n - 1];
  $('nw-pkr').textContent = fmtPKRFull(latest);
  $('last-updated').textContent = 'As of\n' + (rows[n - 1]?.[0] || '');

  // ── 3-month linear forecast from the recent trend ────────────────────────
  // Least-squares slope over the last `win` months projects the trajectory.
  const FCAST = 3;
  const win   = Math.min(6, n);
  const seg   = nominal.slice(n - win);
  const mx    = (win - 1) / 2;
  const my    = seg.reduce((a, b) => a + b, 0) / win;
  let num = 0, den = 0;
  seg.forEach((y, i) => { num += (i - mx) * (y - my); den += (i - mx) ** 2; });
  const slope = den ? num / den : 0;

  const lastMonth = months[n - 1];
  const labels = [
    ...months.map(fmtMonth),
    ...Array.from({ length: FCAST }, (_, k) => fmtMonth(addMonths(lastMonth, k + 1))),
  ];

  // Forecast series: null over history, anchored to the last actual point, then
  // projected forward so the dashed line continues seamlessly from the curve.
  const forecast = new Array(n - 1).fill(null);
  forecast.push(latest);
  for (let k = 1; k <= FCAST; k++) forecast.push(Math.round(latest + slope * k));

  // Year-end KPI: project the same monthly slope out to December of this year.
  const monthsToYE  = Math.max(0, 12 - Number(lastMonth.split('-')[1]));
  const yearEndNW   = Math.round(latest + slope * monthsToYE);
  const yeEl = $('metric-yearend');
  if (yeEl) {
    yeEl.textContent = fmtN(yearEndNW);
    yeEl.title = `Forecast for Dec ${lastMonth.split('-')[0]} at the recent ${win}-month trend`;
  }

  // Pad actual series so they align with the extended label axis.
  const pad = new Array(FCAST).fill(null);

  // Value label on the last ACTUAL month (not the padded forecast tail).
  const lastActualLabel = {
    display: (ctx) => ctx.dataIndex === n - 1,
    align: 'top', anchor: 'end',
    color: '#CBD5E1',
    font: { size: 9, weight: '600' },
    formatter: (v) => fmtPKR(v),
    offset: 2,
  };

  mkChart('chart-nw', {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Nominal Net Worth',
          data: [...nominal, ...pad],
          borderColor: c('blue', '.9'),
          backgroundColor: c('blue', '.08'),
          fill: true, tension: .35, pointRadius: 2, pointHoverRadius: 5,
          pointStyle: 'line',
          datalabels: lastActualLabel,
        },
        {
          label: 'Forecast',
          data: forecast,
          borderColor: c('blue', '.55'),
          backgroundColor: 'transparent',
          borderDash: [2, 3], tension: .35, pointRadius: 0, pointHoverRadius: 4,
          pointStyle: 'line',
          datalabels: {
            display: (ctx) => ctx.dataIndex === ctx.dataset.data.length - 1,
            align: 'top', anchor: 'end',
            color: c('blue', '.8'),
            font: { size: 9, weight: '600' },
            formatter: (v) => fmtPKR(v),
            offset: 2,
          },
        },
        {
          label: 'Inflation Floor',
          data: [...real, ...pad],
          borderColor: 'rgba(160,160,170,.85)',
          backgroundColor: 'transparent',
          borderDash: [5, 4], tension: .35, pointRadius: 2, pointHoverRadius: 5,
          pointStyle: 'line',
          datalabels: lastActualLabel,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: legend('bottom', true) },
      scales: { x: xAxis(), y: yAxis() },
    },
  });
}

// ── Chart 2: Monthly Income vs Expenses ───────────────────────────────────────
function renderCashFlow(vr) {
  const { rows } = parseBlock(vr, true);
  if (!rows.length) return;

  const labels   = rows.map((r) => fmtMonth(r[0]));
  const income   = rows.map((r) => parseFloat(r[1]) || 0);
  const expenses = rows.map((r) => parseFloat(r[2]) || 0);
  const savings  = rows.map((r) => parseFloat(r[3]) || 0);

  mkChart('chart-cashflow', {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Income',
          data: income,
          backgroundColor: c('green', '.65'),
          borderColor: c('green', '.9'),
          borderWidth: 1,
          borderRadius: 3,
          categoryPercentage: 0.7,
          barPercentage: 0.9,
          order: 2,
        },
        {
          label: 'Expenses',
          data: expenses,
          backgroundColor: c('red', '.6'),
          borderColor: c('red', '.9'),
          borderWidth: 1,
          borderRadius: 3,
          categoryPercentage: 0.7,
          barPercentage: 0.9,
          order: 2,
        },
        {
          label: 'Net Savings',
          type: 'line',
          data: savings,
          borderColor: c('blue', '.9'),
          backgroundColor: c('blue', '.9'),
          tension: .35,
          pointRadius: 2,
          pointHoverRadius: 5,
          pointStyle: 'circle',
          order: 1,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: { legend: legend('bottom') },
      scales: { x: xAxis(), y: yAxis() },
    },
  });
}

// ── Chart 3: Asset Allocation (stacked area) ──────────────────────────────────
function renderAllocation(vr) {
  const { rows } = parseBlock(vr, true);
  if (!rows.length) return;

  const labels = rows.map((r) => fmtMonth(r[0]));
  const cats   = ['Cash/PKR', 'Investments', 'Foreign Currency', 'Gold', 'Receivables'];
  const colors = ['blue', 'purple', 'teal', 'yellow', 'slate'];

  // Per-month totals (all categories sum to net worth) for % share labels.
  const totals = rows.map((r) =>
    cats.reduce((s, _cat, i) => s + (parseFloat(r[i + 1]) || 0), 0));

  // Subtle % labels at a few evenly spaced months — only on bands with enough
  // share to stay readable (thin slivers like Gold/Receivables are skipped).
  const LABEL_COUNT = 3;
  const last  = labels.length - 1;
  const start = Math.min(2, last);
  const span  = last - start;
  const labelIdx = new Set(
    Array.from({ length: LABEL_COUNT }, (_, k) =>
      start + (span ? Math.round((k * span) / (LABEL_COUNT - 1)) : 0))
  );
  const share = (j, v) => (totals[j] ? (v / totals[j]) * 100 : 0);

  const datasets = cats.map((cat, i) => ({
    label: cat,
    data: rows.map((r) => parseFloat(r[i + 1]) || 0),
    backgroundColor: c(colors[i], '.5'),
    borderColor: c(colors[i], '.85'),
    borderWidth: 1,
    fill: true,
    tension: .3,
    pointRadius: 0,
    pointHoverRadius: 4,
    datalabels: {
      display: (ctx) =>
        labelIdx.has(ctx.dataIndex) &&
        share(ctx.dataIndex, ctx.dataset.data[ctx.dataIndex]) >= 7,
      formatter: (value, ctx) => Math.round(share(ctx.dataIndex, value)) + '%',
      // Sit just inside the top of each band; muted, no background — quieter
      // than the Currency Exposure labels.
      anchor: 'center', align: 'bottom', offset: 1, clamp: true,
      color: 'rgba(255,255,255,.78)',
      font: { size: 9 },
      textShadowColor: 'rgba(0,0,0,.5)',
      textShadowBlur: 3,
    },
  }));

  mkChart('chart-allocation', {
    type: 'line',
    plugins: window.ChartDataLabels ? [window.ChartDataLabels] : [],
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      layout: { padding: { right: 22 } },  // room for last-month % labels
      plugins: { legend: legend() },
      scales: {
        x: { ...xAxis(), stacked: true },
        y: { ...yAxis(), stacked: true },
      },
    },
  });
}

// ── Chart 4: Currency Exposure (stacked area: Hard vs PKR) ───────────────────
function renderExposure(vr) {
  const { rows } = parseBlock(vr, true);
  if (!rows.length) return;

  const labels = rows.map((r) => fmtMonth(r[0]));
  const hard   = rows.map((r) => parseFloat(r[1]) || 0);
  const pkrA   = rows.map((r) => parseFloat(r[2]) || 0);

  // Show % share labels at a handful of evenly spaced months (inset from the
  // left edge, always including the latest month) — enough to read the trend
  // without cluttering every point.
  const LABEL_COUNT = 4;
  const last  = labels.length - 1;
  const start = Math.min(2, last);
  const span  = last - start;
  const labelIdx = new Set(
    Array.from({ length: LABEL_COUNT }, (_, k) =>
      start + (span ? Math.round((k * span) / (LABEL_COUNT - 1)) : 0))
  );

  const area = (label, data, color, dl) => ({
    label, data,
    backgroundColor: c(color, '.5'),
    borderColor: c(color, '.85'),
    borderWidth: 1,
    fill: true,
    tension: .3,
    pointRadius: 0,
    pointHoverRadius: 4,
    datalabels: {
      display: (ctx) => labelIdx.has(ctx.dataIndex),
      formatter: (value, ctx) => {
        const i = ctx.dataIndex;
        const total = hard[i] + pkrA[i];
        return total ? Math.round((value / total) * 100) + '%' : null;
      },
      color: '#fff',
      // No background pill — a soft shadow keeps the text legible over the area.
      textShadowColor: 'rgba(0,0,0,.6)',
      textShadowBlur: 4,
      font: { size: 10, weight: 'bold' },
      ...dl,
    },
  });

  mkChart('chart-exposure', {
    type: 'line',
    // The datalabels plugin is loaded but never globally registered, so enable
    // it inline for just this chart (per-dataset display() drives which months
    // actually show a label).
    plugins: window.ChartDataLabels ? [window.ChartDataLabels] : [],
    data: {
      labels,
      datasets: [
        // PKR sits on top of the stack → label above the top line; hard
        // currency is the lower band → label tucked just under the boundary.
        area('Hard Currency (GBP/USD/Gold)', hard, 'purple',
             { anchor: 'center', align: 'bottom', offset: 2, clamp: true }),
        area('PKR Assets',                   pkrA, 'blue',
             { anchor: 'end', align: 'top', offset: 2, clamp: true }),
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      layout: { padding: { top: 16, right: 26 } },  // room for top + last-month % labels
      plugins: { legend: legend() },
      scales: {
        x: { ...xAxis(), stacked: true },
        y: { ...yAxis(), stacked: true },
      },
    },
  });
}

// ── Chart 5: Return Gap (Net Worth as flat reference, savings as the gap) ─────
// Net Worth is drawn as a constant reference line at y=0. The "Net Savings
// Invested" line is plotted as its difference from that reference
// (savings − net worth), so the vertical gap to the zero line is exactly the
// cumulative investment return. Removing the shared growth trend makes it easy
// to read how returns build (or lag) over time instead of two near-parallel
// lines climbing together.
function renderGrowth(vr) {
  const { rows } = parseBlock(vr, true);
  if (!rows.length) return;

  const labels  = rows.map((r) => fmtMonth(r[0]));
  const nw      = rows.map((r) => parseFloat(r[1]) || 0);
  const savings = rows.map((r) => parseFloat(r[2]) || 0);

  // Difference of savings from the net-worth reference. Negative when
  // investments have added value (net worth above pure savings); positive when
  // savings would have left you better off (returns lagged).
  const gap = savings.map((s, i) => s - nw[i]);

  // Signed PKR formatter — the shared fmtPKR() strips the sign via Math.abs(),
  // which would make every tick on this (negative) axis read as positive.
  const fmtSigned = (v) => (v < 0 ? '−' : '') + fmtPKR(v);

  mkChart('chart-growth', {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Net Worth (reference)',
          data: labels.map(() => 0),
          borderColor: c('blue', '.9'),
          backgroundColor: 'transparent',
          borderWidth: 2,
          fill: false, tension: 0, pointRadius: 0,
          pointStyle: 'line',
        },
        {
          label: 'Net Savings Invested (vs Net Worth)',
          data: gap,
          borderColor: c('green', '.85'),
          // Shade the gap between the savings line and the reference — this band
          // IS the investment return at each month.
          backgroundColor: c('green', '.12'),
          fill: 'origin',
          tension: .35, pointRadius: 2,
          pointStyle: 'line',
          // Colour the line red over any stretch where savings beat net worth
          // (returns lagged, i.e. the gap rises above the reference).
          segment: {
            borderColor: (ctx) =>
              ctx.p0.parsed.y > 0 ? c('red', '.85') : c('green', '.85'),
          },
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: legend('bottom', true),
        tooltip: {
          callbacks: {
            label: (item) => {
              const i = item.dataIndex;
              return item.datasetIndex === 0
                ? ` Net Worth: ${fmtPKRFull(nw[i])}`
                : ` Savings invested: ${fmtPKRFull(savings[i])}`;
            },
            afterBody: (items) => {
              const i   = items[0].dataIndex;
              const ret = nw[i] - savings[i];
              return ret >= 0
                ? `Investment return: +${fmtPKRFull(ret)}`
                : `Below savings: −${fmtPKRFull(Math.abs(ret))}`;
            },
          },
        },
      },
      scales: { x: xAxis(), y: yAxis({ ticks: { ...TICK, callback: fmtSigned } }) },
    },
  });
}

// ── Chart 6: Return vs Contribution (horizontal stacked bar) ──────────────────
function renderContribution(vr) {
  const { rows }  = parseBlock(vr);
  if (!rows.length) return;

  const labels    = rows.map((r) => r[0]);
  const nominal   = rows.map((r) => parseFloat(r[1]) || 0);  // actual PKR deposited
  const nomReturn = rows.map((r) => parseFloat(r[2]) || 0);  // current value − nominal (signed)
  const inflFloor = rows.map((r) => parseFloat(r[3]) || 0);  // CPI-adjusted deposit value today
  const kind      = rows.map((r) => r[6] || 'invest');       // 'invest' | 'bank'

  const currentBal = nominal.map((n, i) => n + nomReturn[i]);
  const realGain   = currentBal.map((b, i) => b - inflFloor[i]);
  const realPct    = realGain.map((rg, i) => inflFloor[i] !== 0 ? (rg / Math.abs(inflFloor[i])) * 100 : 0);

  // Sort all accounts by real % performance (best at top).
  // Bank accounts use realPct (inflation erosion) as their rank key — nomReturn
  // stays 0 for them so the bars are unchanged; only their position in the list changes.
  const order = Array.from({ length: labels.length }, (_, i) => i)
    .sort((a, b) => realPct[b] - realPct[a]);
  const reorder = (arr) => order.map((i) => arr[i]);

  const labels_s    = reorder(labels);
  const nominal_s   = reorder(nominal);
  const nomReturn_s = reorder(nomReturn);
  const inflFloor_s = reorder(inflFloor);
  const kind_s      = reorder(kind);
  const currentBal_s = reorder(currentBal);
  const realGain_s  = reorder(realGain);
  const realPct_s   = reorder(realPct);

  // Gain:  blue = nominal deposits,   green extends to current value
  // Loss:  blue = current value,      red extends to nominal deposits
  const blueData  = nominal_s.map((n, i) => nomReturn_s[i] >= 0 ? n : currentBal_s[i]);
  const greenData = nomReturn_s.map((r) => Math.max(r, 0));
  const redData   = nomReturn_s.map((r) => r < 0 ? Math.abs(r) : 0);

  const xMax = Math.ceil(Math.max(...currentBal_s, ...nominal_s, ...inflFloor_s) / 50000) * 50000;

  const annotations = Object.fromEntries(
    inflFloor_s.map((floor, i) => [
      `floor${i}`,
      {
        type:        'line',
        xMin:        floor,
        xMax:        floor,
        yMin:        i - 0.46,
        yMax:        i + 0.46,
        borderColor: 'rgba(160,160,170,.70)',
        borderWidth: 1.5,
        borderDash:  [5, 3],
        label: {
          display:         i === 0,
          content:         'Inflation floor',
          position:        'start',
          yAdjust:         -13,
          color:           'rgba(160,160,170,.85)',
          font:            { size: 8, weight: '500' },
          backgroundColor: 'transparent',
          padding:         0,
        },
      },
    ])
  );

  const sgn    = (v) => (v >= 0 ? '+' : '−') + fmtPKR(Math.abs(v));
  const fmtPct = (v) => (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(1) + '%';
  const makeLabel = (i) => [fmtPKR(currentBal_s[i]), `${fmtPct(realPct_s[i])} real`];

  const labelCfg = {
    anchor: 'end', align: 'right', padding: { left: 6 },
    color: '#94A3B8', font: { size: 8 },
    formatter: (_, ctx) => makeLabel(ctx.dataIndex),
  };

  mkChart('chart-contribution', {
    type: 'bar',
    data: {
      labels: labels_s,
      datasets: [
        {
          label: 'Invested',
          data:  blueData,
          backgroundColor: c('blue', '.65'),
          stack: 'rc',
          datalabels: {
            ...labelCfg,
            display:   (ctx) => kind_s[ctx.dataIndex] === 'bank',
            formatter: (_, ctx) => fmtPKR(currentBal_s[ctx.dataIndex]),
          },
        },
        {
          label: 'Profit',
          data:  greenData,
          backgroundColor: c('green', '.80'),
          stack: 'rc',
          datalabels: { ...labelCfg, display: (ctx) => greenData[ctx.dataIndex] > 0 },
        },
        {
          label: 'Loss',
          data:  redData,
          backgroundColor: c('red', '.80'),
          stack: 'rc',
          datalabels: { ...labelCfg, display: (ctx) => redData[ctx.dataIndex] > 0 },
        },
      ],
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      layout: { padding: { right: 0 } },
      plugins: {
        legend: legend('top'),
        annotation: { annotations },
        tooltip: {
          callbacks: {
            label: (item) => {
              const i   = item.dataIndex;
              const rp  = realPct_s[i];
              const rgStr = rp >= 0
                ? ` Real gain:  +${Math.abs(rp).toFixed(1)}%`
                : ` Real loss:   −${Math.abs(rp).toFixed(1)}%`;
              if (item.datasetIndex === 0) return ` Invested:   PKR ${fmtN(nominal_s[i])}`;
              if (item.datasetIndex === 1) return [` Profit:    +PKR ${fmtN(nomReturn_s[i])}`, rgStr];
              return [` Loss:       PKR ${fmtN(nomReturn_s[i])}`, rgStr];
            },
          },
        },
      },
      scales: {
        x: {
          stacked: true,
          max:     xMax,
          ticks:   { ...TICK, callback: (v) => fmtN(v) },
          grid:    GRID_Y,
        },
        y: {
          stacked: true,
          ticks:   { color: '#94A3B8', font: { size: 10 } },
          grid:    GRID_X,
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

    // Fetch all 5 time-series blocks + scalar metrics in one call
    const batch1 = await batchGet([
      `Dashboard!A${R}:C`,       // Block A: NW timeline
      `Dashboard!E${R}:I`,       // Block B: Cash flow
      `Dashboard!K${R}:P`,       // Block C: Asset allocation
      `Dashboard!R${R}:T`,       // Block D: Currency exposure
      `Dashboard!V${R}:X`,       // Block E: Growth attribution
      `Dashboard!Y${R}:Z${R+2}`, // Scalars: Wealth CAGR nom + real
    ]);

    const [vrA, vrB, vrC, vrD, vrE, vrScalars] = batch1.valueRanges;

    const cagrNom  = parseFloat(vrScalars?.values?.[1]?.[1]) || 0;
    const cagrReal = parseFloat(vrScalars?.values?.[2]?.[1]) || 0;

    const bRows    = parseBlock(vrB, true).rows;
    const avgSavingsRate = bRows.length
      ? Math.round(bRows.reduce((s, r) => s + (parseFloat(r[4]) || 0), 0) / bRows.length)
      : 0;

    const sgn = (v) => (v >= 0 ? '+' : '') + v.toFixed(1);
    $('metric-savings').textContent = `${avgSavingsRate}%`;
    $('metric-cagr').textContent    = `${sgn(cagrNom)}%`;
    $('metric-real').textContent    = `${sgn(cagrReal)}%`;

    // Count only valid YYYY-MM rows (skip header + gap rows + block_f account rows
    // that all land in the same unbounded A:C range we fetched above)
    const nMonths  = Math.max(
      (vrA.values || []).slice(1).filter((r) => r[0] && IS_MONTH(r[0]) && r[0] <= NOW_MONTH).length,
      1,
    );
    const blockFRow = R + nMonths + 3;

    const batch2 = await batchGet([`Dashboard!A${blockFRow}:G`]);
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
  // Guest entry needs no Google library — wire it immediately.
  $('guest-btn').addEventListener('click', enterGuestMode);

  // GIS loads async — poll until ready
  const wait = setInterval(() => {
    if (window.google?.accounts?.oauth2) {
      clearInterval(wait);
      initAuth();
    }
  }, 100);
});
