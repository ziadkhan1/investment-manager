import re
import sqlite3
from pathlib import Path

import pandas as pd


def parse_grams(notes_series) -> float:
    total = 0.0
    for note in notes_series.dropna():
        m = re.search(r"([\d.]+)\s*g", str(note), re.IGNORECASE)
        if m:
            total += float(m.group(1))
    return total


def load_data(db_paths: list):
    """
    Load and merge transactions from one or more .fydb files.
    Deduplicates by transactionsTableID so quick-sync rows don't double-count.
    Accounts are loaded from the first DB that has a complete ACCOUNTSTABLE.
    """
    all_tx   = []
    accounts = None

    for db_path in db_paths:
        conn = sqlite3.connect(db_path)
        try:
            tx = pd.read_sql_query("""
                SELECT t.transactionsTableID,
                       t.accountID,
                       t.amount / 1000000.0 AS amount_pkr,
                       t.conversionRateNew,
                       t.transactionTypeID,
                       t.date,
                       t.notes
                FROM TRANSACTIONSTABLE t
                WHERE t.deletedTransaction = 6
                  AND (t.reminderTransaction IS NULL OR t.reminderTransaction != 9)
                ORDER BY t.date
            """, conn)
            all_tx.append(tx)
        except Exception as e:
            print(f"  Warning: could not read transactions from {Path(db_path).name}: {e}")

        if accounts is None:
            try:
                accounts = pd.read_sql_query("""
                    SELECT a.accountsTableID,
                           a.accountName,
                           at.accountTypeName,
                           ag.accountGroupName,
                           a.accountCurrency
                    FROM ACCOUNTSTABLE a
                    LEFT JOIN ACCOUNTTYPETABLE     at ON a.accountTypeID      = at.accountTypeTableID
                    LEFT JOIN ACCOUNTINGGROUPTABLE ag ON at.accountingGroupID = ag.accountingGroupTableID
                    WHERE a.accountsTableID > 0
                """, conn)
            except Exception:
                pass
        conn.close()

    if not all_tx:
        raise RuntimeError("No transactions could be loaded from any database.")

    merged = pd.concat(all_tx, ignore_index=True)
    merged = merged.drop_duplicates(subset="transactionsTableID", keep="last")
    merged["date"]   = pd.to_datetime(merged["date"], errors="coerce", format="mixed")
    merged           = merged.dropna(subset=["date"])
    merged["period"] = merged["date"].dt.to_period("M")
    return merged, accounts
