"""
Google Sheets database handler for Unithread App.
No Streamlit dependency — pure Python with gspread.
"""

import gspread
from google.oauth2.service_account import Credentials
import json
import os
import time
import hashlib
from pathlib import Path
from datetime import datetime

# --- Configuration ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
SERVICE_ACCOUNT_FILE = Path(__file__).parent / "service_account.json"
SPREADSHEET_ID = "1VHeYLxhU-ItlS0snz-trqp9mEjk7FchC3zymbidYNE4"

# In-memory cache with TTL
_cache = {}
_cache_ttl = {}
CACHE_DURATION = 60  # seconds


class GoogleSheetsDB:
    """Manages all Google Sheets operations with retry logic and caching."""

    def __init__(self):
        self.client = None
        self.sheet = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Google using service account (file or env var)."""
        gcp_json = os.environ.get("GCP_SERVICE_ACCOUNT")
        if gcp_json:
            # Production: read from environment variable (JSON string)
            import tempfile
            info = json.loads(gcp_json)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            # Local dev: read from file
            creds = Credentials.from_service_account_file(
                str(SERVICE_ACCOUNT_FILE), scopes=SCOPES
            )
        self.client = gspread.authorize(creds)
        self.sheet = self.client.open_by_key(SPREADSHEET_ID)

    def _retry(self, func, max_retries=3):
        """Execute a function with retry logic for transient errors."""
        last_exc = None
        for attempt in range(max_retries):
            try:
                return func()
            except gspread.exceptions.APIError as e:
                last_exc = e
                status = e.response.status_code if hasattr(e, 'response') else 0
                if status in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
            except Exception as e:
                last_exc = e
                error_msg = str(e)
                retryable = any(t in error_msg for t in [
                    "Connection aborted", "RemoteDisconnected",
                    "timed out", "Transport endpoint"
                ])
                if retryable and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
        raise last_exc

    def _get_worksheet(self, name):
        """Get or create a worksheet by name."""
        try:
            return self._retry(lambda: self.sheet.worksheet(name))
        except gspread.WorksheetNotFound:
            return self._retry(
                lambda: self.sheet.add_worksheet(title=name, rows=1000, cols=26)
            )

    def _invalidate_cache(self, sheet_name):
        """Remove cached data for a worksheet."""
        _cache.pop(sheet_name, None)
        _cache_ttl.pop(sheet_name, None)

    def load_data(self, sheet_name):
        """Load all rows from a worksheet as list of dicts. Cached."""
        now = time.time()
        if sheet_name in _cache and now - _cache_ttl.get(sheet_name, 0) < CACHE_DURATION:
            return _cache[sheet_name]

        ws = self._get_worksheet(sheet_name)
        try:
            data = self._retry(lambda: ws.get_all_records())
        except Exception:
            data = []

        _cache[sheet_name] = data
        _cache_ttl[sheet_name] = now
        return data

    def save_data(self, sheet_name, data_list):
        """Overwrite a worksheet with a list of dicts."""
        self._invalidate_cache(sheet_name)
        ws = self._get_worksheet(sheet_name)

        if not data_list:
            self._retry(lambda: ws.clear())
            return

        # Build header from all keys across all rows
        headers = []
        for row in data_list:
            for key in row.keys():
                if key not in headers:
                    headers.append(key)

        rows = [headers]
        for item in data_list:
            row = []
            for h in headers:
                val = item.get(h, "")
                # Convert non-string types for sheets
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                elif val is None:
                    val = ""
                row.append(val)
            rows.append(row)

        self._retry(lambda: ws.clear())
        self._retry(lambda: ws.update(rows, value_input_option='USER_ENTERED'))

    def append_row(self, sheet_name, row_dict):
        """Append a single row to a worksheet."""
        self._invalidate_cache(sheet_name)
        ws = self._get_worksheet(sheet_name)

        existing = self._retry(lambda: ws.row_values(1))
        if not existing:
            # Empty sheet — write headers first
            headers = list(row_dict.keys())
            self._retry(lambda: ws.append_row(headers, value_input_option='USER_ENTERED'))
            values = list(row_dict.values())
        else:
            headers = existing
            values = []
            for h in headers:
                val = row_dict.get(h, "")
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                elif val is None:
                    val = ""
                values.append(val)

        # Convert any remaining complex types
        clean_values = []
        for v in values:
            if isinstance(v, (dict, list)):
                clean_values.append(json.dumps(v, ensure_ascii=False))
            elif v is None:
                clean_values.append("")
            else:
                clean_values.append(v)

        self._retry(lambda: ws.append_row(clean_values, value_input_option='USER_ENTERED'))

    def delete_rows_by_field(self, sheet_name, field, value):
        """Delete all rows where field == value."""
        data = self.load_data(sheet_name)
        filtered = [row for row in data if str(row.get(field, "")) != str(value)]
        self.save_data(sheet_name, filtered)

    def update_rows_by_field(self, sheet_name, field, value, updates):
        """Update all rows where field == value with the given dict of updates."""
        data = self.load_data(sheet_name)
        for row in data:
            if str(row.get(field, "")) == str(value):
                row.update(updates)
        self.save_data(sheet_name, data)

    def clear_cache(self):
        """Clear all cached data."""
        _cache.clear()
        _cache_ttl.clear()


# --- Initialize default admin user if needed ---
def initialize_database(db):
    """Create default admin user if users sheet is empty."""
    users = db.load_data("users")
    if not users:
        default_admin = {
            "username": "Viktor",
            "password_hash": hashlib.sha256("Admin".encode()).hexdigest(),
            "role": "admin",
            "permissions": json.dumps([
                "access_settings", "access_reports",
                "create_chat", "archive_chat"
            ], ensure_ascii=False),
        }
        db.save_data("users", [default_admin])
        print("✅ Default admin user 'Viktor' created (password: Admin)")


# Singleton
db = GoogleSheetsDB()
initialize_database(db)
