# How the Finance Dashboard Works — Plain English

---

## The Basics

### Net Worth (PKR)
Just the sum of every account balance converted to PKR at today's exchange rates.
- PKR accounts: taken as-is from transactions
- GBP/USD accounts: native balance × today's live rate
- Gold: grams held × today's 24k gold price per gram

**What to check:** Does this match what you'd expect if you added up your bank balances, investments, and gold?

---

### Real Net Worth (PKR)
Same as Net Worth, but older money is worth less in today's terms.

Each transaction is multiplied by `CPI_at_transaction / CPI_today`. Since CPI today is always larger than in the past, old deposits get a fraction smaller than 1 — so they shrink.

**Example:** You deposited 100,000 PKR in 2022. Inflation has been ~20% since then. Real value = 100,000 × (2022 CPI / 2024 CPI) ≈ 83,000 PKR in today's money.

**What to check:** Real NW should always be lower than Nominal NW and grow more slowly. If they track identically, CPI data may not be loading.

---

### CPI Series
The script uses World Bank monthly CPI data (base year 2010 = 100) loaded from the Market Rates sheet. If a month is missing, it estimates using the Pakistan annual inflation rate from `config.py`.

**What to check:** The script prints `CPI: 377 months … 2026-05=515.64`. A value of ~500 for 2026 means prices are roughly 5× what they were in 2010 — reasonable for Pakistan.

---

## Investment Accounts

### Real Cost Basis (the blue bar)
For each investment deposit, multiply by `CPI_deposit / CPI_today` (a number less than 1). Sum them up.

This answers: *"In today's purchasing power, how much did I actually give up when I made these deposits?"*

Because older deposits had more purchasing power eroded by inflation, they contribute less to this number than their face value.

**Example:** 500,000 deposited in 2023, 300,000 in 2025. If inflation was 30% between 2023 and now, the 2023 deposit counts as ~385,000. The 2025 deposit counts as ~285,000. Real Cost Basis ≈ 670,000 — less than the 800,000 you actually put in.

---

### Inflation-Adjusted Value (the grey reference line)
For each deposit, multiply by `CPI_today / CPI_deposit` (a number greater than 1). Sum them up.

This answers: *"How much PKR would I need to deposit today to have spent the same purchasing power I spent back then?"*

This is the inflation hurdle. If your investment's current value is above this line, you beat inflation. Below it, you lost real value.

**Example:** Same 500,000 from 2023. If prices rose 30%, you'd need 650,000 today to buy the same things you bought with 500,000 back then. That's the floor.

**Key distinction:** Real Cost Basis deflates (shows less). Inflation Floor inflates (shows more). Both use the same deposit transactions — no returns included.

---

### Investment Return (the green bar)
`Current Balance − Real Cost Basis`

This is the raw gain. It can be negative (red bar) if the fund has lost value.

**What to check:** Does `Cost Basis + Return = Current Balance`? It should exactly.

---

### Return % (label on bar)
`Investment Return / Real Cost Basis × 100`

How much the account earned relative to what you put in (in real terms). A +15% means your current value is 15% above your inflation-deflated cost.

---

### All-Time Beat (in Inflation Rankings sheet)
`Current Balance / Real Cost Basis`

A ratio, not a percentage. 1.0 = breaking even in real terms. 1.2 = 20% real gain. Below 1.0 = losing to inflation.

**What to check:** Most investment accounts should be above 1.0 over time. If a long-held account is below 1.0, it's losing purchasing power.

---

### Period Beat (1M / 3M / 1Y / 2Y)
`(Balance_now / Balance_then) / (CPI_now / CPI_then)`

This measures growth vs inflation over a specific window. 1.05 means the account grew 5% more than inflation in that period.

**What to check:** Values consistently above 1.0 across periods = genuinely beating inflation. A high All-Time Beat but a low 1Y Beat may mean recent performance is weak.

---

## The Six Dashboard Charts

### 1. Real vs Nominal Net Worth (line chart)
Two lines over time: your PKR net worth and your inflation-adjusted net worth.

**What to look for:** If the gap between them is widening, more of your nominal growth is just inflation. If Real NW is also rising, you're genuinely getting richer.

---

### 2. Monthly Income vs Expenses (line chart)
Income = deposits into non-investment accounts (salary, business).
Expenses = all spending transactions.

**What to look for:** Income line should be above expenses. A falling gap = shrinking savings rate.

---

### 3. Asset Allocation over Time (stacked bar)
Splits your net worth each month into: Cash/PKR, Investments, Foreign Currency, Gold, Receivables, Liabilities.

**What to look for:** Are you diversifying over time? Is the liability slice growing or shrinking?

---

### 4. Currency Exposure (stacked bar)
Two stacks: Hard Currency (GBP + USD + Gold in PKR) vs PKR Assets.

**What to look for:** Hard currency protects against PKR devaluation. A growing hard currency slice = better hedge.

---

### 5. Net Worth vs Savings Invested (line chart)
Two lines: cumulative real savings (income minus expenses, CPI-adjusted) vs actual net worth.

**What to look for:** If Net Worth > Cumulative Savings, your investments are generating returns above what you've saved. The gap is investment alpha.

---

### 6. Return vs Contribution (horizontal bar)
One row per investment account. Blue = real cost basis, Green = return. Grey line = inflation floor.

**What to look for:**
- Total bar length > grey line → beating inflation ✓
- Large green bar relative to blue → high return on investment
- Bar shorter than grey line → investment is losing real value ✗
- Negative return (red) → fund is underwater ✗

---

## Accounts Not in Investment Charts
Cash accounts (Askari, HBL, Savings, Wallet, Easy Paisa, Easy Paisa) are excluded from the investment beat metrics because they have regular large outflows (spending). Calculating a "cost basis" for a spending account would be misleading.

Receivables = money owed to you, counted as an asset.
Payables = money you owe, counted as a liability (reduces net worth).
