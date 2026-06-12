# TODO — queued dashboard changes

**Workflow:** changes added here are applied **on the next change request** (bundled
together with whatever the new request asks for). Once applied, move the item to
the "Done" section with its commit hash.

## Pending

_(none)_

## Done

Feature change (guest-login request):

-5. **Guest login with anonymised data** — added a "Continue as guest" button on
   the sign-in screen. Guests get **no Google access token**, so the real Sheet is
   never contacted; `batchGet` short-circuits to `demoBatchGet`, which serves a
   structurally identical **synthetic** dataset (fabricated numbers, regenerated
   on refresh). A "Sample data" pill shows in the header during guest mode.
   sw.js cache v19 → v20.

CI change (commit `5f59ca8`):

-4. **Workflow run frequency → 4×/day** — `networth.yml` cron changed from
   `0 3 * * *` (once daily, 08:00 PKT) to `0 3,9,15,21 * * *` (every 6h:
   08:00 / 14:00 / 20:00 / 02:00 PKT). No dashboard/sw.js change.

Layout change (commit `11a7617`+):

-3. **Fit all 3 chart rows in one viewport (no scroll)** — chart heights switched
   from fixed px to `max(floor, calc((100vh - 330px) * ratio / 650))`, preserving
   the 230:210:210 proportion; mobile keeps fixed 210px + scroll. sw.js v17 → v18.

Layout change (commit `5c7db25`+):

-2. **Swap Portfolio Health ↔ Net Worth vs Savings; Row 1 now 50-50** — Net Worth
   vs Savings moved up beside Net Worth (both `col-half`, `chart-wrap-row1`);
   Portfolio Health moved down beside Income vs Expenses. sw.js cache v16 → v17.

Layout change (commit `60d61ce`):

-1. **Income vs Expenses + Net Worth vs Savings on one row** — merged the two
   standalone cards into a `.row-split` (50-50, `.col-half`); stacks on mobile.
   sw.js cache bumped v15 → v16.

Layout change (commit `b07f364`):

0. **Asset Allocation + Currency Exposure on one row** — both wrapped in a
   `.row-split` with new `.col-half` class (50-50 split); stacks on mobile.
   sw.js cache bumped v14 → v15.

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
