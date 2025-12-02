import json
from pathlib import Path
from db_handler import db

DATA_DIR = Path(__file__).parent / "foretag_data"
BUDGET_FILE = DATA_DIR / "budget.json"


def migrate_budget():
    print("🚀 Migrerar budget till Google Sheets...")

    if not BUDGET_FILE.exists():
        print("❌ budget.json hittades inte!")
        return

    try:
        with open(BUDGET_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        rows = []
        for bolag, content in data.items():
            row = {
                "bolag": bolag,
                "total": content.get("total", 0),
                "kategorier": json.dumps(content.get("kategorier", {}), ensure_ascii=False)
            }
            rows.append(row)

        print(f"   📊 Hittade {len(rows)} rader att ladda upp.")
        db.save_data("budget", rows)
        print("   ✅ Klar med budget!")

    except Exception as e:
        print(f"   ❌ Fel vid migrering av budget: {e}")


if __name__ == "__main__":
    migrate_budget()
