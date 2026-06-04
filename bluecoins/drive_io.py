import io
import re
import tempfile
from datetime import datetime
from pathlib import Path

from googleapiclient.http import MediaIoBaseDownload

from config import DRIVE_FOLDER_ID, QUICK_SYNC_FOLDER_ID, SHEET_TITLE
from services import get_service_account_email


def parse_filename_timestamp(name: str):
    m = re.search(r"Bluecoins_(\d{4}-\d{2}-\d{2}_\d{2}_\d{2}_\d{2})", name)
    return datetime.strptime(m.group(1), "%Y-%m-%d_%H_%M_%S") if m else datetime.min


def _download_fydb(drive_service, file_id: str) -> Path:
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, drive_service.files().get_media(fileId=file_id))
    done = False
    while not done:
        status, done = downloader.next_chunk()
        print(f"  {int(status.progress() * 100)}%", end="\r")
    print()
    tmp = tempfile.NamedTemporaryFile(suffix=".fydb", delete=False)
    tmp.write(buf.getvalue())
    tmp.close()
    return Path(tmp.name)


def find_latest_fydb(drive_service) -> dict | None:
    """Newest timestamped full export from the main folder (by filename timestamp)."""
    query = "name contains 'Bluecoins' and name contains '.fydb' and trashed = false"
    if DRIVE_FOLDER_ID:
        query += f" and '{DRIVE_FOLDER_ID}' in parents"

    results = drive_service.files().list(
        q=query, fields="files(id, name, modifiedTime)", pageSize=20,
    ).execute()

    files = results.get("files", [])
    if not files:
        return None

    files.sort(key=lambda f: parse_filename_timestamp(f["name"]), reverse=True)

    print(f"Found {len(files)} Bluecoins file(s) on Drive:")
    for f in files:
        ts     = parse_filename_timestamp(f["name"])
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if ts != datetime.min else "unknown"
        print(f"  {f['name']}  ({ts_str})")

    return files[0]


def download_latest_fydb(drive_service) -> Path:
    latest = find_latest_fydb(drive_service)
    if not latest:
        raise FileNotFoundError(
            "No Bluecoins .fydb files found.\n"
            f"Share the Drive folder with: {get_service_account_email()}"
        )
    print(f"Using: {latest['name']}")
    return _download_fydb(drive_service, latest["id"])


def find_quick_sync_files(drive_service) -> list:
    """
    Bluecoins Quick Sync overwrites a single fixed-name file `bluecoins.fydb`
    (no timestamp in the name) which usually holds the freshest data.

    Prefer the configured QUICK_SYNC_FOLDER_ID; if that secret is unset, fall back
    to locating `bluecoins.fydb` anywhere the service account can see it, so a
    missing folder-id never silently drops the most recent transactions.
    Sorted newest-first by modifiedTime (filename carries no timestamp).
    """
    if QUICK_SYNC_FOLDER_ID:
        query = (
            "name contains '.fydb' and trashed = false "
            f"and '{QUICK_SYNC_FOLDER_ID}' in parents"
        )
    else:
        query = "name = 'bluecoins.fydb' and trashed = false"

    results = drive_service.files().list(
        q=query, fields="files(id, name, modifiedTime)", pageSize=50,
    ).execute()
    files = results.get("files", [])
    files.sort(key=lambda f: f.get("modifiedTime", ""), reverse=True)
    return files


def find_spreadsheet(drive_service) -> str:
    query = (
        f"name='{SHEET_TITLE}' "
        "and mimeType='application/vnd.google-apps.spreadsheet' "
        "and trashed=false"
    )
    if DRIVE_FOLDER_ID:
        query += f" and '{DRIVE_FOLDER_ID}' in parents"

    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files   = results.get("files", [])
    if not files:
        raise FileNotFoundError(
            f"Google Sheet '{SHEET_TITLE}' not found.\n"
            f"Create it and share with: {get_service_account_email()}"
        )
    return files[0]["id"]
