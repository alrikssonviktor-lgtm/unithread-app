import json
from pathlib import Path
from db_handler import db

DATA_DIR = Path(__file__).parent / "foretag_data"
CHATT_FILE = DATA_DIR / "chatt.json"


def migrate_chat():
    print("🚀 Migrerar chatt till Google Sheets...")

    if not CHATT_FILE.exists():
        print("❌ chatt.json hittades inte!")
        return

    try:
        with open(CHATT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        rows = []
        for group in data.get("groups", []):
            rows.append({
                "id": group["id"],
                "type": "group",
                "data": json.dumps(group, ensure_ascii=False)
            })
        for message in data.get("messages", []):
            msg_id = message.get("timestamp", "") + "_" + \
                message.get("sender", "")
            rows.append({
                "id": msg_id,
                "type": "message",
                "data": json.dumps(message, ensure_ascii=False)
            })

        print(f"   📊 Hittade {len(rows)} rader att ladda upp.")
        db.save_data("chatt", rows)
        print("   ✅ Klar med chatt!")

    except Exception as e:
        print(f"   ❌ Fel vid migrering av chatt: {e}")


if __name__ == "__main__":
    migrate_chat()
