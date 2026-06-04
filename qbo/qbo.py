import requests
import pandas as pd


def fetch_account_classifications(access_token, company_id):
    url = f"https://quickbooks.api.intuit.com/v3/company/{company_id}/query"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    accounts, start = [], 1
    while True:
        q = (
            "SELECT Id, Name, FullyQualifiedName, Classification, "
            "AccountType, AccountSubType FROM Account "
            f"STARTPOSITION {start} MAXRESULTS 1000"
        )
        response = requests.get(url, headers=headers,
                                params={"query": q, "minorversion": "75"})
        response.raise_for_status()
        page = response.json().get("QueryResponse", {}).get("Account", [])
        accounts.extend(page)
        if len(page) < 1000:
            break
        start += 1000

    df = pd.DataFrame(accounts)
    df = df.rename(columns={"Id": "AccountId", "Name": "Account"})
    return df[["AccountId", "Account", "Classification", "AccountType", "AccountSubType"]]


def fetch_pnl_flat(access_token, company_id, start_date, end_date):
    """Fetch the P&L report and return one row per data line.
    Columns: AccountId, Account, Section, Amount.
    The P&L JSON is a nested section tree; this walks it recursively."""
    url = f"https://quickbooks.api.intuit.com/v3/company/{company_id}/reports/ProfitAndLoss"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "accounting_method": "Accrual",
        "minorversion": "75",
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    report = response.json()

    rows = []

    def _walk(row_list, section):
        for row in row_list:
            row_type = row.get("type", "")
            if row_type == "Section":
                col = row.get("Header", {}).get("ColData", [{}])
                section_name = col[0].get("value", section) if col else section
                _walk(row.get("Rows", {}).get("Row", []), section_name)
            elif row_type == "Data":
                col = row.get("ColData", [])
                account_id   = col[0].get("id", "")   if len(col) > 0 else ""
                account_name = col[0].get("value", "") if len(col) > 0 else ""
                amount_str   = col[1].get("value", "0") if len(col) > 1 else "0"
                try:
                    amount = float(amount_str) if amount_str else 0.0
                except ValueError:
                    amount = 0.0
                rows.append({
                    "AccountId":   account_id,
                    "Account":     account_name,
                    "Section":     section,
                    "Amount":      amount,
                })

    _walk(report.get("Rows", {}).get("Row", []), "")
    return pd.DataFrame(rows)


# ── Date range for P&L report ─────────────────────────────────────────────────
PNL_START = "2024-01-01"   # update as needed
PNL_END   = "2024-12-31"

# ── Franchise token table (Franchise, Validity, Access_Token, Company_ID) ─────
df_xl = pd.read_excel(output_path_xl, dtype=object)

# ── Pull P&L + account classifications per franchise ─────────────────────────
PNL_COLS = ['AccountId', 'Account', 'Section', 'Amount',
            'Classification', 'AccountType', 'AccountSubType',
            'franchise', 'company_id']
pnl_rows  = []
stat_dict = {}

for i in range(len(df_xl)):
    franchise = df_xl['Franchise'][i]

    if df_xl['Validity'][i] != 'Valid':
        stat_dict[franchise] = "Invalid Token"
        continue

    access_token = df_xl['Access_Token'][i]
    company_id   = str(df_xl['Company_ID'][i])

    try:
        print(f"Pulling P&L for  {franchise}  ({company_id}) ...")

        df_pnl   = fetch_pnl_flat(access_token, company_id, PNL_START, PNL_END)
        df_heads = fetch_account_classifications(access_token, company_id)

        if df_pnl.empty:
            stat_dict[franchise] = "No Data"
            print(f"  → No P&L rows for {franchise}")
            continue

        # join AccountType / Classification onto each P&L line
        df_merged = df_pnl.merge(
            df_heads[["AccountId", "Classification", "AccountType", "AccountSubType"]],
            on="AccountId",
            how="left",
        )
        df_merged['franchise']  = franchise
        df_merged['company_id'] = company_id

        pnl_rows.append(df_merged)
        stat_dict[franchise] = "Success"
        print(f"  → {len(df_merged)} P&L rows for {franchise}")

    except Exception as e:
        print(f"  ERROR: {e}")
        stat_dict[franchise] = f"Error: {e}"

df_pnl_all = (
    pd.concat(pnl_rows, ignore_index=True)[PNL_COLS]
    if pnl_rows else pd.DataFrame(columns=PNL_COLS)
)

df_stat = pd.DataFrame(
    [{'Franchise': k, 'Status': v} for k, v in stat_dict.items()]
)

# ── Write to delta table ───────────────────────────────────────────────────────
DELTA_TABLE = "your_lakehouse.your_schema.qbo_pnl"   # update this

if not df_pnl_all.empty:
    spark_df = spark.createDataFrame(df_pnl_all)
    spark_df.write.format("delta").mode("overwrite").saveAsTable(DELTA_TABLE)
    print(f"Written {len(df_pnl_all)} rows to {DELTA_TABLE}")
else:
    print("Nothing to write — df_pnl_all is empty")
