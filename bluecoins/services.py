import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build

import config


def _load_credentials(json_env_var: str, file_config_attr: str, scopes: list):
    """
    Load a Google service-account credential.
    Priority:
      1. Env var <json_env_var>  — full JSON content (used in CI / GitHub Actions)
      2. Config attr <file_config_attr> — path to a local JSON file (local dev)
    """
    json_content = os.getenv(json_env_var)
    if json_content:
        return service_account.Credentials.from_service_account_info(
            json.loads(json_content), scopes=scopes
        )

    file_path = getattr(config, file_config_attr, None)
    if file_path:
        return service_account.Credentials.from_service_account_file(
            str(file_path), scopes=scopes
        )

    raise EnvironmentError(
        f"No credentials found. Set env var '{json_env_var}' (JSON content) "
        f"or '{file_config_attr.replace('_FILE','')}_FILE' in your .env file."
    )


def get_drive_service():
    creds = _load_credentials(
        "GOOGLE_DRIVE_CREDENTIALS",
        "DRIVE_CREDENTIALS_FILE",
        ["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds)


def get_sheets_service():
    creds = _load_credentials(
        "GOOGLE_SHEETS_CREDENTIALS",
        "SHEETS_CREDENTIALS_FILE",
        ["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def get_service_account_email() -> str:
    try:
        json_content = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
        if json_content:
            return json.loads(json_content).get("client_email", "unknown")
        if config.DRIVE_CREDENTIALS_FILE:
            return json.loads(
                open(config.DRIVE_CREDENTIALS_FILE).read()
            ).get("client_email", "unknown")
    except Exception:
        pass
    return "unknown"
