from datetime import date

import pandas as pd

from config import (
    MONTHLY_SHEET, RATES_SHEET, ANALYSIS_SHEET,
    ACCOUNT_ANALYSIS_SHEET, ACCOUNT_PKR_SHEET, INFLATION_RANKINGS_SHEET,
    TRANSACTIONS_SHEET,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_add_sheet(sheets_service, spreadsheet_id, title) -> int:
    meta = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in meta["sheets"]:
        if sheet["properties"]["title"] == title:
            return sheet["properties"]["sheetId"]

    resp = sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
    ).execute()
    return resp["replies"][0]["addSheet"]["properties"]["sheetId"]


def _existing_chart_ids(sheets_service, spreadsheet_id, sheet_id) -> list:
    meta = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in meta["sheets"]:
        if sheet["properties"]["sheetId"] == sheet_id:
            return [c["chartId"] for c in sheet.get("charts", [])]
    return []


def _clear_charts(sheets_service, spreadsheet_id, sheet_id):
    old_charts = _existing_chart_ids(sheets_service, spreadsheet_id, sheet_id)
    if old_charts:
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [
                {"deleteEmbeddedObject": {"objectId": cid}} for cid in old_charts
            ]},
        ).execute()


# ── Market Rates ──────────────────────────────────────────────────────────────

def load_historical_rates(sheets_service, spreadsheet_id) -> dict:
    """Reads the Market Rates sheet and returns {YYYY-MM: {gold, usd, gbp, cpi}}."""
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{RATES_SHEET}!A:E",
    ).execute()
    rows  = result.get("values", [])
    rates = {}
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        try:
            period = row[0][:7]
            gold   = float(row[1]) if len(row) > 1 and row[1] else None
            usd    = float(row[2]) if len(row) > 2 and row[2] else None
            gbp    = float(row[3]) if len(row) > 3 and row[3] else None
            cpi    = float(row[4]) if len(row) > 4 and row[4] else None
            if any(v is not None for v in (gold, usd, gbp, cpi)):
                rates[period] = {"gold": gold, "usd": usd, "gbp": gbp, "cpi": cpi}
        except (ValueError, IndexError):
            continue
    return rates


def upsert_market_rates(sheets_service, spreadsheet_id, prices: dict, cpi=""):
    _get_or_add_sheet(sheets_service, spreadsheet_id, RATES_SHEET)

    today_str = date.today().isoformat()
    headers   = ["Date", "Gold (PKR/g)", "USD-PKR", "GBP-PKR", "CPI"]
    row       = [today_str, prices["gold"], prices["usd"], prices["gbp"], cpi]

    result   = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{RATES_SHEET}!A:E",
    ).execute()
    existing = result.get("values", [])

    if not existing:
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{RATES_SHEET}!A1",
            valueInputOption="RAW",
            body={"values": [headers, row]},
        ).execute()
        print(f"  Market Rates: initialized with today's rates.")
        return

    today_row_num = next(
        (i + 2 for i, r in enumerate(existing[1:]) if r and r[0] == today_str),
        None,
    )

    if today_row_num:
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{RATES_SHEET}!A{today_row_num}",
            valueInputOption="RAW",
            body={"values": [row]},
        ).execute()
        print(f"  Market Rates: updated row {today_row_num} for {today_str}.")
    else:
        sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{RATES_SHEET}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
        print(f"  Market Rates: appended row for {today_str}.")


# ── Monthly Balances ──────────────────────────────────────────────────────────

def write_monthly_sheet(sheets_service, spreadsheet_id, df: pd.DataFrame):
    sheet_id = _get_or_add_sheet(sheets_service, spreadsheet_id, MONTHLY_SHEET)
    _clear_charts(sheets_service, spreadsheet_id, sheet_id)

    sheets_service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"{MONTHLY_SHEET}!A:Z",
    ).execute()

    values = [list(df.columns)] + [
        [v if v != "" else "" for v in row]
        for row in df.itertuples(index=False)
    ]
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{MONTHLY_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()

    print(
        f"  Monthly Balances: {len(df)} rows "
        f"({df['Month'].nunique()} months x {df['Account'].nunique()} accounts)."
    )


# ── Analysis ──────────────────────────────────────────────────────────────────

def write_analysis_sheet(sheets_service, spreadsheet_id, summary: pd.DataFrame):
    """
    Writes summary metrics and 2 charts:
      Chart 1 — Net Worth in PKR (absolute)
      Chart 2 — PKR / USD / Gold / Real indexed to 100 (trend comparison)
    """
    sheet_id = _get_or_add_sheet(sheets_service, spreadsheet_id, ANALYSIS_SHEET)
    num_rows = len(summary) + 1
    _clear_charts(sheets_service, spreadsheet_id, sheet_id)

    sheets_service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"{ANALYSIS_SHEET}!A:Z",
    ).execute()

    data_rows = [[("" if pd.isna(v) else v) for v in row] for row in summary.itertuples(index=False)]
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{ANALYSIS_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": [list(summary.columns)] + data_rows},
    ).execute()

    # Col indices (0-based):
    #   A=0 Month  B=1 PKR  C=2 USD  D=3 Gold  E=4 Real Net Worth (PKR)
    #   F=5 PKR Index  G=6 USD Index  H=7 Gold Index  I=8 Real PKR Index
    def data_src(col_start, col_end):
        return {
            "sourceRange": {
                "sources": [{
                    "sheetId":          sheet_id,
                    "startRowIndex":    0,
                    "endRowIndex":      num_rows,
                    "startColumnIndex": col_start,
                    "endColumnIndex":   col_end,
                }]
            }
        }

    def make_chart(title, y_label, series_cols, chart_type, anchor_row):
        return {
            "addChart": {
                "chart": {
                    "spec": {
                        "title": title,
                        "basicChart": {
                            "chartType":      chart_type,
                            "legendPosition": "BOTTOM_LEGEND",
                            "axis": [
                                {"position": "BOTTOM_AXIS", "title": "Month"},
                                {"position": "LEFT_AXIS",   "title": y_label},
                            ],
                            "domains": [{"domain": data_src(0, 1)}],
                            "series": [
                                {"series": data_src(col, col + 1), "targetAxis": "LEFT_AXIS"}
                                for col in series_cols
                            ],
                            "headerCount": 1,
                        },
                    },
                    "position": {
                        "overlayPosition": {
                            "anchorCell": {
                                "sheetId":     sheet_id,
                                "rowIndex":    anchor_row,
                                "columnIndex": 0,
                            },
                            "widthPixels":  700,
                            "heightPixels": 380,
                        }
                    },
                }
            }
        }

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [
            make_chart("Net Worth (PKR)", "PKR", [1], "LINE", 0),
            make_chart("Value Trend (Indexed, Base = 100)", "Index", [5, 6, 7, 8], "LINE", 21),
        ]},
    ).execute()

    print(f"  Analysis: {len(summary)} months of data + 2 charts.")


# ── Account Analysis ──────────────────────────────────────────────────────────

def write_account_analysis_sheet(
    sheets_service, spreadsheet_id, acct_df: pd.DataFrame, active_accounts: list
):
    """
    Per-account indexed data (rebased to 100 at first active month) with one
    chart per account showing PKR / USD / Gold / Real PKR lines.
    """
    sheet_id = _get_or_add_sheet(sheets_service, spreadsheet_id, ACCOUNT_ANALYSIS_SHEET)
    n_months = len(acct_df)
    num_rows = n_months + 1
    _clear_charts(sheets_service, spreadsheet_id, sheet_id)

    sheets_service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"{ACCOUNT_ANALYSIS_SHEET}!A:ZZ",
    ).execute()

    data_rows = [
        [("" if (v is None or (isinstance(v, float) and pd.isna(v))) else v) for v in row]
        for row in acct_df.itertuples(index=False)
    ]
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{ACCOUNT_ANALYSIS_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": [list(acct_df.columns)] + data_rows},
    ).execute()

    def _src(col_s, col_e):
        return {
            "sourceRange": {
                "sources": [{
                    "sheetId":          sheet_id,
                    "startRowIndex":    0,
                    "endRowIndex":      num_rows,
                    "startColumnIndex": col_s,
                    "endColumnIndex":   col_e,
                }]
            }
        }

    charts_start_row = n_months + 3
    chart_requests   = []

    for i, name in enumerate(active_accounts):
        cb = 4 * i + 1
        chart_requests.append({
            "addChart": {
                "chart": {
                    "spec": {
                        "title": name,
                        "basicChart": {
                            "chartType":      "LINE",
                            "legendPosition": "BOTTOM_LEGEND",
                            "axis": [
                                {"position": "BOTTOM_AXIS", "title": "Month"},
                                {"position": "LEFT_AXIS",   "title": "Index (Base=100)"},
                            ],
                            "domains": [{"domain": _src(0, 1)}],
                            "series": [
                                {"series": _src(cb,     cb + 1), "targetAxis": "LEFT_AXIS"},
                                {"series": _src(cb + 1, cb + 2), "targetAxis": "LEFT_AXIS"},
                                {"series": _src(cb + 2, cb + 3), "targetAxis": "LEFT_AXIS"},
                                {"series": _src(cb + 3, cb + 4), "targetAxis": "LEFT_AXIS"},
                            ],
                            "headerCount": 1,
                        },
                    },
                    "position": {
                        "overlayPosition": {
                            "anchorCell": {
                                "sheetId":     sheet_id,
                                "rowIndex":    charts_start_row + (i // 2) * 21,
                                "columnIndex": (i % 2) * 9,
                            },
                            "widthPixels":  700,
                            "heightPixels": 380,
                        }
                    },
                }
            }
        })

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": chart_requests},
    ).execute()

    print(
        f"  Account Analysis: {len(active_accounts)} accounts x {n_months} months"
        f" + {len(active_accounts)} charts."
    )


# ── Account Values (PKR) ──────────────────────────────────────────────────────

def write_account_pkr_sheet(
    sheets_service, spreadsheet_id, acct_df: pd.DataFrame, active_accounts: list
):
    """
    Same layout as Account Analysis but with raw PKR values. Each chart shows
    PKR (nominal) / USD in PKR / Gold in PKR / Real PKR on a common PKR y-axis.
    """
    sheet_id = _get_or_add_sheet(sheets_service, spreadsheet_id, ACCOUNT_PKR_SHEET)
    n_months = len(acct_df)
    num_rows = n_months + 1
    _clear_charts(sheets_service, spreadsheet_id, sheet_id)

    sheets_service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"{ACCOUNT_PKR_SHEET}!A:ZZ",
    ).execute()

    data_rows = [
        [("" if (v is None or (isinstance(v, float) and pd.isna(v))) else v) for v in row]
        for row in acct_df.itertuples(index=False)
    ]
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{ACCOUNT_PKR_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": [list(acct_df.columns)] + data_rows},
    ).execute()

    def _src(col_s, col_e):
        return {
            "sourceRange": {
                "sources": [{
                    "sheetId":          sheet_id,
                    "startRowIndex":    0,
                    "endRowIndex":      num_rows,
                    "startColumnIndex": col_s,
                    "endColumnIndex":   col_e,
                }]
            }
        }

    charts_start_row = n_months + 3
    chart_requests   = []

    for i, name in enumerate(active_accounts):
        cb = 4 * i + 1
        chart_requests.append({
            "addChart": {
                "chart": {
                    "spec": {
                        "title": name,
                        "basicChart": {
                            "chartType":      "LINE",
                            "legendPosition": "BOTTOM_LEGEND",
                            "axis": [
                                {"position": "BOTTOM_AXIS", "title": "Month"},
                                {"position": "LEFT_AXIS",   "title": "PKR"},
                            ],
                            "domains": [{"domain": _src(0, 1)}],
                            "series": [
                                {"series": _src(cb,     cb + 1), "targetAxis": "LEFT_AXIS"},
                                {"series": _src(cb + 1, cb + 2), "targetAxis": "LEFT_AXIS"},
                                {"series": _src(cb + 2, cb + 3), "targetAxis": "LEFT_AXIS"},
                                {"series": _src(cb + 3, cb + 4), "targetAxis": "LEFT_AXIS"},
                            ],
                            "headerCount": 1,
                        },
                    },
                    "position": {
                        "overlayPosition": {
                            "anchorCell": {
                                "sheetId":     sheet_id,
                                "rowIndex":    charts_start_row + (i // 2) * 21,
                                "columnIndex": (i % 2) * 9,
                            },
                            "widthPixels":  700,
                            "heightPixels": 380,
                        }
                    },
                }
            }
        })

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": chart_requests},
    ).execute()

    print(
        f"  Account Values: {len(active_accounts)} accounts x {n_months} months"
        f" + {len(active_accounts)} charts."
    )


# ── Inflation Rankings ────────────────────────────────────────────────────────

def write_inflation_rankings_sheet(sheets_service, spreadsheet_id, rankings_df: pd.DataFrame):
    """
    Writes the Inflation Rankings sheet.
    Color shading (green/yellow/red) applied to every Beat column.
    Header row and TOTAL NET WORTH row are bolded.
    """
    sheet_id = _get_or_add_sheet(sheets_service, spreadsheet_id, INFLATION_RANKINGS_SHEET)

    # Delete existing conditional format rules to prevent accumulation across runs
    meta = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet_meta in meta["sheets"]:
        if sheet_meta["properties"]["sheetId"] == sheet_id:
            n_rules = len(sheet_meta.get("conditionalFormats", []))
            if n_rules:
                sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"requests": [
                        {"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": i}}
                        for i in range(n_rules - 1, -1, -1)
                    ]},
                ).execute()
            break

    sheets_service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id, range=f"{INFLATION_RANKINGS_SHEET}!A:Z",
    ).execute()

    values = [list(rankings_df.columns)] + [
        [v if v != "" else "" for v in row]
        for row in rankings_df.itertuples(index=False)
    ]
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{INFLATION_RANKINGS_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()

    cols      = list(rankings_df.columns)
    n_cols    = len(cols)
    n_data    = len(rankings_df)
    total_idx = n_data   # 0-based row index of TOTAL NET WORTH (header = row 0)

    # Apply color shading to the contiguous block of all "Beat" columns
    beat_indices = [i for i, c in enumerate(cols) if "Beat" in c]
    beat_start   = beat_indices[0]
    beat_end     = beat_indices[-1] + 1   # exclusive

    GREEN  = {"red": 0.714, "green": 0.843, "blue": 0.659}
    YELLOW = {"red": 1.0,   "green": 0.898, "blue": 0.6}
    RED    = {"red": 0.918, "green": 0.6,   "blue": 0.6}

    def cond_fmt(condition_type, vals, bg_color, idx):
        return {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId":          sheet_id,
                        "startRowIndex":    1,
                        "endRowIndex":      n_data + 1,
                        "startColumnIndex": beat_start,
                        "endColumnIndex":   beat_end,
                    }],
                    "booleanRule": {
                        "condition": {
                            "type":   condition_type,
                            "values": [{"userEnteredValue": v} for v in vals],
                        },
                        "format": {"backgroundColor": bg_color},
                    },
                },
                "index": idx,
            }
        }

    def bold_row(row_start, row_end):
        return {
            "repeatCell": {
                "range": {
                    "sheetId":          sheet_id,
                    "startRowIndex":    row_start,
                    "endRowIndex":      row_end,
                    "startColumnIndex": 0,
                    "endColumnIndex":   n_cols,
                },
                "cell":   {"userEnteredFormat": {"textFormat": {"bold": True}}},
                "fields": "userEnteredFormat.textFormat.bold",
            }
        }

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [
            cond_fmt("NUMBER_GREATER", ["1"],         GREEN,  0),
            cond_fmt("NUMBER_BETWEEN", ["0.95", "1"], YELLOW, 1),
            cond_fmt("NUMBER_LESS",    ["0.95"],       RED,    2),
            bold_row(0, 1),                        # header
            bold_row(total_idx, total_idx + 1),    # TOTAL NET WORTH
        ]},
    ).execute()

    print(
        f"  Inflation Rankings: {n_data - 1} accounts + total row, "
        f"{len(beat_indices)} beat columns, color shading applied."
    )


# ── Transactions ──────────────────────────────────────────────────────────────

def write_transactions_sheet(sheets_service, spreadsheet_id, tx, accounts):
    """
    Writes every active transaction to a Transactions tab, sorted newest first.
    Columns: Date | Account | Type | Amount (PKR) | Native Amount | Notes
    Useful for auditing the cost-basis and period-beat calculations.
    """
    TYPE_LABELS = {2: "Opening", 3: "Expense", 4: "Income", 5: "Transfer"}

    acct_name = accounts.set_index("accountsTableID")["accountName"].to_dict()
    acct_curr = accounts.set_index("accountsTableID")["accountCurrency"].to_dict()

    rows = []
    for _, r in tx.iterrows():
        currency = acct_curr.get(r["accountID"], "PKR")
        native   = ""
        if currency != "PKR" and r["conversionRateNew"] and r["conversionRateNew"] != 0:
            native = round(r["amount_pkr"] * r["conversionRateNew"], 4)
        rows.append([
            r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else str(r["date"])[:10],
            acct_name.get(r["accountID"], str(r["accountID"])),
            TYPE_LABELS.get(int(r["transactionTypeID"]) if pd.notna(r["transactionTypeID"]) else 0, "Unknown"),
            round(r["amount_pkr"], 2),
            native,
            str(r["notes"]) if pd.notna(r["notes"]) else "",
        ])

    rows.sort(key=lambda x: x[0], reverse=True)   # newest first
    headers = ["Date", "Account", "Type", "Amount (PKR)", "Native Amount", "Notes"]

    sheet_id = _get_or_add_sheet(sheets_service, spreadsheet_id, TRANSACTIONS_SHEET)
    sheets_service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id, range=f"{TRANSACTIONS_SHEET}!A:F",
    ).execute()
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{TRANSACTIONS_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": [headers] + rows},
    ).execute()

    # Bold header row
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0, "endRowIndex": 1,
                    "startColumnIndex": 0, "endColumnIndex": 6,
                },
                "cell":   {"userEnteredFormat": {"textFormat": {"bold": True}}},
                "fields": "userEnteredFormat.textFormat.bold",
            }
        }]},
    ).execute()

    print(f"  Transactions: {len(rows)} rows written.")
