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
  if (useLines) { labels.usePointStyle = true; labels.pointStyleWidth = 18; }
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
    yeEl.textContent = fmtPKR(yearEndNW);
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
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Income',   data: income,   borderColor: c('green', '.9'),  backgroundColor: 'transparent', tension: .35, pointRadius: 2, pointStyle: 'line' },
        { label: 'Expenses', data: expenses, borderColor: c('red', '.9'),    backgroundColor: 'transparent', tension: .35, pointRadius: 2, pointStyle: 'line' },
        { label: 'Net Savings', data: savings, borderColor: c('blue', '.9'), backgroundColor: c('blue', '.07'), fill: true, tension: .35, pointRadius: 2, pointStyle: 'line' },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: legend('bottom', true) },
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
  }));

  mkChart('chart-allocation', {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
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

  const area = (label, data, color) => ({
    label, data,
    backgroundColor: c(color, '.5'),
    borderColor: c(color, '.85'),
    borderWidth: 1,
    fill: true,
    tension: .3,
    pointRadius: 0,
    pointHoverRadius: 4,
  });

  mkChart('chart-exposure', {
    type: 'line',
    data: {
      labels,
      datasets: [
        area('PKR Assets',                   pkrA, 'blue'),
        area('Hard Currency (GBP/USD/Gold)', hard, 'purple'),
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
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
  const { rows } = parseBlock(vr, true);
  if (!rows.length) return;

  const labels  = rows.map((r) => fmtMonth(r[0]));
  const nw      = rows.map((r) => parseFloat(r[1]) || 0);
  const savings = rows.map((r) => parseFloat(r[2]) || 0);

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
          pointStyle: 'line',
        },
        {
          label: 'Savings Invested (Real)',
          data: savings,
          borderColor: c('yellow', '.8'),
          backgroundColor: 'transparent',
          borderDash: [5, 4], tension: .35, pointRadius: 2,
          pointStyle: 'line',
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: legend('bottom', true),
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

  // Gain:  blue = nominal deposits,   green extends to current value
  // Loss:  blue = current value,      red extends to nominal deposits
  const blueData  = nominal.map((n, i) => nomReturn[i] >= 0 ? n : currentBal[i]);
  const greenData = nomReturn.map((r) => Math.max(r, 0));
  const redData   = nomReturn.map((r) => r < 0 ? Math.abs(r) : 0);

  const xMax = Math.ceil(Math.max(...currentBal, ...nominal, ...inflFloor) / 50000) * 50000;

  const annotations = Object.fromEntries(
    inflFloor.map((floor, i) => [
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
  const makeLabel = (i) => [fmtPKR(currentBal[i]), `${fmtPct(realPct[i])} real`];

  const labelCfg = {
    anchor: 'end', align: 'right', padding: { left: 6 },
    color: '#94A3B8', font: { size: 8 },
    formatter: (_, ctx) => makeLabel(ctx.dataIndex),
  };

  mkChart('chart-contribution', {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Invested',
          data:  blueData,
          backgroundColor: c('blue', '.65'),
          stack: 'rc',
          datalabels: {
            ...labelCfg,
            display:   (ctx) => kind[ctx.dataIndex] === 'bank',
            formatter: (_, ctx) => fmtPKR(currentBal[ctx.dataIndex]),
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
              const rp  = realPct[i];
              const rgStr = rp >= 0
                ? ` Real gain:  +${Math.abs(rp).toFixed(1)}%`
                : ` Real loss:   −${Math.abs(rp).toFixed(1)}%`;
              if (item.datasetIndex === 0) return ` Invested:   PKR ${fmtN(nominal[i])}`;
              if (item.datasetIndex === 1) return [` Profit:    +PKR ${fmtN(nomReturn[i])}`, rgStr];
              return [` Loss:       PKR ${fmtN(nomReturn[i])}`, rgStr];
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
  // GIS loads async — poll until ready
  const wait = setInterval(() => {
    if (window.google?.accounts?.oauth2) {
      clearInterval(wait);
      initAuth();
    }
  }, 100);
});
