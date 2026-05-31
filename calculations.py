import pandas as pd

from config import GOLD_ACCOUNT_ID, PAKISTAN_ANNUAL_INFLATION
from db_queries import parse_grams


def compute_cpi_index(months: list) -> dict:
    """Returns {YYYY-MM: cumulative_cpi_index} where the first month = 100."""
    idx        = {}
    cumulative = 100.0
    for i, month_str in enumerate(months):
        if i > 0:
            year        = int(months[i - 1][:4])
            annual_rate = PAKISTAN_ANNUAL_INFLATION.get(year, 10.0) / 100
            cumulative *= (1 + annual_rate) ** (1 / 12)
        idx[month_str] = round(cumulative, 4)
    return idx


def build_cpi_series(all_months: list, hist_rates: dict) -> dict:
    """
    Returns {YYYY-MM: cpi_value} for every month in all_months.
    Prefers actual monthly CPI from the Market Rates sheet; falls back to the
    compute_cpi_index approximation scaled to match the actual values at the
    first overlap month. Only the ratio cpi_tx / cpi_eval matters.
    """
    raw    = compute_cpi_index(all_months)
    actual = {m: v["cpi"] for m, v in hist_rates.items() if v.get("cpi")}

    if not actual:
        return raw

    anchor = next((m for m in all_months if m in actual), None)
    scale  = (actual[anchor] / raw[anchor]) if (anchor and raw.get(anchor)) else 1.0

    return {m: (actual[m] if m in actual else round(raw[m] * scale, 4)) for m in all_months}


def compute_monthly_balances(tx, accounts, prices: dict, hist_rates: dict) -> pd.DataFrame:
    """
    Returns a tall DataFrame: one row per (month, account).
    USD and Gold equivalents use period-matched historical rates from hist_rates,
    falling back to today's live prices for any month not yet in the rate history.
    Balance (PKR - Real) is the inflation-adjusted cost basis in today's PKR terms:
    each transaction's PKR value is scaled by cpi_tx / cpi_today so that older
    deposits that experienced more inflation contribute proportionally less.
    """
    current_period = pd.Timestamp.today().to_period("M")
    start_period   = tx["period"].min()
    all_periods    = list(pd.period_range(start_period, current_period, freq="M"))

    months_list = [p.strftime("%Y-%m") for p in all_periods]
    cpi_series  = build_cpi_series(months_list, hist_rates)

    total_grams = parse_grams(tx[tx["accountID"] == GOLD_ACCOUNT_ID]["notes"])
    if total_grams == 0:
        total_grams = 2.5
    print(f"  Gold: {total_grams}g | Live PKR value: PKR {total_grams * prices['gold']:,.2f}")

    rows = []
    for period in all_periods:
        month_str  = period.strftime("%Y-%m")
        is_current = (period == current_period)
        snapshot   = tx[tx["period"] <= period]

        h           = hist_rates.get(month_str, {})
        period_usd  = h.get("usd")  or prices["usd"]
        period_gold = h.get("gold") or prices["gold"]

        for _, acct in accounts.iterrows():
            acct_id  = acct["accountsTableID"]
            currency = acct["accountCurrency"]
            acct_tx  = snapshot[snapshot["accountID"] == acct_id]

            if is_current and acct_id == GOLD_ACCOUNT_ID:
                bal_pkr = total_grams * prices["gold"]
            elif is_current and currency == "GBP":
                native  = (acct_tx["amount_pkr"] * acct_tx["conversionRateNew"]).sum()
                bal_pkr = native * prices["gbp"]
            elif is_current and currency == "USD":
                native  = (acct_tx["amount_pkr"] * acct_tx["conversionRateNew"]).sum()
                bal_pkr = native * prices["usd"]
            else:
                bal_pkr = acct_tx["amount_pkr"].sum()

            if acct_id == GOLD_ACCOUNT_ID:
                bal_native = round(parse_grams(acct_tx["notes"]), 4) or ""
            elif currency in ("GBP", "USD"):
                bal_native = round(
                    (acct_tx["amount_pkr"] * acct_tx["conversionRateNew"]).sum(), 4
                )
            else:
                bal_native = ""

            bal_usd  = round(bal_pkr / period_usd,  4)
            bal_gold = round(bal_pkr / period_gold, 6)

            cpi_T  = cpi_series.get(month_str, 100)
            tx_cpi = pd.to_numeric(
                acct_tx["period"].apply(
                    lambda p: cpi_series.get(p.strftime("%Y-%m"), cpi_T)
                ),
                errors="coerce",
            ).fillna(cpi_T)
            bal_real = round((acct_tx["amount_pkr"] * tx_cpi / cpi_T).sum(), 2)

            rows.append({
                "Month":                month_str,
                "Account":              acct["accountName"],
                "Group":                acct["accountGroupName"] or "",
                "Type":                 acct["accountTypeName"]  or "",
                "Currency":             currency,
                "Balance (PKR)":        round(bal_pkr, 2),
                "Balance (PKR - Real)": bal_real,
                "Balance (Native)":     bal_native,
                "Balance (USD)":        bal_usd,
                "Balance (Gold g)":     bal_gold,
            })

    return pd.DataFrame(rows)


def compute_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per month with net worth totals and indexes rebased to 100 at the
    earliest month for trend comparison across PKR, USD, Gold, and Real PKR.
    """
    months = sorted(df["Month"].unique())

    nw_pkr  = df.groupby("Month")["Balance (PKR)"].sum()
    nw_usd  = df.groupby("Month")["Balance (USD)"].sum()
    nw_gold = df.groupby("Month")["Balance (Gold g)"].sum()
    nw_real = df.groupby("Month")["Balance (PKR - Real)"].sum()

    pkr_vals  = [nw_pkr.get(m, 0)  for m in months]
    usd_vals  = [nw_usd.get(m, 0)  for m in months]
    gold_vals = [nw_gold.get(m, 0) for m in months]
    real_vals = [nw_real.get(m, 0) for m in months]

    base_pkr  = pkr_vals[0]  or 1
    base_usd  = usd_vals[0]  or 1
    base_gold = gold_vals[0] or 1
    base_real = real_vals[0] or 1

    return pd.DataFrame({
        "Month":                months,
        "Net Worth (PKR)":      [round(v, 2) for v in pkr_vals],
        "Net Worth (USD)":      [round(v, 2) for v in usd_vals],
        "Net Worth (Gold g)":   [round(v, 4) for v in gold_vals],
        "Real Net Worth (PKR)": [round(v, 2) for v in real_vals],
        "PKR Index":            [round(v / base_pkr  * 100, 2) for v in pkr_vals],
        "USD Index":            [round(v / base_usd  * 100, 2) for v in usd_vals],
        "Gold Index":           [round(v / base_gold * 100, 2) for v in gold_vals],
        "Real PKR Index":       [round(v / base_real * 100, 2) for v in real_vals],
    })


def compute_account_pkr_values(monthly_df: pd.DataFrame, prices: dict):
    """
    Wide DataFrame of raw PKR-denominated values per account:
      Month | [Acct PKR] | [Acct USD (PKR)] | [Acct Gold (PKR)] | [Acct Real PKR] | ...
    Empty cells before each account's first active month. No rebasing applied.
    """
    months        = sorted(monthly_df["Month"].unique())
    account_names = monthly_df["Account"].drop_duplicates().tolist()
    usd_rate  = prices["usd"]
    gold_rate = prices["gold"]

    data   = {"Month": months}
    active = []

    for name in account_names:
        acct = monthly_df[monthly_df["Account"] == name].set_index("Month")

        pkr_all = pd.to_numeric(
            pd.Series({m: acct.at[m, "Balance (PKR)"] if m in acct.index else 0 for m in months}),
            errors="coerce",
        ).fillna(0)
        if (pkr_all.abs() <= 0.01).all():
            continue

        first_m = pkr_all[pkr_all.abs() > 0.01].index[0]

        rows_pkr, rows_usd, rows_gold, rows_real = [], [], [], []
        for month in months:
            if month < first_m or month not in acct.index:
                rows_pkr.append(""); rows_usd.append("")
                rows_gold.append(""); rows_real.append("")
            else:
                bp = float(acct.at[month, "Balance (PKR)"])
                bu = float(acct.at[month, "Balance (USD)"])
                bg = float(acct.at[month, "Balance (Gold g)"])
                br = float(acct.at[month, "Balance (PKR - Real)"])
                rows_pkr.append( round(bp, 2))
                rows_usd.append( round(bu * usd_rate,  2))
                rows_gold.append(round(bg * gold_rate, 2))
                rows_real.append(round(br, 2))

        data[f"{name} PKR"]        = rows_pkr
        data[f"{name} USD (PKR)"]  = rows_usd
        data[f"{name} Gold (PKR)"] = rows_gold
        data[f"{name} Real PKR"]   = rows_real
        active.append(name)

    return pd.DataFrame(data), active


def compute_account_indices(monthly_df: pd.DataFrame):
    """
    Wide DataFrame of per-account indexed values, all rebased to 100 at each
    account's first non-zero balance month. Comparing PKR vs Real PKR series
    directly shows whether the account is beating or lagging inflation.
    """
    months        = sorted(monthly_df["Month"].unique())
    account_names = monthly_df["Account"].drop_duplicates().tolist()

    data   = {"Month": months}
    active = []

    for name in account_names:
        acct = monthly_df[monthly_df["Account"] == name].set_index("Month")

        pkr_all = pd.to_numeric(
            pd.Series({m: acct.at[m, "Balance (PKR)"] if m in acct.index else 0 for m in months}),
            errors="coerce",
        ).fillna(0)

        nonzero = pkr_all[pkr_all.abs() > 0.01]
        if nonzero.empty:
            continue

        first_m   = nonzero.index[0]
        base_pkr  = float(acct.at[first_m, "Balance (PKR)"])        if first_m in acct.index else 1
        base_usd  = float(acct.at[first_m, "Balance (USD)"])        if first_m in acct.index else 1
        base_gold = float(acct.at[first_m, "Balance (Gold g)"])     if first_m in acct.index else 1
        base_real = float(acct.at[first_m, "Balance (PKR - Real)"]) if first_m in acct.index else 1

        rows_pkr, rows_usd, rows_gold, rows_real = [], [], [], []
        for month in months:
            if month < first_m:
                rows_pkr.append("");  rows_usd.append("")
                rows_gold.append(""); rows_real.append("")
            else:
                bp = float(acct.at[month, "Balance (PKR)"])        if month in acct.index else 0
                bu = float(acct.at[month, "Balance (USD)"])        if month in acct.index else 0
                bg = float(acct.at[month, "Balance (Gold g)"])     if month in acct.index else 0
                br = float(acct.at[month, "Balance (PKR - Real)"]) if month in acct.index else 0
                rows_pkr.append( round(bp / base_pkr  * 100, 2) if base_pkr  else "")
                rows_usd.append( round(bu / base_usd  * 100, 2) if base_usd  else "")
                rows_gold.append(round(bg / base_gold * 100, 2) if base_gold else "")
                rows_real.append(round(br / base_real * 100, 2) if base_real else "")

        data[f"{name} PKR"]      = rows_pkr
        data[f"{name} USD"]      = rows_usd
        data[f"{name} Gold"]     = rows_gold
        data[f"{name} Real PKR"] = rows_real
        active.append(name)

    return pd.DataFrame(data), active


def compute_inflation_rankings(
    monthly_df: pd.DataFrame, tx, accounts, hist_rates: dict
) -> pd.DataFrame:
    """
    Per-account inflation beat metrics for the latest month.

    All-Time Beat = Current Balance / Real Cost Basis (contribution-based).
    Only meaningful for accounts where money is deliberately placed to grow:
      - Investment accounts (accountTypeName contains "invest") and Gold:
          cost basis = type 2 opening + positive type 5 transfers in only.
          Fund profit distributions (type 4 income) are returns, not new capital.
      - Foreign currency accounts (GBP, USD):
          same contribution-based approach; FX appreciation is the return.
      - Bank / cash accounts:
          All-Time Beat and Real Cost Basis are left blank. Large transfers OUT
          (e.g. to MCF) would deflate the cost basis and produce a misleadingly
          high ratio. Period beats are the correct metric for these accounts.

    TOTAL row: net external savings = CPI-adjusted income from bank accounts only
    (salary, business income) minus all expenses. Fund distributions are excluded
    because they are portfolio returns, not new money from the world.

    Period Beat (1M / 3M / YTD / FYTD / 1Y / 3Y):
      = (current_balance / start_balance) / (cpi_today / cpi_start)
      > 1.0 means the account grew faster than inflation over that window.

    Liabilities excluded. Investment accounts sorted first by All-Time Beat,
    cash accounts listed below.
    """
    months_list  = sorted(monthly_df["Month"].unique())
    cpi_series   = build_cpi_series(months_list, hist_rates)
    latest_month = months_list[-1]
    cpi_today    = cpi_series.get(latest_month, 100)

    # Accounts where "income" = fund/FX return, not external earnings
    invest_ids = set(
        accounts.loc[
            accounts["accountTypeName"].str.contains("invest", case=False, na=False) |
            (accounts["accountCurrency"] != "PKR"),
            "accountsTableID",
        ].tolist()
    ) | {GOLD_ACCOUNT_ID}

    # Period start months
    today_p  = pd.Period(latest_month, "M")

    periods = {
        "1M": (today_p -  1).strftime("%Y-%m"),
        "3M": (today_p -  3).strftime("%Y-%m"),
        "6M": (today_p -  6).strftime("%Y-%m"),
        "1Y": (today_p - 12).strftime("%Y-%m"),
        "2Y": (today_p - 24).strftime("%Y-%m"),
    }
    available = set(months_list)

    latest_df = monthly_df[monthly_df["Month"] == latest_month].set_index("Account")

    def _period_beats(name, current_bal):
        cols = {}
        for label, start_m in periods.items():
            key = f"Beat ({label})"
            if start_m not in available or start_m >= latest_month:
                cols[key] = ""; continue
            rows = monthly_df[
                (monthly_df["Month"] == start_m) & (monthly_df["Account"] == name)
            ]
            if rows.empty:
                cols[key] = ""; continue
            start_bal = float(rows.iloc[0]["Balance (PKR)"])
            if abs(start_bal) <= 0.01:
                cols[key] = ""; continue
            cpi_start = cpi_series.get(start_m, cpi_today)
            cols[key] = round((current_bal / start_bal) / (cpi_today / cpi_start), 4)
        return cols

    invest_rows = []

    for _, acct in accounts.iterrows():
        acct_id = acct["accountsTableID"]
        name    = acct["accountName"]

        if acct_id not in invest_ids:
            continue
        if name not in latest_df.index:
            continue
        current_bal = float(latest_df.at[name, "Balance (PKR)"])
        if latest_df.at[name, "Group"] == "Liabilities" or abs(current_bal) <= 100:
            continue

        acct_tx = tx[tx["accountID"] == acct_id]
        cost_tx = acct_tx[
            acct_tx["transactionTypeID"].isin([2, 5]) & (acct_tx["amount_pkr"] > 0)
        ]
        if len(cost_tx):
            tx_cpis   = cost_tx["period"].apply(
                lambda p: cpi_series.get(p.strftime("%Y-%m"), cpi_today)
            )
            real_cost = round((cost_tx["amount_pkr"] * tx_cpis / cpi_today).sum(), 2)
        else:
            real_cost = 0.0
        all_time  = round(current_bal / real_cost, 4) if abs(real_cost) > 0.01 else ""
        real_gain = round(current_bal - real_cost, 2) if all_time != "" else ""

        invest_rows.append({
            "Account":               name,
            "Current Balance (PKR)": round(current_bal, 2),
            "Real Cost Basis (PKR)": real_cost,
            "All-Time Beat":         all_time,
            **_period_beats(name, current_bal),
            "Real Gain/Loss (PKR)":  real_gain,
        })

    result_df = (
        pd.DataFrame(invest_rows)
        .sort_values("All-Time Beat", ascending=False,
                     key=lambda s: pd.to_numeric(s, errors="coerce").fillna(-999))
        if invest_rows else pd.DataFrame()
    )

    # Total Net Worth row: net external savings (salary/business income minus spending)
    # Exclude income from investment/FX accounts — those are portfolio returns, not new money
    non_invest_ids = set(accounts["accountsTableID"].tolist()) - invest_ids

    def _cpi_sum(subset):
        if len(subset) == 0:
            return 0.0
        cpis = subset["period"].apply(
            lambda p: cpi_series.get(p.strftime("%Y-%m"), cpi_today)
        )
        return (subset["amount_pkr"] * cpis / cpi_today).sum()

    # income (positive) from bank accounts + expenses (negative, all accounts) = net saved
    net_real_cost = round(
        _cpi_sum(tx[(tx["transactionTypeID"] == 4) & tx["accountID"].isin(non_invest_ids)]) +
        _cpi_sum(tx[tx["transactionTypeID"] == 3]),
        2,
    )
    total_pkr   = round(result_df["Current Balance (PKR)"].sum(), 2)
    total_ratio = round(total_pkr / net_real_cost, 4) if abs(net_real_cost) > 0.01 else ""

    included = set(result_df["Account"].tolist())
    total_period_cols = {}
    for label, start_m in periods.items():
        key = f"Beat ({label})"
        if start_m not in available or start_m >= latest_month:
            total_period_cols[key] = ""; continue
        start_nw = monthly_df[
            (monthly_df["Month"] == start_m) & monthly_df["Account"].isin(included)
        ]["Balance (PKR)"].sum()
        if abs(start_nw) <= 0.01:
            total_period_cols[key] = ""; continue
        cpi_start = cpi_series.get(start_m, cpi_today)
        total_period_cols[key] = round(
            (total_pkr / start_nw) / (cpi_today / cpi_start), 4
        )

    total_row = pd.DataFrame([{
        "Account":               "TOTAL NET WORTH",
        "Current Balance (PKR)": total_pkr,
        "Real Cost Basis (PKR)": net_real_cost,
        "All-Time Beat":         total_ratio,
        **total_period_cols,
        "Real Gain/Loss (PKR)":  round(total_pkr - net_real_cost, 2) if total_ratio != "" else "",
    }])

    return pd.concat([result_df, total_row], ignore_index=True)
