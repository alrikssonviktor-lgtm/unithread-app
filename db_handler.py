import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import io
import time

# --- KONFIGURATION ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
SERVICE_ACCOUNT_FILE = "service_account.json"
SPREADSHEET_NAME = "Ekonomi_DB"
DRIVE_FOLDER_NAME = "Unithread_App_Data"  # Mappen vi skapade


class DBHandler:
    def __init__(self):
        self.creds = None
        self.client = None
        self.sheet = None
        self.drive_service = None
        self.drive_folder_id = None
        self._authenticate()

    def _authenticate(self):
        """Autentiserar mot Google API."""
        try:
            # 1. Försök ladda från Streamlit Secrets (Molnet)
            if "gcp_service_account" in st.secrets:
                self.creds = Credentials.from_service_account_info(
                    st.secrets["gcp_service_account"], scopes=SCOPES
                )
            # 2. Annars ladda från lokal fil (Lokal utveckling)
            else:
                self.creds = Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_FILE, scopes=SCOPES
                )

            self.client = gspread.authorize(self.creds)
            self.drive_service = build('drive', 'v3', credentials=self.creds)

            # Öppna kalkylarket
            try:
                self.sheet = self.client.open(SPREADSHEET_NAME)
            except gspread.SpreadsheetNotFound:
                st.error(
                    f"Kunde inte hitta kalkylarket '{SPREADSHEET_NAME}'. Har du delat det med roboten?")
                st.stop()

            # Hitta Drive-mappen
            self._find_drive_folder()

        except Exception as e:
            st.error(f"Autentiseringsfel: {str(e)}")
            st.stop()

    def _find_drive_folder(self):
        """Hittar ID för mappen där vi sparar filer."""
        query = f"name = '{DRIVE_FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        # Lägg till supportsAllDrives=True och includeItemsFromAllDrives=True för att hitta delade mappar
        results = self.drive_service.files().list(
            q=query,
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        files = results.get('files', [])

        if not files:
            # Om mappen inte hittas via API (kanske delad mapp?), sök bredare eller varna
            # För enkelhetens skull, om vi inte hittar den, varnar vi.
            # Man kan också hårdkoda IDt om det krånglar.
            st.warning(
                f"Kunde inte hitta mappen '{DRIVE_FOLDER_NAME}' via API. Filer kanske sparas i roten.")
            self.drive_folder_id = None
        else:
            self.drive_folder_id = files[0]['id']

    def _retry_api_call(self, func):
        """Kör en funktion med retry-logik för nätverksfel."""
        max_retries = 3
        last_exception = None

        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                error_msg = str(e)
                # Lista på fel som bör trigga retry
                retry_triggers = [
                    "Connection aborted",
                    "RemoteDisconnected",
                    "The read operation timed out",
                    "Transport endpoint is not connected",
                    "APIError",
                    "500", "502", "503", "504"
                ]

                should_retry = any(
                    trigger in error_msg for trigger in retry_triggers)

                if should_retry and attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                else:
                    raise last_exception

    def _get_worksheet(self, name):
        """Hämtar en flik, skapar den om den inte finns."""
        try:
            return self._retry_api_call(lambda: self.sheet.worksheet(name))
        except gspread.WorksheetNotFound:
            return self._retry_api_call(lambda: self.sheet.add_worksheet(title=name, rows=100, cols=20))

    def load_data(self, sheet_name):
        """Laddar data från en flik till en lista av dicts."""
        ws = self._get_worksheet(sheet_name)
        data = self._retry_api_call(lambda: ws.get_all_records())
        return data

    def save_data(self, sheet_name, data_list):
        """Sparar en lista av dicts till en flik (skriver över allt)."""
        if not data_list:
            return  # Inget att spara

        ws = self._get_worksheet(sheet_name)

        # Konvertera till DataFrame för enkel hantering av headers
        df = pd.DataFrame(data_list)

        # Rensa bladet
        self._retry_api_call(lambda: ws.clear())

        # Skriv headers och data
        self._retry_api_call(lambda: ws.update(
            [df.columns.values.tolist()] + df.values.tolist()))

    def append_row(self, sheet_name, row_dict):
        """Lägger till en rad i slutet av en flik."""
        ws = self._get_worksheet(sheet_name)

        # Om bladet är tomt, lägg till headers först
        if ws.row_count == 0 or not ws.row_values(1):
            self._retry_api_call(lambda: ws.append_row(list(row_dict.keys())))

        # Se till att ordningen matchar headers om de finns
        headers = self._retry_api_call(lambda: ws.row_values(1))
        if headers:
            row_values = [row_dict.get(h, "") for h in headers]
            self._retry_api_call(lambda: ws.append_row(row_values))
        else:
            # Fallback om inga headers fanns (borde hanterats ovan)
            self._retry_api_call(
                lambda: ws.append_row(list(row_dict.values())))

    def upload_file(self, file_obj, filename, folder_subpath=None):
        """Laddar upp en fil till Google Drive och returnerar ID/Länk."""

        # Metadata för filen
        file_metadata = {
            'name': filename,
            'parents': [self.drive_folder_id] if self.drive_folder_id else []
        }

        # Skapa media-objekt
        media = MediaIoBaseUpload(
            file_obj, mimetype='application/octet-stream', resumable=True)

        # Ladda upp
        # Lägg till supportsAllDrives=True för att stödja uppladdning till delade enheter
        file = self.drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webContentLink, webViewLink',
            supportsAllDrives=True
        ).execute()

        return file.get('webViewLink')  # Länk för att visa filen


# Singleton-instans
db = DBHandler()
