# Claude Code Projects — Context

## Bluecoins Net Worth Workflow

### Source file
`Bluecoins_YYYY-MM-DD_HH_MM_SS.fydb` — exported from the Bluecoins Android app. It is a **SQLite database** (not a proprietary format).

### Key tables
| Table | Purpose |
|---|---|
| `TRANSACTIONSTABLE` | All transactions |
| `ACCOUNTSTABLE` | Accounts (bank, cash, investments, foreign, etc.) |
| `ACCOUNTTYPETABLE` | Maps `accountTypeID` → name + `accountingGroupID` |
| `ACCOUNTINGGROUPTABLE` | Group 1 = Assets, Group 2 = Liabilities |
| `TRANSACTIONTYPETABLE` | 2=New Account, 3=Expense, 4=Income, 5=Transfer |

### Filter for active transactions
```sql
WHERE deletedTransaction = 6          -- 6=active, 5=deleted
  AND (reminderTransaction IS NULL OR reminderTransaction != 9)
```

### Amount encoding
- Stored as `INTEGER`: divide by `1,000,000` to get real value.
- All amounts are stored in **PKR (base currency)**, even for foreign-currency accounts.
- `conversionRateNew` in each transaction = foreign-currency units per 1 PKR (e.g. 0.00267 GBP/PKR).

### Foreign currency balance (native amount)
```python
native_balance = sum(amount_pkr * tx.conversionRateNew)   # gives e.g. GBP
current_pkr    = native_balance * live_pkr_per_foreign     # convert at today's rate
```

### Gold account
- Account ID: `1777732763023`, name: **Gold**, type: Other Assets
- Weight is stored in the `notes` field of the Transfer transaction (e.g. `"2.5g"`).
- Value = grams × live 24k gold price (PKR/gram).

### Accounts as of 2026-05-30
| Account | Currency | Native balance |
|---|---|---|
| Askari | PKR | — |
| SC | PKR | — |
| HBL | PKR | — |
| Savings | PKR | — |
| Wallet | PKR | — |
| Easy Paisa | PKR | — |
| Savings GBP | GBP | ~750 GBP |
| Savings USD | USD | ~250 USD |
| MCF | PKR | investment |
| AMMF | PKR | investment |
| MIACF | PKR | investment |
| Gold | PKR | 2.5g (use live price) |
| Receivables | PKR | — |
| Payables | PKR | liability |

### Live price sources (fetch each run)
| Data | Source URL |
|---|---|
| Gold 24k PKR/gram | https://goldpricez.com/pk/gram |
| USD → PKR | https://wise.com/us/currency-converter/usd-to-pkr-rate |
| GBP → PKR | https://wise.com/us/currency-converter/gbp-to-pkr-rate |

### Google Drive integration (pending setup)
Goal: pull the latest `.fydb` from a Google Drive folder instead of the local folder.

**Setup steps (one-time):**
1. Go to https://console.cloud.google.com → create a project → enable Google Drive API
2. Create OAuth 2.0 credentials (Desktop app type) → download as `client_secret.json` into this folder
3. `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib`
4. Provide the Google Drive folder URL/ID

**Script to create:** `download_from_drive.py`
- Auth via OAuth2 (browser prompt on first run, then cached in `token.json`)
- Find latest `Bluecoins_*.fydb` in the specified Drive folder
- Download it locally, then hand off to `networth.py`

### Output scripts
| Script | Purpose |
|---|---|
| `export_to_excel.py` | Exports all DB tables to `Bluecoins_YYYY-MM-DD.xlsx` |
| `networth.py` | Calculates net worth with live rates, saves to `Bluecoins_NetWorth.xlsx` |
| `inspect_db.py` | Utility: lists tables, schemas, and sample data |
| `inspect_accounts.py` | Utility: debugs account/transaction data |
