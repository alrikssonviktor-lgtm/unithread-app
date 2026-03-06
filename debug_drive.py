import os
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# Konfiguration
SERVICE_ACCOUNT_FILE = "service_account.json"
FOLDER_ID = "1JLBR9p2NW1AuXvDZF7gbb5yP7RUVpUQV"  # ID från din db_handler.py
SCOPES = ["https://www.googleapis.com/auth/drive"]

print("--- STARTAR DIAGNOS ---")

# 1. Kontrollera att nyckelfilen finns
if not os.path.exists(SERVICE_ACCOUNT_FILE):
    print(f"❌ FEL: Filen {SERVICE_ACCOUNT_FILE} saknas.")
    exit()
print("✅ Nyckelfil hittad.")

try:
    # 2. Försök autentisera
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    print("✅ Autentisering lyckades.")
    
    # 3. Kolla vem roboten är (email)
    about = service.about().get(fields="user").execute()
    email = about['user']['emailAddress']
    print(f"🤖 Robotens email: {email}")

    # 4. Försök hitta mappen
    try:
        folder = service.files().get(fileId=FOLDER_ID, fields="name, capabilities").execute()
        print(f"✅ Mappen hittad: '{folder.get('name')}'")
        
        can_add = folder.get('capabilities', {}).get('canAddChildren')
        print(f"   Kan lägga till filer? {'JA' if can_add else 'NEJ (Saknar rättigheter!)'}")
        
    except Exception as e:
        print(f"❌ FEL: Kunde inte hitta mappen {FOLDER_ID}.")
        print(f"   Orsak: {e}")
        print("   TIPS: Kontrollera att mappen finns och är delad med robotens email.")
        exit()

    # 5. Försök ladda upp en testfil
    print("\nFörsöker ladda upp en testfil...")
    file_metadata = {
        'name': 'test_upload_debug.txt',
        'parents': [FOLDER_ID]
    }
    media = MediaIoBaseUpload(io.BytesIO(b"Detta ar ett test"), mimetype='text/plain')
    
    try:
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        print(f"✅ LYCKADES! Fil skapad med ID: {file.get('id')}")
        
        # Städa upp (ta bort testfilen)
        service.files().delete(fileId=file.get('id')).execute()
        print("   (Testfilen städades bort igen)")
        
    except Exception as e:
        print(f"❌ UPPPLADDNING MISSLYCKADES.")
        print(f"   Felmeddelande: {e}")
        
except Exception as e:
    print(f"❌ Oväntat fel: {e}")

print("\n--- DIAGNOS KLAR ---")