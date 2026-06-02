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

6. **Fix "Net Worth vs Savings Invested" — savings baseline (nominal + opening)**
   - **Why:** the current "return" gap (~32% of NW) is fake. It excludes opening
     balances and inflation-deflates the savings line, so opening wealth (~364k)
     and an inflation artifact (~134k) masquerade as investment return. Actual
     return is ~3% (~51k). User confirmed framing: **nominal, include opening**.
   - File: [calculations.py](calculations.py) → `compute_dashboard_data`, **block_e**
     - Build cumulative savings from **nominal** flows (use `amount_pkr`, NOT
       `cpi_adj_amt`): per month, `contributions = type-2 opening (all accounts)
       + type-4 income (non-invest accounts) + type-3 expenses`. `cum_savings +=
       contributions`. Keep type-4 income into investment accounts EXCLUDED
       (those are returns, not contributions).
     - Net Worth line stays nominal (`Balance (PKR)` sum). Both lines nominal now
       → gap = true returns.
   - File: [docs/app.js](docs/app.js) → `renderGrowth`
     - Rename dataset label "Savings Invested (Real)" → **"Savings Invested"**
       (drop "(Real)", it is nominal now). Tooltip "Return component" wording is
       now accurate — keep it.
   - **Requires a GitHub Actions workflow run** (block_e is sheet data written by
     the Python pipeline, not computed client-side).
   - Verify latest month: savings ≈ 1,648,647, NW ≈ 1,699,425, gap ≈ 50,778 (~3%).

> When applying: bump the service-worker cache (`docs/sw.js` `CACHE = 'finance-vN'`).
> Items touching Python (6) also need the workflow re-run to refresh sheet data.

### Note — label name (item 3)
Confirmed: **"EOY Forecast"**.

## Done
_(empty)_
