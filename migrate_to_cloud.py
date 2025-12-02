import json
import math
import pandas as pd
import numpy as np
from pathlib import Path
from db_handler import db
import streamlit as st

# Mocka st.error/warning eftersom vi kör detta som ett script
if not hasattr(st, "error"):
    st.error = print
if not hasattr(st, "warning"):
    st.warning = print
if not hasattr(st, "stop"):
    st.stop = lambda: exit(1)

DATA_DIR = Path(__file__).parent / "foretag_data"

FILES_TO_MIGRATE = {
    "utgifter": "utgifter.json",
    "intakter": "intakter.json",
    "bokforing": "bokforing.json",
    "kvitton": "kvitton.json",
    "mal": "mal.json",
    "aktivitetslogg": "aktivitetslogg.json"
}


def clean_data(data):
    """
    Aggressiv städning av data för att ta bort NaN/Infinity.
    Använder Pandas för att hantera detta smidigt.
    """
    try:
        # Konvertera till DataFrame
        df = pd.DataFrame(data)

        # Ersätt NaN/Inf med 0 eller tom sträng
        df = df.replace([np.inf, -np.inf], 0)
        df = df.fillna(0)  # Eller "" om du föredrar tomma strängar för text

        # Konvertera tillbaka till lista av dicts
        return df.to_dict('records')
    except Exception as e:
        print(f"⚠️ Kunde inte städa data med Pandas: {e}")
        # Fallback: Manuell rekursiv städning
        return _manual_clean(data)


def _manual_clean(data):
    if isinstance(data, list):
        return [_manual_clean(item) for item in data]
    elif isinstance(data, dict):
        return {k: _manual_clean(v) for k, v in data.items()}
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return 0.0
        return data
    return data


def migrate():
    print("🚀 Startar migrering till Google Sheets...")

    # --- UTGIFTER ---
    try:
        print("📂 Läser utgifter.json...")
        with open(DATA_DIR / "utgifter.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        rows = []
        if isinstance(data, dict):
            for company, content in data.items():
                print(f"   🔎 Hittade bolag: {company}")
                if isinstance(content, dict) and "utgifter" in content:
                    utgifter_lista = content["utgifter"]
                    print(f"      - Antal utgifter: {len(utgifter_lista)}")
                    for item in utgifter_lista:
                        item["bolag"] = company
                        rows.append(item)

        # STÄDA DATAN
        if rows:
            rows = clean_data(rows)

        print(f"   📊 Totalt antal rader att ladda upp: {len(rows)}")

        if rows:
            print(
                f"   📤 Laddar upp {len(rows)} rader till fliken 'utgifter'...")
            db.save_data("utgifter", rows)
            print("   ✅ Klar med utgifter!")
        else:
            print("   ⚠️ Inga utgifter hittades att ladda upp.")
    except Exception as e:
        print(f"   ❌ Fel vid utgifter: {e}")

    # --- INTÄKTER ---
    try:
        print("📂 Läser intakter.json...")
        with open(DATA_DIR / "intakter.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        rows = []
        if isinstance(data, dict) and "intakter" in data:
            rows = data["intakter"]

        # STÄDA DATAN
        if rows:
            rows = clean_data(rows)

        if rows:
            print(
                f"   📤 Laddar upp {len(rows)} rader till fliken 'intakter'...")
            db.save_data("intakter", rows)
            print("   ✅ Klar med intakter!")
        else:
            print("   ⚠️ Inga intäkter hittades.")
    except Exception as e:
        print(f"   ❌ Fel vid intäkter: {e}")

    # --- ANVÄNDARE (KVITTON.JSON) ---
    try:
        print("📂 Läser kvitton.json (Användare)...")
        with open(DATA_DIR / "kvitton.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        rows = []
        if isinstance(data, dict) and "users" in data:
            rows = data["users"]

        if rows:
            print(f"   📤 Laddar upp {len(rows)} rader till fliken 'users'...")
            db.save_data("users", rows)
            print("   ✅ Klar med users!")
        else:
            print("   ⚠️ Inga användare hittades.")
    except Exception as e:
        print(f"   ❌ Fel vid users: {e}")

    # --- SYSTEM USERS (system_users.json) ---
    try:
        print("📂 Läser system_users.json (Inloggning)...")
        with open(DATA_DIR / "system_users.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        rows = []
        if isinstance(data, dict) and "users" in data:
            for username, user_data in data["users"].items():
                user_row = user_data.copy()
                user_row["username"] = username
                # Konvertera permissions-listan till en sträng för att kunna sparas i en cell
                if "permissions" in user_row and isinstance(user_row["permissions"], list):
                    user_row["permissions"] = ",".join(user_row["permissions"])
                rows.append(user_row)

        if rows:
            print(
                f"   📤 Laddar upp {len(rows)} rader till fliken 'system_users'...")
            db.save_data("system_users", rows)
            print("   ✅ Klar med system_users!")
        else:
            print("   ⚠️ Inga system-användare hittades.")
    except Exception as e:
        print(f"   ❌ Fel vid system_users: {e}")

    # --- AKTIVITETSLOGG ---
    try:
        print("📂 Läser aktivitetslogg.json...")
        with open(DATA_DIR / "aktivitetslogg.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list) and len(data) > 0:
            print(
                f"   📤 Laddar upp {len(data)} rader till fliken 'aktivitetslogg'...")
            db.save_data("aktivitetslogg", data)
            print("   ✅ Klar med aktivitetslogg!")
        else:
            print("   ⚠️ Inga aktiviteter hittades.")
    except Exception as e:
        print(f"   ❌ Fel vid aktivitetslogg: {e}")

    # --- KVITTON (RECEIPTS) ---
    try:
        print("📂 Läser kvitton.json (Kvitton)...")
        with open(DATA_DIR / "kvitton.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        rows = []
        if isinstance(data, dict) and "receipts" in data:
            rows = data["receipts"]

        if rows:
            rows = clean_data(rows)
            print(
                f"   📤 Laddar upp {len(rows)} rader till fliken 'receipts'...")
            db.save_data("receipts", rows)
            print("   ✅ Klar med receipts!")
        else:
            print("   ⚠️ Inga kvitton hittades.")
    except Exception as e:
        print(f"   ❌ Fel vid receipts: {e}")

    # --- MÅL (BUDGET) ---
    try:
        print("📂 Läser mal.json...")
        with open(DATA_DIR / "mal.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        rows = []
        if isinstance(data, dict):
            for company, content in data.items():
                row = {
                    "bolag": company,
                    "total": content.get("total", 0),
                    "kategorier": json.dumps(content.get("kategorier", {}), ensure_ascii=False)
                }
                rows.append(row)

        if rows:
            print(f"   📤 Laddar upp {len(rows)} rader till fliken 'mal'...")
            db.save_data("mal", rows)
            print("   ✅ Klar med mal!")
        else:
            print("   ⚠️ Inga mål hittades.")
    except Exception as e:
        print(f"   ❌ Fel vid mal: {e}")

    # --- BOKFÖRING ---
    try:
        print("📂 Läser bokforing.json...")
        with open(DATA_DIR / "bokforing.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        rows = []
        if isinstance(data, dict):
            for company, years in data.items():
                for year, months in years.items():
                    for month, content in months.items():
                        # Flatten structure: One row per month per company
                        row = {
                            "bolag": company,
                            "ar": year,
                            "manad": month,
                            "status": content.get("status", "ej_paborjad"),
                            # Store full content as JSON
                            "data": json.dumps(content, ensure_ascii=False)
                        }
                        rows.append(row)

        if rows:
            print(
                f"   📤 Laddar upp {len(rows)} rader till fliken 'bokforing'...")
            db.save_data("bokforing", rows)
            print("   ✅ Klar med bokforing!")
        else:
            print("   ⚠️ Ingen bokföring hittades.")
    except Exception as e:
        print(f"   ❌ Fel vid bokforing: {e}")

    print("\n🎉 Migrering klar! VIKTIGT: Titta på FLIKARNA längst ner i Google Sheet!")


if __name__ == "__main__":
    migrate()
