# TODO — queued dashboard changes

**Workflow:** changes added here are applied **on the next change request** (bundled
together with whatever the new request asks for). Once applied, move the item to
the "Done" section with its commit hash.

## Pending

1. **Currency Exposure area — stacking order**
   - File: [docs/app.js](docs/app.js) → `renderExposure`
   - Put **Hard Currency at the bottom of the stack** and **PKR Assets on top**
     (currently PKR Assets is the base / Hard Currency on top). Swap the dataset
     order so `area('Hard Currency …', hard, 'purple')` comes first, then
     `area('PKR Assets', pkrA, 'blue')`.

2. **Forecast line — legend dash**
   - File: [docs/app.js](docs/app.js) → `renderNW` / `legend()`
   - The Forecast dataset draws a dotted line on the chart but its **legend marker
     renders solid**. Make the legend marker dashed/dotted to match (e.g. a custom
     `generateLabels` that carries `lineDash`, or set `lineDash` on the legend item
     for the Forecast dataset). The actual "Nominal Net Worth" / "Inflation Floor"
     markers should stay as-is.

3. **Year-End KPI — rename label**
   - Files: [docs/index.html](docs/index.html) (`#metric-yearend` label),
     [docs/app.js](docs/app.js) (`renderNW`, tooltip text)
   - Rename "Year-End" → **"EOY Forecast"** (confirmed by user).

4. **Year-End KPI — no rounding / full number**
   - File: [docs/app.js](docs/app.js) → `renderNW`
   - Display the forecast to the **nearest whole rupee with thousand separators**
     (use `fmtN`, e.g. `2,011,540`) instead of the compact `fmtPKR` (`2.01M`).

5. **Remove "REAL PKR" badge from the last chart**
   - File: [docs/index.html](docs/index.html#L109)
   - Delete `<span class="card-badge green-badge">REAL PKR</span>` from the
     "Net Worth vs Savings Invested" card header.

> When applying: bump the service-worker cache (`docs/sw.js` `CACHE = 'finance-vN'`).

### Note — label name (item 3)
Confirmed: **"EOY Forecast"**.

## Done
_(empty)_
