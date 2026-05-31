"""
Bluecoins Net Worth Calculator
- Downloads latest .fydb from Google Drive (main folder)
- Optionally merges incremental Quick Sync .fydb files
- Fetches live gold / USD / GBP prices and Pakistan CPI
- Computes month-end balance for every account across full transaction history
- Writes to Google Sheets:
    "Monthly Balances"  — one row per (month, account)
    "Market Rates"      — daily upsert of gold / FX rates
    "Analysis"          — aggregated net worth metrics + 2 embedded charts
    "Account Analysis"  — per-account indexed charts (base=100)
    "Account Values"    — per-account raw PKR charts
    "Inflation Rankings"— per-account inflation beat ratio with color shading
"""

import os
from datetime import date

from services import get_drive_service, get_sheets_service, get_service_account_email
from drive_io import download_latest_fydb, find_quick_sync_files, find_spreadsheet, _download_fydb
from prices import fetch_live_prices, fetch_pakistan_cpi_series
from db_queries import load_data
from calculations import (
    compute_monthly_balances,
    compute_summary,
    compute_account_indices,
    compute_account_pkr_values,
    compute_inflation_rankings,
)
from sheets_io import (
    load_historical_rates,
    write_monthly_sheet,
    write_analysis_sheet,
    write_account_analysis_sheet,
    write_account_pkr_sheet,
    write_inflation_rankings_sheet,
    write_transactions_sheet,
    upsert_market_rates,
)


def main():
    print("=== Bluecoins Net Worth Calculator ===\n")
    print("Drive service account:", get_service_account_email())

    print("\n[1/4] Connecting to Google Drive...")
    drive_service  = get_drive_service()
    sheets_service = get_sheets_service()
    spreadsheet_id = find_spreadsheet(drive_service)

    db_path  = download_latest_fydb(drive_service)
    db_paths = [db_path]

    qs_files = find_quick_sync_files(drive_service)
    if qs_files:
        print(f"  Quick sync: {len(qs_files)} file(s) found, merging latest...")
        qs_path = _download_fydb(drive_service, qs_files[0]["id"])
        db_paths.append(qs_path)
        print(f"  Merged: {qs_files[0]['name']}")

    try:
        print("\n[2/4] Fetching live prices...")
        prices = fetch_live_prices()

        print("\n[3/4] Processing database...")
        hist_rates  = load_historical_rates(sheets_service, spreadsheet_id)
        fetched_cpi = fetch_pakistan_cpi_series()
        for month, cpi_val in fetched_cpi.items():
            if month not in hist_rates:
                hist_rates[month] = {}
            if not hist_rates[month].get("cpi"):
                hist_rates[month]["cpi"] = cpi_val
        print(f"  Historical rates loaded: {len(hist_rates)} months")

        tx, accounts = load_data(db_paths)
        print(f"  Loaded {len(tx):,} transactions across {len(accounts)} accounts")
        if len(tx) < 500:
            print(f"  WARNING: only {len(tx)} transactions — Drive file may be an older export.")

        monthly  = compute_monthly_balances(tx, accounts, prices, hist_rates)
        summary  = compute_summary(monthly)
        acct_analysis, active_accounts = compute_account_indices(monthly)
        acct_pkr, active_pkr           = compute_account_pkr_values(monthly, prices)
        rankings = compute_inflation_rankings(monthly, tx, accounts, hist_rates)

        cur = summary.iloc[-1]
        print(f"\n  Net Worth {cur['Month']}:")
        print(f"    PKR  : {cur['Net Worth (PKR)']:>15,.2f}")
        print(f"    USD  : {cur['Net Worth (USD)']:>15,.2f}")
        print(f"    Gold : {cur['Net Worth (Gold g)']:>15,.4f}g")

        print("\n[4/4] Updating Google Sheet...")
        write_monthly_sheet(sheets_service, spreadsheet_id, monthly)
        write_analysis_sheet(sheets_service, spreadsheet_id, summary)
        write_account_analysis_sheet(sheets_service, spreadsheet_id, acct_analysis, active_accounts)
        write_account_pkr_sheet(sheets_service, spreadsheet_id, acct_pkr, active_pkr)
        write_inflation_rankings_sheet(sheets_service, spreadsheet_id, rankings)
        write_transactions_sheet(sheets_service, spreadsheet_id, tx, accounts)
        today_cpi = fetched_cpi.get(date.today().strftime("%Y-%m"), "")
        upsert_market_rates(sheets_service, spreadsheet_id, prices, today_cpi)

        print(f"\nDone: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")

    finally:
        for p in db_paths:
            try:
                os.unlink(p)
            except Exception:
                pass


if __name__ == "__main__":
    main()
