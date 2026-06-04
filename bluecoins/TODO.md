# TODO — queued dashboard changes

**Workflow:** changes added here are applied **on the next change request** (bundled
together with whatever the new request asks for). Once applied, move the item to
the "Done" section with its commit hash.

## Pending

_(none)_

## Done

Applied together in the chart-cleanup change request:

1. **Currency Exposure area — stacking order** — Hard Currency now on the bottom,
   PKR Assets on top (`renderExposure` dataset order swapped).
2. **Forecast line — legend dash** — `legend()` now mirrors each dataset's
   `borderDash` onto its legend marker via `generateLabels`, so Forecast /
   Inflation Floor / Savings Invested read as dashed in the legend.
3. **Year-End KPI renamed** → **"EOY Forecast"** (index.html + tooltip).
4. **Year-End KPI formatting** — now `fmtN` (nearest whole rupee, thousand
   separators) instead of compact `fmtPKR`.
5. **Removed "REAL PKR" badge** from the "Net Worth vs Savings Invested" card.
6. **Fixed "Net Worth vs Savings Invested"** — savings baseline is now nominal
   + opening balances (`calculations.py` block_e), so the gap = true return
   (~3%) instead of the old inflation/opening-balance artifact (~32%). Dataset
   label dropped "(Real)". Verified: NW 1,699,145 / Savings 1,648,647 / gap
   50,498 (~3%). **Needs a workflow run** to refresh the sheet data block.

Also in the same change request (not previously queued):

7. **Removed duplicate Google Sheets charts** that the web app already renders:
   - `write_dashboard_sheet` no longer creates the 6 embedded charts (keeps the
     data blocks the web app reads; `_clear_charts` removes old chart objects).
   - `write_analysis_sheet` dropped the "Net Worth (PKR)" chart, kept the indexed
     "Value Trend" chart (not in the web app).
   - Kept per-account charts in `Account Analysis` / `Account Values` (not in the
     web app). **Needs a workflow run** to strip the old embedded charts.
