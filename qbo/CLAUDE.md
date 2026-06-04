# qbo — QuickBooks Online integration

## What this is
Pulls data from the **QuickBooks Online (QBO) REST API v3** and lands it in
**Azure Synapse / Microsoft Fabric** as Delta tables.

`qbo.py` is currently a **Fabric/Synapse notebook cell**, not the local CLI script
that `README.md` describes (the README is the older standalone-script variant —
treat `qbo.py` as the source of truth).

## qbo.py — current shape
- `fetch_account_classifications(access_token, company_id)` — queries the `Account`
  entity (`/query` endpoint) with `STARTPOSITION`/`MAXRESULTS 1000` pagination →
  `AccountId, Account, Classification, AccountType, AccountSubType`.
- `fetch_pnl_flat(access_token, company_id, start_date, end_date)` — calls
  `/reports/ProfitAndLoss` and **recursively walks** the nested `Rows.Row[]` section
  tree (flat `json_normalize` misses the section grouping) → one row per data line
  with `AccountId, Account, Section, Amount`.
- Multi-franchise loop reads a token table from Excel:
  `df_xl = pd.read_excel(output_path_xl, dtype=object)` with columns
  `Franchise, Validity, Access_Token, Company_ID`. Only `Validity == 'Valid'` rows run.
- Joins P&L lines to classifications on `AccountId`, tags `franchise`/`company_id`,
  concatenates, and writes to a Delta table via `spark.createDataFrame(...).write
  .format("delta").mode("overwrite").saveAsTable(DELTA_TABLE)`.

## Key QBO facts
- P&L report JSON has **no** account `Classification`/`AccountType` — those only exist
  on the `Account` entity, so they must be fetched separately and joined on `AccountId`
  (the P&L data rows carry it in `ColData[0].id`).
- `minorversion=75` on requests.

## Runtime notes
- `output_path_xl`, `spark`, `notebookutils`/`mssparkutils` are **provided by the
  Fabric/Synapse runtime** — IDE "not defined" warnings on these are expected.
- Before running: set `PNL_START` / `PNL_END` and `DELTA_TABLE`
  (`your_lakehouse.your_schema.<table>`).
