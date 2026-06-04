"""
One-time backfill script: writes historical end-of-month market rates
(Gold PKR/g, USD-PKR, GBP-PKR, CPI) into the "Market Rates" Google Sheet tab.

FX + Gold: Yahoo Finance via yfinance (no API key required).
CPI:       World Bank FP.CPI.TOTL indicator (annual, interpolated monthly).

Run once:
    pip install yfinance
    python backfill_rates.py

Existing rows with manually entered values are preserved (existing rows win).
The sheet is rewritten in chronological order.
"""

import calendar
import requests
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ── Config ────────────────────────────────────────────────────────────────────
SECRETS_DIR             = Path(r"C:\Users\LENOVO\secrets")
DRIVE_CREDENTIALS_FILE  = SECRETS_DIR / "finance-497913-2e9089af7111.json"
SHEETS_CREDENTIALS_FILE = SECRETS_DIR / "finance-497913-5de8f23a9f2d.json"
SHEET_TITLE             = "finances"
RATES_SHEET             = "Market Rates"

GRAMS_PER_OZ    = 31.1035
BACKFILL_MONTHS = 30


# ── Google services ───────────────────────────────────────────────────────────

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        DRIVE_CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds)


def get_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        SHEETS_CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def find_spreadsheet(drive_service) -> str:
    results = drive_service.files().list(
        q=(
            f"name='{SHEET_TITLE}' "
            "and mimeType='application/vnd.google-apps.spreadsheet' "
            "and trashed=false"
        ),
        fields="files(id, name)",
    ).execute()
    files = results.get("files", [])
    if not files:
        raise FileNotFoundError(f"Google Sheet '{SHEET_TITLE}' not found.")
    return files[0]["id"]


# ── FX + Gold fetching (yfinance) ─────────────────────────────────────────────

def fetch_monthly_close(ticker: str, start: date, end: date) -> pd.Series:
    df = yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=(end + timedelta(days=10)).strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
    )
    if df.empty:
        print(f"    WARNING: no data returned for {ticker}")
        return pd.Series(dtype=float)
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.squeeze()
    return close.resample("ME").last().dropna()


def build_rate_table(start: date, end: date) -> pd.DataFrame:
    print(f"  USD/PKR  (USDPKR=X)  ...", end=" ", flush=True)
    usd = fetch_monthly_close("USDPKR=X", start, end)
    print(f"{len(usd)} months")

    print(f"  GBP/PKR  (GBPPKR=X)  ...", end=" ", flush=True)
    gbp = fetch_monthly_close("GBPPKR=X", start, end)
    print(f"{len(gbp)} months")

    print(f"  Gold USD/oz  (GC=F)  ...", end=" ", flush=True)
    gold_usd = fetch_monthly_close("GC=F", start, end)
    print(f"{len(gold_usd)} months")

    df = pd.DataFrame({"usd": usd, "gbp": gbp, "gold_usd": gold_usd})
    df["gold_pkr_g"] = (df["gold_usd"] * df["usd"] / GRAMS_PER_OZ).round(2)
    df["usd"]        = df["usd"].round(2)
    df["gbp"]        = df["gbp"].round(2)
    return df[["gold_pkr_g", "usd", "gbp"]]


# ── CPI fetching (World Bank) ─────────────────────────────────────────────────

def fetch_pakistan_cpi_series() -> dict:
    """
    Fetch Pakistan annual CPI (World Bank FP.CPI.TOTL, base 2010=100)
    and interpolate to monthly via compound growth.
    Returns {YYYY-MM: cpi_value}. Returns {} on failure.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    url     = (
        "https://api.worldbank.org/v2/country/PK/indicator/FP.CPI.TOTL"
        "?format=json&per_page=30&mrv=30"
    )
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        data = resp.json()
    except Exception as e:
        print(f"  Warning: could not fetch CPI ({e})")
        return {}

    if len(data) < 2 or not data[1]:
        return {}

    annual = {
        int(e["date"]): e["value"]
        for e in data[1]
        if e.get("value") is not None
    }
    if len(annual) < 2:
        return {}

    today        = date.today()
    sorted_years = sorted(annual.keys())
    last, prev   = sorted_years[-1], sorted_years[-2]
    tail_rate    = (annual[last] / annual[prev]) - 1

    result = {}
    for year in range(sorted_years[0], today.year + 1):
        for month in range(1, 13):
            if year == today.year and month > today.month:
                break
            month_key = f"{year}-{month:02d}"

            if year in annual and (year - 1) in annual:
                rate = (annual[year] / annual[year - 1]) - 1
                cpi  = annual[year - 1] * ((1 + rate) ** (month / 12))
            elif year > last:
                months_ahead = (year - last) * 12 + month
                cpi = annual[last] * ((1 + tail_rate) ** (months_ahead / 12))
            elif year in annual:
                cpi = annual[year]
            else:
                continue

            result[month_key] = round(cpi, 2)

    print(f"  CPI: {len(result)} months fetched (World Bank 2010=100)")
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Market Rates Backfill ===\n")

    today = date.today()

    total = today.year * 12 + today.month - BACKFILL_MONTHS
    start_year, start_month = divmod(total, 12)
    if start_month == 0:
        start_month = 12
        start_year -= 1
    fetch_start = date(start_year, start_month, 1)

    first_this_month = today.replace(day=1)
    fetch_end        = first_this_month - timedelta(days=1)

    print(f"Backfill range : {fetch_start.strftime('%Y-%m')} to {fetch_end.strftime('%Y-%m')}")
    print(f"Months targeted: {BACKFILL_MONTHS}\n")

    drive_service  = get_drive_service()
    sheets_service = get_sheets_service()
    spreadsheet_id = find_spreadsheet(drive_service)

    # Read existing sheet rows
    result        = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{RATES_SHEET}!A:E",
    ).execute()
    existing_rows = result.get("values", [])
    headers       = ["Date", "Gold (PKR/g)", "USD-PKR", "GBP-PKR", "CPI"]
    existing_data = {r[0]: r for r in existing_rows[1:] if r}
    print(f"Existing rows in sheet: {len(existing_data)}\n")

    # Fetch FX + Gold rates
    print("Fetching FX and gold rates from Yahoo Finance...")
    rates_df = build_rate_table(fetch_start, fetch_end)
    rates_df = rates_df[rates_df.index < pd.Timestamp(first_this_month)]

    # Fetch CPI
    print("\nFetching Pakistan CPI from World Bank...")
    cpi_series = fetch_pakistan_cpi_series()
    print()

    # Build new rows (FX + Gold + CPI)
    new_rows = {}
    for ts, row in rates_df.iterrows():
        d_str     = ts.date().isoformat()
        month_key = d_str[:7]
        new_rows[d_str] = [
            d_str,
            row["gold_pkr_g"] if not pd.isna(row["gold_pkr_g"]) else "",
            row["usd"]        if not pd.isna(row["usd"])        else "",
            row["gbp"]        if not pd.isna(row["gbp"])        else "",
            cpi_series.get(month_key, ""),
        ]

    # Smart merge:
    #   - FX / Gold columns: existing sheet values always win (preserves manual corrections)
    #   - CPI column: use whichever source has a non-empty value (fills historical blanks)
    merged    = {}
    all_keys  = set(list(new_rows) + list(existing_data))
    for d_str in all_keys:
        if d_str in existing_data and d_str in new_rows:
            e = existing_data[d_str] + [""] * (5 - len(existing_data[d_str]))
            n = new_rows[d_str]
            chosen_cpi = e[4] if e[4] else (n[4] if len(n) > 4 else "")
            merged[d_str] = e[:4] + [chosen_cpi]
        elif d_str in existing_data:
            e = existing_data[d_str]
            merged[d_str] = e + [""] * (5 - len(e))
        else:
            merged[d_str] = new_rows[d_str]

    today_str   = today.isoformat()
    sorted_rows = sorted(
        (r for r in merged.values() if r[0] <= today_str),
        key=lambda r: r[0],
    )

    added   = sum(1 for d in new_rows if d not in existing_data)
    skipped = len(new_rows) - added
    print(f"Fetched {len(new_rows)} months  |  New: {added}  |  Kept existing: {skipped}\n")

    sheets_service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"{RATES_SHEET}!A:E",
    ).execute()
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{RATES_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": [headers] + sorted_rows},
    ).execute()

    print(f"Sheet rewritten: {len(sorted_rows)} total rows (sorted by date).\n")
    print("Last 5 rows written:")
    for r in sorted_rows[-5:]:
        print(f"  {r[0]}  Gold={r[1]}  USD={r[2]}  GBP={r[3]}  CPI={r[4]}")


if __name__ == "__main__":
    main()
