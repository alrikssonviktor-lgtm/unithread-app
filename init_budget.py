import json
from db_handler import db


def init_budget():
    print("🚀 Initierar budget-fliken i Google Sheets...")

    default_budget = {
        "Unithread": {"total": 0, "kategorier": {}},
        "Merchoteket": {"total": 0, "kategorier": {}}
    }

    rows = []
    for bolag, content in default_budget.items():
        row = {
            "bolag": bolag,
            "total": content.get("total", 0),
            "kategorier": json.dumps(content.get("kategorier", {}), ensure_ascii=False)
        }
        rows.append(row)

    try:
        db.save_data("budget", rows)
        print("✅ Budget-fliken skapad och initierad med standardvärden!")
    except Exception as e:
        print(f"❌ Kunde inte skapa budget-fliken: {e}")


if __name__ == "__main__":
    init_budget()
