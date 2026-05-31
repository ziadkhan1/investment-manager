import os
from pathlib import Path


# ── Local .env loader (used when running on dev machine, ignored in CI) ───────
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())


# ── Credentials (file paths for local dev; JSON content for CI) ───────────────
# Local: set GOOGLE_DRIVE_CREDENTIALS_FILE / GOOGLE_SHEETS_CREDENTIALS_FILE in .env
# CI:    set GOOGLE_DRIVE_CREDENTIALS / GOOGLE_SHEETS_CREDENTIALS as repo secrets
DRIVE_CREDENTIALS_FILE  = os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE")
SHEETS_CREDENTIALS_FILE = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE")

# ── Drive ─────────────────────────────────────────────────────────────────────
DRIVE_FOLDER_ID      = os.getenv("DRIVE_FOLDER_ID")       or None
QUICK_SYNC_FOLDER_ID = os.getenv("QUICK_SYNC_FOLDER_ID")  or None
SHEET_TITLE          = os.environ["SHEET_TITLE"]

# ── Accounts ──────────────────────────────────────────────────────────────────
GOLD_ACCOUNT_ID = int(os.environ["GOLD_ACCOUNT_ID"])

# ── Sheet tab names ───────────────────────────────────────────────────────────
MONTHLY_SHEET          = "Monthly Balances"
RATES_SHEET            = "Market Rates"
ANALYSIS_SHEET         = "Analysis"
ACCOUNT_ANALYSIS_SHEET = "Account Analysis"
ACCOUNT_PKR_SHEET      = "Account Values"
INFLATION_RANKINGS_SHEET = "Inflation Rankings"
TRANSACTIONS_SHEET     = "Transactions"

# ── Pakistan annual CPI inflation rates (%). Source: SBP / PBS. ───────────────
PAKISTAN_ANNUAL_INFLATION = {
    2018: 3.9,  2019: 6.8,  2020: 10.7, 2021: 8.9,
    2022: 19.9, 2023: 29.2, 2024: 23.4, 2025: 8.5, 2026: 5.0,
}
