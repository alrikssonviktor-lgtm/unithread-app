import streamlit as st
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List
import base64
from io import BytesIO
from PIL import Image
import fitz  # PyMuPDF för PDF-hantering
import calendar
import plotly.express as px
import plotly.graph_objects as go
import auth

# --- AUTHENTICATION ---
if not auth.check_login():
    st.stop()

DATA_FILE = Path(__file__).parent / "kvitton.json"
REVENUE_FILE = Path(__file__).parent / "intakter.json"
CALENDAR_FILE = Path(__file__).parent / "kalender.json"
BUDGET_FILE = Path(__file__).parent / "budget.json"
CATEGORIES_FILE = Path(__file__).parent / "kategorier.json"
COMPANY_EXPENSES_FILE = Path(__file__).parent / "foretagsutgifter.json"
COMPANY_BUDGET_FILE = Path(__file__).parent / "foretagsbudget.json"
IMAGES_DIR = Path(__file__).parent / "kvitto_bilder"
REVENUE_IMAGES_DIR = Path(__file__).parent / "intakt_bilder"
CALENDAR_FILES_DIR = Path(__file__).parent / "kalender_filer"
COMPANY_FILES_DIR = Path(__file__).parent / "foretag_filer"

# Skapa mappar om de inte finns
IMAGES_DIR.mkdir(exist_ok=True)
REVENUE_IMAGES_DIR.mkdir(exist_ok=True)
CALENDAR_FILES_DIR.mkdir(exist_ok=True)
COMPANY_FILES_DIR.mkdir(exist_ok=True)

# Verksamheter
BUSINESSES = ["Unithread", "Merchoteket"]


def load_data() -> Dict:
    """Laddar användare och kvitton från JSON-fil"""
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_data(data: Dict) -> None:
    """Sparar användare och kvitton till JSON-fil"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")


def load_revenue_data() -> Dict:
    """Laddar intäkter från JSON-fil"""
    if REVENUE_FILE.exists():
        with open(REVENUE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"intakter": [], "total": 0, "kategorier": ["Kundfaktura", "Försäljning", "Konsultarvode", "Övrigt"]}


def save_revenue_data(revenue_data: Dict) -> None:
    """Sparar intäkter till JSON-fil"""
    try:
        with open(REVENUE_FILE, 'w', encoding='utf-8') as f:
            json.dump(revenue_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")


def load_calendar_data() -> Dict:
    """Laddar kalenderhändelser från JSON-fil"""
    if CALENDAR_FILE.exists():
        with open(CALENDAR_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "händelser": [],
        "kategorier": ["Bokföring", "Skatt", "Möte", "Deadline", "Betalning", "Övrigt"]
    }


def save_calendar_data(calendar_data: Dict) -> None:
    """Sparar kalenderhändelser till JSON-fil"""
    try:
        with open(CALENDAR_FILE, 'w', encoding='utf-8') as f:
            json.dump(calendar_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")


def load_budget_data() -> Dict:
    """Laddar budgetdata från JSON-fil"""
    if BUDGET_FILE.exists():
        with open(BUDGET_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "budgets": {},  # {"username": {"total": 10000, "kategorier": {"Mat": 3000, "Transport": 2000}}}
        "warnings_sent": {}
    }


def save_budget_data(budget_data: Dict) -> None:
    """Sparar budgetdata till JSON-fil"""
    try:
        with open(BUDGET_FILE, 'w', encoding='utf-8') as f:
            json.dump(budget_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")


def load_categories() -> Dict:
    """Laddar kategorier från JSON-fil"""
    if CATEGORIES_FILE.exists():
        with open(CATEGORIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "utgifter": {
            "Mat": ["ICA", "Willys", "Coop", "Restaurang"],
            "Transport": ["Bensin", "Parkering", "Kollektivtrafik"],
            "Kontor": ["Material", "Utrustning", "Programvara"],
            "Övrigt": []
        }
    }


def save_categories(categories: Dict) -> None:
    """Sparar kategorier till JSON-fil"""
    try:
        with open(CATEGORIES_FILE, 'r', encoding='utf-8') as f:
            json.dump(categories, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")


def get_expense_category(beskrivning: str, categories: Dict) -> str:
    """Automatisk kategorisering baserat på beskrivning"""
    beskrivning_lower = beskrivning.lower()
    for kategori, nyckelord in categories["utgifter"].items():
        for nyckel in nyckelord:
            if nyckel.lower() in beskrivning_lower:
                return kategori
    return "Övrigt"


def get_category_expenses(data: Dict, username: str, categories: Dict, month: str = None) -> Dict:
    """Räknar utgifter per kategori för en användare"""
    if month is None:
        month = date.today().strftime("%Y-%m")

    category_expenses = {}
    for kategori in categories["utgifter"].keys():
        category_expenses[kategori] = 0

    if username in data:
        for kvitto in data[username]["kvitton"]:
            if kvitto["datum"].startswith(month):
                kategori = get_expense_category(
                    kvitto["beskrivning"], categories)
                if kategori in category_expenses:
                    category_expenses[kategori] += kvitto["belopp"]
                else:
                    category_expenses[kategori] = kvitto["belopp"]

    return category_expenses


def check_category_budget_warnings(data: Dict, budget_data: Dict, categories: Dict) -> List[Dict]:
    """Kontrollerar om någon kategori närmar sig sin budget"""
    warnings = []
    current_month = date.today().strftime("%Y-%m")

    for username, user_budget in budget_data["budgets"].items():
        if "kategorier" not in user_budget:
            continue

        category_expenses = get_category_expenses(
            data, username, categories, current_month)

        for kategori, budget in user_budget["kategorier"].items():
            if budget > 0:
                spent = category_expenses.get(kategori, 0)
                percentage = (spent / budget) * 100

                if percentage >= 80:
                    warnings.append({
                        "user": username,
                        "kategori": kategori,
                        "budget": budget,
                        "spent": spent,
                        "percentage": percentage
                    })

    return warnings


def create_category_budget_chart(data: Dict, budget_data: Dict, categories: Dict, username: str):
    """Skapar stapeldiagram för budget vs faktiska utgifter per kategori"""
    current_month = date.today().strftime("%Y-%m")

    if username not in budget_data["budgets"] or "kategorier" not in budget_data["budgets"][username]:
        return None

    category_expenses = get_category_expenses(
        data, username, categories, current_month)
    user_budget = budget_data["budgets"][username]["kategorier"]

    kategorier = []
    budgets = []
    actual = []

    for kategori in user_budget.keys():
        if user_budget[kategori] > 0:
            kategorier.append(kategori)
            budgets.append(user_budget[kategori])
            actual.append(category_expenses.get(kategori, 0))

    if not kategorier:
        return None

    fig = go.Figure(data=[
        go.Bar(name='Budget', x=kategorier, y=budgets, marker_color='#0066cc'),
        go.Bar(name='Faktiskt', x=kategorier, y=actual, marker_color='#ff4b4b')
    ])

    fig.update_layout(
        title=f"Budget vs Faktiska utgifter - {username}",
        barmode='group',
        xaxis_title="Kategori",
        yaxis_title="Belopp (kr)"
    )

    return fig


def check_budget_warnings(data: Dict, budget_data: Dict, categories: Dict) -> List[Dict]:
    """Kontrollerar om någon användare närmar sig sin budget"""
    warnings = []
    current_month = date.today().strftime("%Y-%m")

    for username, user_data in data.items():
        if username in budget_data["budgets"]:
            user_budget = budget_data["budgets"][username]
            total_budget = user_budget.get("total", 0)

            # Räkna månadens utgifter
            month_expenses = sum(
                k["belopp"] for k in user_data["kvitton"]
                if k["datum"].startswith(current_month)
            )

            if total_budget > 0:
                percentage = (month_expenses / total_budget) * 100
                if percentage >= 80:
                    warnings.append({
                        "user": username,
                        "budget": total_budget,
                        "spent": month_expenses,
                        "percentage": percentage,
                        "type": "total"
                    })

    # Lägg till kategorivarningar
    category_warnings = check_category_budget_warnings(
        data, budget_data, categories)
    for warning in category_warnings:
        warning["type"] = "category"
        warnings.append(warning)

    return warnings


def create_expense_pie_chart(data: Dict, categories: Dict):
    """Skapar cirkeldiagram för utgifter per kategori"""
    category_totals = {}

    for username, user_data in data.items():
        for kvitto in user_data["kvitton"]:
            kategori = get_expense_category(kvitto["beskrivning"], categories)
            if kategori not in category_totals:
                category_totals[kategori] = 0
            category_totals[kategori] += kvitto["belopp"]

    if category_totals:
        fig = px.pie(
            values=list(category_totals.values()),
            names=list(category_totals.keys()),
            title="Utgifter per kategori",
            hole=0.3
        )
        return fig
    return None


def create_monthly_comparison_chart(data: Dict, revenue_data: Dict):
    """Skapar stapeldiagram för intäkter vs utgifter per månad"""
    months = {}

    # Samla utgifter
    for user_data in data.values():
        for kvitto in user_data["kvitton"]:
            month = kvitto["datum"][:7]
            if month not in months:
                months[month] = {"utgifter": 0, "intäkter": 0}
            months[month]["utgifter"] += kvitto["belopp"]

    # Samla intäkter
    for intakt in revenue_data["intakter"]:
        month = intakt["datum"][:7]
        if month not in months:
            months[month] = {"utgifter": 0, "intäkter": 0}
        months[month]["intäkter"] += intakt["belopp"]

    if months:
        sorted_months = sorted(months.items())
        month_labels = [m[0] for m in sorted_months]
        utgifter = [m[1]["utgifter"] for m in sorted_months]
        intäkter = [m[1]["intäkter"] for m in sorted_months]

        fig = go.Figure(data=[
            go.Bar(name='Utgifter', x=month_labels,
                   y=utgifter, marker_color='#ff4b4b'),
            go.Bar(name='Intäkter', x=month_labels,
                   y=intäkter, marker_color='#00cc00')
        ])
        fig.update_layout(
            title="Intäkter vs Utgifter per månad",
            barmode='group',
            xaxis_title="Månad",
            yaxis_title="Belopp (kr)"
        )
        return fig
    return None


def create_revenue_trend_chart(revenue_data: Dict):
    """Skapar linjediagram för intäkter över tid"""
    monthly_revenue = {}

    for intakt in revenue_data["intakter"]:
        month = intakt["datum"][:7]
        if month not in monthly_revenue:
            monthly_revenue[month] = 0
        monthly_revenue[month] += intakt["belopp"]

    if monthly_revenue:
        sorted_months = sorted(monthly_revenue.items())
        months = [m[0] for m in sorted_months]
        amounts = [m[1] for m in sorted_months]

        fig = px.line(
            x=months,
            y=amounts,
            title="Intäktsutveckling",
            markers=True
        )
        fig.update_layout(
            xaxis_title="Månad",
            yaxis_title="Intäkter (kr)"
        )
        fig.update_traces(line_color='#00cc00', line_width=3)
        return fig
    return None


def generate_monthly_report(data: Dict, revenue_data: Dict, month: str) -> pd.DataFrame:
    """Genererar månadsrapport"""
    report_data = {
        "Kategori": [],
        "Typ": [],
        "Antal": [],
        "Summa (kr)": []
    }

    # Utgifter
    categories = load_categories()
    category_stats = {}
    for user_data in data.values():
        for kvitto in user_data["kvitton"]:
            if kvitto["datum"].startswith(month):
                kategori = get_expense_category(
                    kvitto["beskrivning"], categories)
                if kategori not in category_stats:
                    category_stats[kategori] = {"count": 0, "sum": 0}
                category_stats[kategori]["count"] += 1
                category_stats[kategori]["sum"] += kvitto["belopp"]

    for kategori, stats in category_stats.items():
        report_data["Kategori"].append(kategori)
        report_data["Typ"].append("Utgift")
        report_data["Antal"].append(stats["count"])
        report_data["Summa (kr)"].append(f"{stats['sum']:.2f}")

    # Intäkter
    revenue_categories = {}
    for intakt in revenue_data["intakter"]:
        if intakt["datum"].startswith(month):
            kat = intakt["kategori"]
            if kat not in revenue_categories:
                revenue_categories[kat] = {"count": 0, "sum": 0}
            revenue_categories[kat]["count"] += 1
            revenue_categories[kat]["sum"] += intakt["belopp"]

    for kategori, stats in revenue_categories.items():
        report_data["Kategori"].append(kategori)
        report_data["Typ"].append("Intäkt")
        report_data["Antal"].append(stats["count"])
        report_data["Summa (kr)"].append(f"{stats['sum']:.2f}")

    return pd.DataFrame(report_data)


def add_calendar_event(calendar_data: Dict, titel: str, datum: date, tid: str,
                       beskrivning: str, kategori: str, prioritet: str,
                       återkommande: str, påminnelse: int, file_info: tuple = None) -> None:
    """Lägger till kalenderhändelse"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename, file_type = file_info if file_info else (None, None)

    händelse = {
        "id": timestamp,
        "titel": titel,
        "datum": datum.strftime("%Y-%m-%d"),
        "tid": tid,
        "beskrivning": beskrivning,
        "kategori": kategori,
        "prioritet": prioritet,
        "status": "Planerad",
        "återkommande": återkommande,
        "påminnelse": påminnelse,
        "bild": filename,
        "filtyp": file_type,
        "skapad": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    calendar_data["händelser"].append(händelse)
    save_calendar_data(calendar_data)


def update_event_status(calendar_data: Dict, event_id: str, new_status: str) -> None:
    """Uppdaterar status för en händelse"""
    for event in calendar_data["händelser"]:
        if event["id"] == event_id:
            event["status"] = new_status
            break
    save_calendar_data(calendar_data)


def delete_calendar_event(calendar_data: Dict, event_id: str) -> None:
    """Tar bort kalenderhändelse"""
    for i, event in enumerate(calendar_data["händelser"]):
        if event["id"] == event_id:
            if event.get("bild"):
                file_path = CALENDAR_FILES_DIR / event["bild"]
                if file_path.exists():
                    file_path.unlink()
            calendar_data["händelser"].pop(i)
            break
    save_calendar_data(calendar_data)


def get_upcoming_events(calendar_data: Dict, days: int = 7) -> List[Dict]:
    """Hämtar kommande händelser inom X dagar"""
    today = date.today()
    upcoming = []
    for event in calendar_data["händelser"]:
        event_date = datetime.strptime(event["datum"], "%Y-%m-%d").date()
        if today <= event_date <= today + timedelta(days=days) and event["status"] != "Klar":
            upcoming.append(event)
    return sorted(upcoming, key=lambda x: x["datum"])


def get_overdue_events(calendar_data: Dict) -> List[Dict]:
    """Hämtar försenade händelser"""
    today = date.today()
    overdue = []
    for event in calendar_data["händelser"]:
        event_date = datetime.strptime(event["datum"], "%Y-%m-%d").date()
        if event_date < today and event["status"] != "Klar":
            overdue.append(event)
    return sorted(overdue, key=lambda x: x["datum"])


def save_file(uploaded_file, identifier: str, timestamp: str, folder: Path) -> tuple:
    """Sparar uppladdad fil (bild eller PDF) och returnerar filnamn + filtyp"""
    if uploaded_file is None:
        return None, None

    file_extension = uploaded_file.name.split('.')[-1].lower()
    filename = f"{identifier}_{timestamp}.{file_extension}"
    filepath = folder / filename

    with open(filepath, 'wb') as f:
        f.write(uploaded_file.getbuffer())

    return filename, file_extension


def load_image(filename: str, folder: Path = IMAGES_DIR):
    """Laddar bild från disk"""
    if not filename:
        return None
    filepath = folder / filename
    if filepath.exists():
        return Image.open(filepath)
    return None


def pdf_to_images(pdf_path: Path) -> List[Image.Image]:
    """Konverterar PDF till bilder (en per sida)"""
    try:
        doc = fitz.open(pdf_path)
        images = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        doc.close()
        return images
    except Exception as e:
        st.error(f"Kunde inte läsa PDF: {e}")
        return []


def display_file(filename: str, folder: Path = IMAGES_DIR):
    """Visar fil (bild eller PDF)"""
    if not filename:
        return None

    filepath = folder / filename
    if not filepath.exists():
        st.warning("Fil kunde inte hittas")
        return

    file_extension = filename.split('.')[-1].lower()

    if file_extension == 'pdf':
        images = pdf_to_images(filepath)
        if images:
            for i, img in enumerate(images):
                st.image(
                    img, caption=f"Sida {i+1}/{len(images)}", use_container_width=True)
            with open(filepath, 'rb') as f:
                st.download_button(
                    label="📄 Ladda ner PDF",
                    data=f.read(),
                    file_name=filename,
                    mime="application/pdf"
                )
    else:
        image = load_image(filename, folder)
        if image:
            st.image(image, caption="Bild", use_container_width=True)


def add_user(data: Dict, username: str) -> bool:
    """Lägger till ny användare"""
    if username in data:
        return False
    data[username] = {"kvitton": [], "total": 0}
    save_data(data)
    return True


def add_receipt(data: Dict, username: str, beskrivning: str, belopp: float, file_info: tuple = None) -> None:
    """Lägger till kvitto under användare"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename, file_type = file_info if file_info else (None, None)

    kvitto = {
        "datum": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "beskrivning": beskrivning,
        "belopp": belopp,
        "bild": filename,
        "filtyp": file_type,
        "timestamp": timestamp,
        "inlagd_av": username
    }
    data[username]["kvitton"].append(kvitto)
    data[username]["total"] = sum(k["belopp"]
                                  for k in data[username]["kvitton"])
    save_data(data)


def add_company_expense(company_expenses: Dict, verksamhet: str, kategori: str,
                        beskrivning: str, leverantor: str, belopp: float,
                        file_info: tuple = None) -> None:
    """Lägger till företagsutgift"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename, file_type = file_info if file_info else (None, None)

    utgift = {
        "datum": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "kategori": kategori,
        "beskrivning": beskrivning,
        "leverantor": leverantor,
        "belopp": belopp,
        "bild": filename,
        "filtyp": file_type,
        "timestamp": timestamp
    }

    company_expenses[verksamhet]["utgifter"].append(utgift)
    company_expenses[verksamhet]["total"] = sum(
        u["belopp"] for u in company_expenses[verksamhet]["utgifter"]
    )
    save_company_expenses(company_expenses)


def delete_receipt(data: Dict, username: str, index: int) -> None:
    """Tar bort kvitto och tillhörande fil"""
    kvitto = data[username]["kvitton"][index]
    if kvitto.get("bild"):
        file_path = IMAGES_DIR / kvitto["bild"]
        if file_path.exists():
            file_path.unlink()
    data[username]["kvitton"].pop(index)
    data[username]["total"] = sum(k["belopp"]
                                  for k in data[username]["kvitton"])
    save_data(data)


def delete_company_expense(company_expenses: Dict, verksamhet: str, index: int) -> None:
    """Tar bort företagsutgift"""
    utgift = company_expenses[verksamhet]["utgifter"][index]
    if utgift.get("bild"):
        file_path = COMPANY_FILES_DIR / utgift["bild"]
        if file_path.exists():
            file_path.unlink()
    company_expenses[verksamhet]["utgifter"].pop(index)
    company_expenses[verksamhet]["total"] = sum(
        u["belopp"] for u in company_expenses[verksamhet]["utgifter"]
    )
    save_company_expenses(company_expenses)


def get_all_receipts(data: Dict) -> List[Dict]:
    """Hämtar alla kvitton från alla användare och sorterar efter datum"""
    all_receipts = []
    for username, user_data in data.items():
        for kvitto in user_data["kvitton"]:
            receipt_copy = kvitto.copy()
            receipt_copy["användare"] = username
            all_receipts.append(receipt_copy)
    all_receipts.sort(key=lambda x: x["datum"], reverse=True)
    return all_receipts


def export_to_excel(data: Dict, username: str = None) -> bytes:
    """Exporterar kvitton till Excel"""
    rows = []
    if username:
        for kvitto in data[username]["kvitton"]:
            filtyp = kvitto.get("filtyp", "ingen")
            rows.append({
                "Användare": username,
                "Datum": kvitto["datum"],
                "Beskrivning": kvitto["beskrivning"],
                "Belopp": kvitto["belopp"],
                "Inlagd av": kvitto.get("inlagd_av", username),
                "Filtyp": filtyp.upper() if filtyp else "Ingen"
            })
    else:
        for user, user_data in data.items():
            for kvitto in user_data["kvitton"]:
                filtyp = kvitto.get("filtyp", "ingen")
                rows.append({
                    "Användare": user,
                    "Datum": kvitto["datum"],
                    "Beskrivning": kvitto["beskrivning"],
                    "Belopp": kvitto["belopp"],
                    "Inlagd av": kvitto.get("inlagd_av", user),
                    "Filtyp": filtyp.upper() if filtyp else "Ingen"
                })

    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Kvitton')
    return output.getvalue()


def export_revenue_to_excel(revenue_data: Dict) -> bytes:
    """Exporterar intäkter till Excel"""
    rows = []
    for intakt in revenue_data["intakter"]:
        rows.append({
            "Datum": intakt["datum"],
            "Beskrivning": intakt["beskrivning"],
            "Kund": intakt["kund"],
            "Kategori": intakt["kategori"],
            "Fakturanr": intakt.get("fakturanr", ""),
            "Betalningsmetod": intakt["betalningsmetod"],
            "Belopp (inkl moms)": intakt["belopp"],
            "Momssats": f"{intakt['momssats']}%",
            "Moms": intakt["moms"],
            "Exkl moms": intakt["exkl_moms"],
            "Registrerad av": intakt.get("registrerad_av", "")
        })

    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Intäkter')
    return output.getvalue()


def export_calendar_to_excel(calendar_data: Dict) -> bytes:
    """Exporterar kalenderhändelser till Excel"""
    rows = []
    for event in calendar_data["händelser"]:
        rows.append({
            "Datum": event["datum"],
            "Tid": event.get("tid", ""),
            "Titel": event["titel"],
            "Beskrivning": event.get("beskrivning", ""),
            "Kategori": event["kategori"],
            "Prioritet": event["prioritet"],
            "Status": event["status"],
            "Återkommande": event.get("återkommande", "Nej"),
            "Påminnelse": f"{event.get('påminnelse', 0)} dagar"
        })

    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Kalenderhändelser')
    return output.getvalue()


def filter_receipts(kvitton: List[Dict], search: str, start_date: date = None, end_date: date = None) -> List[Dict]:
    """Filtrerar kvitton baserat på sökord och datumintervall"""
    filtered = []
    for kvitto in kvitton:
        if search.lower() in kvitto["beskrivning"].lower():
            if start_date and datetime.strptime(kvitto["datum"], "%Y-%m-%d %H:%M").date() < start_date:
                continue
            if end_date and datetime.strptime(kvitto["datum"], "%Y-%m-%d %H:%M").date() > end_date:
                continue
            filtered.append(kvitto)
    return filtered


def filter_revenue(intakter: List[Dict], search: str, kategori: str, start_date: date = None, end_date: date = None) -> List[Dict]:
    """Filtrerar intäkter baserat på sökord, kategori och datumintervall"""
    filtered = []
    for intakt in intakter:
        if search and search.lower() not in intakt["beskrivning"].lower() and search.lower() not in intakt["kund"].lower():
            continue
        if kategori != "Alla" and intakt["kategori"] != kategori:
            continue
        if start_date and datetime.strptime(intakt["datum"], "%Y-%m-%d %H:%M").date() < start_date:
            continue
        if end_date and datetime.strptime(intakt["datum"], "%Y-%m-%d %H:%M").date() > end_date:
            continue
        filtered.append(intakt)
    return filtered


def filter_calendar_events(händelser: List[Dict], search: str, kategori: str, status: str,
                           start_date: date = None, end_date: date = None) -> List[Dict]:
    """Filtrerar kalenderhändelser"""
    filtered = []
    for event in händelser:
        if search and search.lower() not in event["titel"].lower() and search.lower() not in event.get("beskrivning", "").lower():
            continue
        if kategori != "Alla" and event["kategori"] != kategori:
            continue
        if status != "Alla" and event["status"] != status:
            continue
        event_date = datetime.strptime(event["datum"], "%Y-%m-%d").date()
        if start_date and event_date < start_date:
            continue
        if end_date and event_date > end_date:
            continue
        filtered.append(event)
    return filtered


def find_duplicates(data: Dict) -> List[tuple]:
    """Hittar potentiella dubletter baserat på datum, beskrivning och belopp"""
    duplicates = []
    all_receipts = []

    for username, user_data in data.items():
        for idx, kvitto in enumerate(user_data["kvitton"]):
            all_receipts.append({
                "username": username,
                "index": idx,
                "kvitto": kvitto
            })

    for i in range(len(all_receipts)):
        for j in range(i + 1, len(all_receipts)):
            r1 = all_receipts[i]["kvitto"]
            r2 = all_receipts[j]["kvitto"]
            if (r1["belopp"] == r2["belopp"] and
                    r1["beskrivning"].lower() == r2["beskrivning"].lower()):
                duplicates.append((all_receipts[i], all_receipts[j]))

    return duplicates


def delete_user(data: Dict, username: str) -> bool:
    """Tar bort användare och alla tillhörande kvitton"""
    if username not in data:
        return False

    # Ta bort alla bilder för denna användare
    for kvitto in data[username]["kvitton"]:
        if kvitto.get("bild"):
            file_path = IMAGES_DIR / kvitto["bild"]
            if file_path.exists():
                file_path.unlink()

    # Ta bort användaren
    del data[username]
    save_data(data)
    return True


def load_company_expenses() -> Dict:
    """Laddar företagsutgifter från JSON-fil"""
    if COMPANY_EXPENSES_FILE.exists():
        with open(COMPANY_EXPENSES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "Unithread": {"utgifter": [], "total": 0},
        "Merchoteket": {"utgifter": [], "total": 0},
        "kategorier": [
            "Varuinköp",
            "Marknadsföring",
            "Lokalhyra",
            "IT & Programvara",
            "Lager & Logistik",
            "Design & Produktion",
            "Juridik & Konsulter",
            "Underhåll & Reparationer",
            "Telefoni & Bredband",
            "Transporter",
            "Bank & Avgifter",
            "Övrigt"
        ]
    }


def save_company_expenses(company_expenses: Dict) -> None:
    """Sparar företagsutgifter till JSON-fil"""
    try:
        with open(COMPANY_EXPENSES_FILE, 'w', encoding='utf-8') as f:
            json.dump(company_expenses, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")


def load_company_budget() -> Dict:
    """Laddar företagsbudget från JSON-fil"""
    if COMPANY_BUDGET_FILE.exists():
        with open(COMPANY_BUDGET_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "Unithread": {"total": 0, "kategorier": {}},
        "Merchoteket": {"total": 0, "kategorier": {}},
        "warnings_sent": {}
    }


def save_company_budget(company_budget: Dict) -> None:
    """Sparar företagsbudget till JSON-fil"""
    try:
        with open(COMPANY_BUDGET_FILE, 'w', encoding='utf-8') as f:
            json.dump(company_budget, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")


def get_company_category_expenses(company_expenses: Dict, verksamhet: str, month: str = None) -> Dict:
    """Räknar företagsutgifter per kategori"""
    if month is None:
        month = date.today().strftime("%Y-%m")

    category_expenses = {}
    for kategori in company_expenses["kategorier"]:
        category_expenses[kategori] = 0

    for utgift in company_expenses[verksamhet]["utgifter"]:
        if utgift["datum"].startswith(month):
            kategori = utgift["kategori"]
            category_expenses[kategori] = category_expenses.get(
                kategori, 0) + utgift["belopp"]

    return category_expenses


def create_business_comparison_chart(company_expenses: Dict, revenue_data: Dict):
    """Skapar jämförelsediagram mellan verksamheterna"""
    businesses = []
    revenues = []
    expenses = []
    profits = []

    for business in BUSINESSES:
        # Intäkter för verksamhet
        business_revenue = sum(
            i["belopp"] for i in revenue_data["intakter"]
            if i.get("verksamhet") == business
        )
        # Utgifter för verksamhet
        business_expense = company_expenses[business]["total"]

        businesses.append(business)
        revenues.append(business_revenue)
        expenses.append(business_expense)
        profits.append(business_revenue - business_expense)

    fig = go.Figure(data=[
        go.Bar(name='Intäkter', x=businesses,
               y=revenues, marker_color='#00cc00'),
        go.Bar(name='Utgifter', x=businesses,
               y=expenses, marker_color='#ff4b4b'),
        go.Bar(name='Vinst', x=businesses, y=profits, marker_color='#0066cc')
    ])

    fig.update_layout(
        title="Jämförelse mellan verksamheter",
        barmode='group',
        xaxis_title="Verksamhet",
        yaxis_title="Belopp (kr)"
    )

    return fig


def create_business_pie_chart(company_expenses: Dict, revenue_data: Dict):
    """Skapar cirkeldiagram för fördelning mellan verksamheter"""
    business_totals = {}

    for business in BUSINESSES:
        business_revenue = sum(
            i["belopp"] for i in revenue_data["intakter"]
            if i.get("verksamhet") == business
        )
        business_totals[business] = business_revenue

    if sum(business_totals.values()) > 0:
        fig = px.pie(
            values=list(business_totals.values()),
            names=list(business_totals.keys()),
            title="Intäktsfördelning mellan verksamheter",
            hole=0.3,
            color_discrete_sequence=['#0066cc', '#ff9800']
        )
        return fig
    return None


# Uppdatera add_revenue funktionen (runt rad 570)
def add_revenue(revenue_data: Dict, beskrivning: str, belopp: float, kund: str,
                kategori: str, fakturanr: str, betalningsmetod: str, momssats: float,
                file_info: tuple = None, registrerad_av: str = "Admin", verksamhet: str = None) -> None:
    """Lägger till intäkt"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename, file_type = file_info if file_info else (None, None)

    intakt = {
        "datum": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "beskrivning": beskrivning,
        "belopp": belopp,
        "kund": kund,
        "kategori": kategori,
        "fakturanr": fakturanr,
        "betalningsmetod": betalningsmetod,
        "momssats": momssats,
        "moms": belopp * (momssats / 100),
        "exkl_moms": belopp - (belopp * (momssats / 100)),
        "bild": filename,
        "filtyp": file_type,
        "timestamp": timestamp,
        "registrerad_av": registrerad_av,
        "verksamhet": verksamhet  # LÄGG TILL DETTA!
    }
    revenue_data["intakter"].append(intakt)
    revenue_data["total"] = sum(i["belopp"] for i in revenue_data["intakter"])
    save_revenue_data(revenue_data)


def delete_revenue(revenue_data: Dict, index: int) -> None:
    """Tar bort intäkt och tillhörande fil"""
    intakt = revenue_data["intakter"][index]
    if intakt.get("bild"):
        file_path = REVENUE_IMAGES_DIR / intakt["bild"]
        if file_path.exists():
            file_path.unlink()
    revenue_data["intakter"].pop(index)
    revenue_data["total"] = sum(i["belopp"] for i in revenue_data["intakter"])
    save_revenue_data(revenue_data)


# Huvudapp
st.set_page_config(page_title="Ekonomihantering", page_icon="💼", layout="wide")

data = load_data()
revenue_data = load_revenue_data()
calendar_data = load_calendar_data()
budget_data = load_budget_data()
categories = load_categories()
company_expenses = load_company_expenses()
company_budget = load_company_budget()

# Visa notifikationer
upcoming = get_upcoming_events(calendar_data, days=7)
overdue = get_overdue_events(calendar_data)
budget_warnings = check_budget_warnings(
    data, budget_data, categories)  # UPPDATERAD RAD

if overdue:
    st.error(f"⚠️ {len(overdue)} försenade händelser!")
if upcoming:
    st.info(f"📅 {len(upcoming)} kommande händelser denna vecka")
if budget_warnings:
    for warning in budget_warnings:
        if warning["type"] == "total":
            st.warning(
                f"⚠️ {warning['user']} har använt {warning['percentage']:.1f}% av total budget ({warning['spent']:.2f} / {warning['budget']:.2f} kr)")
        else:  # category
            st.warning(
                f"⚠️ {warning['user']} - {warning['kategori']}: {warning['percentage']:.1f}% av budget använd ({warning['spent']:.2f} / {warning['budget']:.2f} kr)")

# Sidebar - Huvudmeny
st.sidebar.title("📋 Huvudmeny")
main_menu = st.sidebar.radio(
    "Välj kategori",
    ["🏠 Dashboard", "🧾 Personliga Utgifter", "🏢 Företagsutgifter", "💰 Intäkter",
     "📅 Kalender", "💳 Budget", "📊 Rapporter", "⚙️ Inställningar"]
)

# Initiera session state
if 'form_submitted' not in st.session_state:
    st.session_state.form_submitted = False

# --- UPPDATERAD DASHBOARD ---
if main_menu == "🏠 Dashboard":
    st.title("🏠 Dashboard - Kombinerad Översikt")

    # Totala siffror
    total_utgifter_personal = sum(user["total"] for user in data.values())
    total_utgifter_foretag = sum(
        company_expenses[b]["total"] for b in BUSINESSES)
    total_utgifter = total_utgifter_personal + total_utgifter_foretag
    total_intakter = revenue_data["total"]
    netto = total_intakter - total_utgifter

    # Månadssiffror
    current_month = date.today().strftime("%Y-%m")
    month_expenses_personal = sum(
        k["belopp"] for user in data.values()
        for k in user["kvitton"] if k["datum"].startswith(current_month)
    )
    month_expenses_company = sum(
        u["belopp"] for b in BUSINESSES
        for u in company_expenses[b]["utgifter"]
        if u["datum"].startswith(current_month)
    )
    month_revenue = sum(
        i["belopp"] for i in revenue_data["intakter"]
        if i["datum"].startswith(current_month)
    )

    # KPI:er - TOTALT
    st.markdown("## 📊 Total Översikt (Båda verksamheter)")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Totala intäkter", f"{total_intakter:.2f} kr")
    col2.metric("🧾 Totala utgifter", f"{total_utgifter:.2f} kr")
    col3.metric("📈 Nettovinst", f"{netto:.2f} kr", delta=f"{netto:.2f} kr")
    col4.metric(
        "📊 Marginal", f"{(netto/total_intakter*100 if total_intakter > 0 else 0):.1f}%")

    st.markdown("---")

    # Denna månad - TOTALT
    st.subheader("📅 Denna månad - Totalt")
    col1, col2, col3 = st.columns(3)
    col1.metric("Intäkter", f"{month_revenue:.2f} kr")
    col2.metric(
        "Utgifter", f"{month_expenses_personal + month_expenses_company:.2f} kr")
    col3.metric(
        "Netto", f"{month_revenue - (month_expenses_personal + month_expenses_company):.2f} kr")

    st.markdown("---")

    # Per verksamhet
    st.markdown("## 🏢 Per Verksamhet")
    col1, col2 = st.columns(2)

    for idx, business in enumerate(BUSINESSES):
        with [col1, col2][idx]:
            st.markdown(
                f"### {'🏢' if business == 'Unithread' else '🏬'} {business}")

            # Beräkna siffror för verksamhet
            business_revenue = sum(
                i["belopp"] for i in revenue_data["intakter"]
                if i.get("verksamhet") == business
            )
            business_expenses = company_expenses[business]["total"]
            business_profit = business_revenue - business_expenses

            # Month
            month_business_revenue = sum(
                i["belopp"] for i in revenue_data["intakter"]
                if i.get("verksamhet") == business and i["datum"].startswith(current_month)
            )
            month_business_expenses = sum(
                u["belopp"] for u in company_expenses[business]["utgifter"]
                if u["datum"].startswith(current_month)
            )

            st.metric("Intäkter", f"{business_revenue:.2f} kr")
            st.metric("Utgifter", f"{business_expenses:.2f} kr")
            st.metric("Vinst", f"{business_profit:.2f} kr")

            if total_intakter > 0:
                percentage = (business_revenue / total_intakter) * 100
                st.progress(percentage / 100)
                st.caption(f"{percentage:.1f}% av totala intäkter")

    st.markdown("---")

    # Diagram
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Jämförelse mellan verksamheter")
        comparison_chart = create_business_comparison_chart(
            company_expenses, revenue_data)
        if comparison_chart:
            st.plotly_chart(comparison_chart, use_container_width=True)
        else:
            st.info("Ingen data att visa")

    with col2:
        st.subheader("📈 Intäktsfördelning")
        pie_chart = create_business_pie_chart(company_expenses, revenue_data)
        if pie_chart:
            st.plotly_chart(pie_chart, use_container_width=True)
        else:
            st.info("Ingen data att visa")

    # Kommande händelser
    st.markdown("---")
    st.subheader("📅 Kommande denna vecka")
    if upcoming:
        for event in upcoming[:5]:
            days_until = (datetime.strptime(
                event['datum'], "%Y-%m-%d").date() - date.today()).days
            st.write(
                f"📌 **{event['datum']}** ({days_until} dagar) - {event['titel']} ({event['kategori']})")
    else:
        st.info("Inga kommande händelser")

    # Senaste transaktioner
    st.markdown("---")
    st.subheader("🔄 Senaste transaktionerna")

    all_transactions = []
    for user_data in data.values():
        for kvitto in user_data["kvitton"][-5:]:
            all_transactions.append({
                "datum": kvitto["datum"],
                "typ": "Utgift",
                "beskrivning": kvitto["beskrivning"],
                "belopp": f"-{kvitto['belopp']:.2f} kr"
            })

    for intakt in revenue_data["intakter"][-5:]:
        all_transactions.append({
            "datum": intakt["datum"],
            "typ": "Intäkt",
            "beskrivning": intakt["beskrivning"],
            "belopp": f"+{intakt['belopp']:.2f} kr"
        })

    all_transactions.sort(key=lambda x: x["datum"], reverse=True)

    if all_transactions:
        for trans in all_transactions[:10]:
            emoji = "🔴" if trans["typ"] == "Utgift" else "🟢"
            st.write(
                f"{emoji} {trans['datum']} - {trans['beskrivning']} - {trans['belopp']}")
    else:
        st.info("Inga transaktioner än")

# --- PERSONLIGA UTGIFTER ---
elif main_menu == "🧾 Personliga Utgifter":
    page = st.sidebar.selectbox("Välj vy", [
        "Registrera Användare",
        "Lägg Till Kvitto",
        "Visa Kvitton",
        "Alla Användare",
        "Övergripande Register",
        "Hantera Dubletter",
        "Ta Bort Användare"  # NYTT!
    ])

    # --- REGISTRERA ANVÄNDARE ---
    if page == "Registrera Användare":
        st.header("Registrera ny användare")

        with st.form("register_form"):
            username = st.text_input("Användarnamn")
            submitted = st.form_submit_button("Registrera")

            if submitted:
                if not username:
                    st.error("Användarnamn får inte vara tomt!")
                elif add_user(data, username):
                    st.success(f"✅ Användare '{username}' registrerad!")

                    # Öka räknaren för att återställa formuläret
                    if 'register_form_counter' not in st.session_state:
                        st.session_state.register_form_counter = 0
                    st.session_state.register_form_counter += 1

                    st.rerun()
                else:
                    st.warning(f"⚠️ Användare '{username}' finns redan!")

    # --- LÄGG TILL KVITTO ---
    elif page == "Lägg Till Kvitto":
        st.header("Lägg till kvitto")

        if not data:
            st.warning(
                "Inga användare registrerade än. Gå till 'Registrera Användare' först.")
        else:
            # Skapa en unik nyckel för formuläret som ändras efter submit
            form_key = f"receipt_form_{st.session_state.get('receipt_form_counter', 0)}"

            with st.form(form_key):
                username = st.selectbox(
                    "Välj användare", options=list(data.keys()))
                beskrivning = st.text_input("Beskrivning (t.ex. ICA, Bensin)")
                belopp = st.number_input(
                    "Belopp (kr)", min_value=0.0, step=0.01, format="%.2f")
                uploaded_file = st.file_uploader(
                    "Ladda upp kvitto (bild eller PDF)",
                    type=["jpg", "jpeg", "png", "pdf"],
                    help="Stödda format: JPG, PNG, PDF"
                )
                submitted = st.form_submit_button("Lägg till kvitto")

                if submitted:
                    if not beskrivning:
                        st.error("Beskrivning får inte vara tom!")
                    elif belopp <= 0:
                        st.error("Belopp måste vara större än 0!")
                    else:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        file_info = save_file(
                            uploaded_file, username, timestamp, IMAGES_DIR)
                        add_receipt(data, username, beskrivning,
                                    belopp, file_info)
                        st.success(
                            f"✅ Kvitto för {belopp:.2f} kr tillagt till {username}!")

                        # Öka räknaren för att återställa formuläret
                        if 'receipt_form_counter' not in st.session_state:
                            st.session_state.receipt_form_counter = 0
                        st.session_state.receipt_form_counter += 1

                        st.rerun()

    # --- VISA KVITTON ---
    elif page == "Visa Kvitton":
        st.header("Visa kvitton för användare")

        if not data:
            st.warning("Inga användare registrerade än.")
        else:
            username = st.selectbox(
                "Välj användare", options=list(data.keys()))

            user_data = data[username]
            st.subheader(f"Kvitton för {username}")
            st.metric("Total summa", f"{user_data['total']:.2f} kr")

            if not user_data["kvitton"]:
                st.info("Inga kvitton registrerade för denna användare.")
            else:
                # Filtrering
                st.markdown("### Filtrera kvitton")
                search = st.text_input("Sök beskrivning")
                start_date = st.date_input(
                    "Startdatum", value=None, format="YYYY-MM-DD")
                end_date = st.date_input(
                    "Slutdatum", value=None, format="YYYY-MM-DD")

                filtered_kvitton = filter_receipts(
                    user_data["kvitton"], search, start_date, end_date)

                if not filtered_kvitton:
                    st.info("Inga kvitton matchar dina sökkriterier.")
                else:
                    for i, kvitto in enumerate(filtered_kvitton):
                        file_icon = "📄" if kvitto.get(
                            "filtyp") == "pdf" else "📷" if kvitto.get("bild") else ""
                        with st.expander(f"{file_icon} {kvitto['datum']} - {kvitto['beskrivning']} - {kvitto['belopp']:.2f} kr"):
                            col1, col2 = st.columns([2, 1])

                            with col1:
                                st.write(f"**Datum:** {kvitto['datum']}")
                                st.write(
                                    f"**Beskrivning:** {kvitto['beskrivning']}")
                                st.write(
                                    f"**Belopp:** {kvitto['belopp']:.2f} kr")

                                if st.button(f"🗑️ Ta bort", key=f"del_{i}"):
                                    delete_receipt(data, username, i)
                                    st.success("Kvitto borttaget!")
                                    st.rerun()

                            with col2:
                                # Visa fil om den finns
                                if kvitto.get("bild"):
                                    display_file(kvitto["bild"])

                # Exportera
                if st.button("📥 Exportera till Excel"):
                    excel_data = export_to_excel(data, username)
                    st.download_button("Ladda ner kvitton.xlsx", data=excel_data, file_name=f"kvitton_{username}.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- ALLA ANVÄNDARE ---
    elif page == "Alla Användare":
        st.header("Alla användare och deras totala summor")

        if not data:
            st.info("Inga användare registrerade än.")
        else:
            total_sum = sum(user["total"] for user in data.values())
            st.metric("Total summa alla användare", f"{total_sum:.2f} kr")

            st.markdown("---")
            for username, user_data in data.items():
                col1, col2 = st.columns([3, 1])
                col1.subheader(f"👤 {username}")
                col2.metric("Totalt", f"{user_data['total']:.2f} kr")
                st.write(f"Antal kvitton: {len(user_data['kvitton'])}")
                st.markdown("---")

    # --- ÖVERGRIPANDE REGISTER ---
    elif page == "Övergripande Register":
        st.header("📋 Övergripande Kvittoregister")

        if not data:
            st.info("Inga användare eller kvitton registrerade än.")
        else:
            all_receipts = get_all_receipts(data)

            if not all_receipts:
                st.info("Inga kvitton registrerade än.")
            else:
                # Statistik
                col1, col2, col3 = st.columns(3)
                total_sum = sum(r["belopp"] for r in all_receipts)
                col1.metric("Totalt antal kvitton", len(all_receipts))
                col2.metric("Total summa", f"{total_sum:.2f} kr")
                col3.metric("Antal användare", len(data))

                st.markdown("---")

                # Filtrera
                st.subheader("Filtrera register")
                col1, col2 = st.columns(2)
                with col1:
                    filter_user = st.selectbox("Filtrera efter användare", [
                                               "Alla"] + list(data.keys()))
                with col2:
                    filter_search = st.text_input("Sök i beskrivning")

                # Applicera filter
                filtered_receipts = all_receipts
                if filter_user != "Alla":
                    filtered_receipts = [
                        r for r in filtered_receipts if r["användare"] == filter_user]
                if filter_search:
                    filtered_receipts = [
                        r for r in filtered_receipts if filter_search.lower() in r["beskrivning"].lower()]

                st.markdown("---")
                st.subheader(f"Visar {len(filtered_receipts)} kvitton")

                # Visa kvitton i tabell
                for receipt in filtered_receipts:
                    file_icon = "📄" if receipt.get(
                        "filtyp") == "pdf" else "📷" if receipt.get("bild") else ""
                    with st.expander(f"{file_icon} {receipt['datum']} - {receipt['användare']} - {receipt['beskrivning']} - {receipt['belopp']:.2f} kr"):
                        col1, col2 = st.columns([2, 1])

                        with col1:
                            st.write(f"**Användare:** {receipt['användare']}")
                            st.write(f"**Datum:** {receipt['datum']}")
                            st.write(
                                f"**Beskrivning:** {receipt['beskrivning']}")
                            st.write(f"**Belopp:** {receipt['belopp']:.2f} kr")
                            st.write(
                                f"**Inlagd av:** {receipt.get('inlagd_av', receipt['användare'])}")

                        with col2:
                            # Visa fil om den finns
                            if receipt.get("bild"):
                                display_file(receipt["bild"])

                # Exportera alla
                st.markdown("---")
                if st.button("📥 Exportera alla kvitton till Excel"):
                    excel_data = export_to_excel(data)
                    st.download_button(
                        "Ladda ner alla_kvitton.xlsx",
                        data=excel_data,
                        file_name="alla_kvitton.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

    # --- HANTERA DUBLETTER ---
    elif page == "Hantera Dubletter":
        st.header("🔍 Hantera Dubletter")

        if not data:
            st.info("Inga användare eller kvitton registrerade än.")
        else:
            duplicates = find_duplicates(data)

            if not duplicates:
                st.success("✅ Inga dubletter hittades!")
            else:
                st.warning(
                    f"⚠️ Hittade {len(duplicates)} potentiella dubletter")

                for idx, (receipt1, receipt2) in enumerate(duplicates):
                    r1 = receipt1["kvitto"]
                    r2 = receipt2["kvitto"]

                    with st.expander(f"Dublett {idx + 1}: {r1['beskrivning']} - {r1['belopp']:.2f} kr"):
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.subheader("Kvitto 1")
                            st.write(f"**Användare:** {receipt1['username']}")
                            st.write(f"**Datum:** {r1['datum']}")
                            st.write(f"**Beskrivning:** {r1['beskrivning']}")
                            st.write(f"**Belopp:** {r1['belopp']:.2f} kr")
                            st.write(
                                f"**Inlagd av:** {r1.get('inlagd_av', receipt1['username'])}")

                            # Visa fil om den finns
                            if r1.get("bild"):
                                if r1.get("filtyp") == "pdf":
                                    st.info(
                                        "📄 PDF-fil (öppna i 'Visa Kvitton' för att se)")
                                else:
                                    image = load_image(r1["bild"])
                                    if image:
                                        st.image(image, caption="Kvitto 1",
                                                 use_container_width=True)
                                    else:
                                        st.warning("Bild kunde inte laddas")

                            if st.button(f"🗑️ Ta bort Kvitto 1", key=f"del1_{idx}"):
                                delete_receipt(
                                    data, receipt1['username'], receipt1['index'])
                                st.success("Kvitto 1 borttaget!")
                                st.rerun()

                        with col2:
                            st.subheader("Kvitto 2")
                            st.write(f"**Användare:** {receipt2['username']}")
                            st.write(f"**Datum:** {r2['datum']}")
                            st.write(f"**Beskrivning:** {r2['beskrivning']}")
                            st.write(f"**Belopp:** {r2['belopp']:.2f} kr")
                            st.write(
                                f"**Inlagd av:** {r2.get('inlagd_av', receipt2['username'])}")

                            # Visa fil om den finns
                            if r2.get("bild"):
                                if r2.get("filtyp") == "pdf":
                                    st.info(
                                        "📄 PDF-fil (öppna i 'Visa Kvitton' för att se)")
                                else:
                                    image = load_image(r2["bild"])
                                    if image:
                                        st.image(image, caption="Kvitto 2",
                                                 use_container_width=True)
                                    else:
                                        st.warning("Bild kunde inte laddas")

                            if st.button(f"🗑️ Ta bort Kvitto 2", key=f"del2_{idx}"):
                                delete_receipt(
                                    data, receipt2['username'], receipt2['index'])
                                st.success("Kvitto 2 borttaget!")
                                st.rerun()

                        with col3:
                            st.subheader("Åtgärder")
                            st.write("Välj vilket kvitto du vill behålla")

                            if st.button(f"🗑️ Ta bort båda", key=f"del_both_{idx}"):
                                # Ta bort i omvänd ordning för att inte påverka index
                                if receipt1['index'] > receipt2['index']:
                                    delete_receipt(
                                        data, receipt1['username'], receipt1['index'])
                                    delete_receipt(
                                        data, receipt2['username'], receipt2['index'])
                                else:
                                    delete_receipt(
                                        data, receipt2['username'], receipt2['index'])
                                    delete_receipt(
                                        data, receipt1['username'], receipt1['index'])
                                st.success("Båda kvittona borttagna!")
                                st.rerun()

                            if st.button(f"✅ Inte dubletter", key=f"keep_{idx}"):
                                st.info(
                                    "Kvittona markerade som unika (ingen åtgärd)")

                # Knapp för att ta bort alla dubletter automatiskt
                st.markdown("---")
                st.warning("⚠️ Farlig åtgärd")
                if st.button("🗑️ Ta bort alla första kvitton i dublettpar", type="secondary"):
                    removed = 0
                    # Sortera i omvänd ordning för att undvika indexproblem
                    for receipt1, receipt2 in reversed(duplicates):
                        try:
                            delete_receipt(
                                data, receipt1['username'], receipt1['index'])
                            removed += 1
                        except:
                            pass
                    st.success(f"Tog bort {removed} dubletter!")
                    st.rerun()

    # --- TA BORT ANVÄNDARE (NYTT!) ---
    elif page == "Ta Bort Användare":
        st.header("🗑️ Ta bort användare")

        st.warning(
            "⚠️ **VARNING:** Denna åtgärd tar bort användaren och ALLA deras kvitton permanent!")

        if not data:
            st.info("Inga användare registrerade än.")
        else:
            # Lösenordsskydd
            st.markdown("### 🔐 Säkerhetsverifiering")
            st.write(
                "För att ta bort en användare måste du ange administratörslösenordet.")

            password = st.text_input(
                "Administratörslösenord", type="password", key="delete_user_password")

            if password == "Admin":
                st.success("✅ Lösenord godkänt")
                st.markdown("---")

                # Visa användarlista
                st.markdown("### Välj användare att ta bort")

                for username, user_data in data.items():
                    with st.expander(f"👤 {username} - {user_data['total']:.2f} kr ({len(user_data['kvitton'])} kvitton)"):
                        st.write(
                            f"**Total summa:** {user_data['total']:.2f} kr")
                        st.write(
                            f"**Antal kvitton:** {len(user_data['kvitton'])}")

                        # Visa de senaste kvittona
                        if user_data['kvitton']:
                            st.write("**Senaste kvitton:**")
                            for kvitto in user_data['kvitton'][-3:]:
                                st.write(
                                    f"- {kvitto['datum']}: {kvitto['beskrivning']} ({kvitto['belopp']:.2f} kr)")

                        st.markdown("---")

                        # Bekräftelse
                        st.error(
                            f"⚠️ Är du säker på att du vill ta bort användare '{username}'?")
                        st.write("Detta kommer permanent radera:")
                        st.write(f"- {len(user_data['kvitton'])} kvitton")
                        st.write(
                            f"- Totalt värde: {user_data['total']:.2f} kr")
                        st.write(f"- Alla bifogade bilder/filer")

                        col1, col2, col3 = st.columns([1, 1, 2])

                        with col1:
                            confirm = st.checkbox(
                                f"Ja, ta bort", key=f"confirm_{username}")

                        with col2:
                            if confirm and st.button(f"🗑️ TA BORT", key=f"delete_{username}", type="primary"):
                                if delete_user(data, username):
                                    st.success(
                                        f"✅ Användare '{username}' och alla kvitton har tagits bort!")
                                    st.rerun()
                                else:
                                    st.error("Något gick fel vid borttagning.")

                        with col3:
                            if confirm:
                                st.warning(
                                    "⚠️ Klicka på 'TA BORT' för att bekräfta")

            elif password:
                st.error("❌ Fel lösenord! Åtkomst nekad.")
                st.info("Kontakta administratören om du glömt lösenordet.")

# --- INTÄKTER ---
elif main_menu == "💰 Intäkter":
    revenue_page = st.sidebar.selectbox("Välj vy", [
        "Registrera Intäkt",
        "Visa Intäkter",
        "Översikt Intäkter"
    ])

    # --- REGISTRERA INTÄKT (UPPDATERAD) ---
    if revenue_page == "Registrera Intäkt":
        st.header("💰 Registrera ny intäkt")

        form_key = f"revenue_form_{st.session_state.get('revenue_form_counter', 0)}"

        with st.form(form_key):
            # LÄGG TILL VERKSAMHET
            verksamhet = st.selectbox("🏢 Verksamhet", BUSINESSES)

            col1, col2 = st.columns(2)
            with col1:
                beskrivning = st.text_input(
                    "Beskrivning", placeholder="t.ex. Kundfaktura Q4")
                belopp = st.number_input(
                    "Belopp (inkl. moms, kr)", min_value=0.0, step=0.01, format="%.2f")
                kund = st.text_input(
                    "Kund/Källa", placeholder="t.ex. Företag AB")
                kategori = st.selectbox("Kategori", revenue_data["kategorier"])
            with col2:
                fakturanr = st.text_input(
                    "Fakturanummer/Referens", placeholder="Valfritt")
                betalningsmetod = st.selectbox("Betalningsmetod", [
                                               "Swish", "Bankgiro", "Kort", "Faktura", "Kontant", "Övrigt"])
                momssats = st.selectbox("Momssats", [25.0, 12.0, 6.0, 0.0])
                registrerad_av = st.text_input("Registrerad av", value="Admin")

            uploaded_file = st.file_uploader(
                "Ladda upp faktura/bekräftelse (valfritt)", type=["jpg", "jpeg", "png", "pdf"])
            submitted = st.form_submit_button("💾 Registrera intäkt")

            if submitted:
                if not beskrivning:
                    st.error("Beskrivning får inte vara tom!")
                elif belopp <= 0:
                    st.error("Belopp måste vara större än 0!")
                elif not kund:
                    st.error("Kund/Källa måste anges!")
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_info = save_file(uploaded_file, kund.replace(
                        " ", "_"), timestamp, REVENUE_IMAGES_DIR)
                    add_revenue(revenue_data, beskrivning, belopp, kund, kategori,
                                fakturanr, betalningsmetod, momssats, file_info, registrerad_av, verksamhet)
                    st.success(
                        f"✅ Intäkt på {belopp:.2f} kr registrerad för {verksamhet}!")

                    if 'revenue_form_counter' not in st.session_state:
                        st.session_state.revenue_form_counter = 0
                    st.session_state.revenue_form_counter += 1

                    st.rerun()

    # --- VISA INTÄKTER ---
    elif revenue_page == "Visa Intäkter":
        st.header("📋 Alla Intäkter")

        if not revenue_data["intakter"]:
            st.info("Inga intäkter registrerade än.")
        else:
            # Filtrering
            st.markdown("### Filtrera intäkter")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                search = st.text_input("Sök (beskrivning/kund)")
            with col2:
                filter_kategori = st.selectbox(
                    "Kategori", ["Alla"] + revenue_data["kategorier"])
            with col3:
                start_date = st.date_input("Från datum", value=None)
            with col4:
                end_date = st.date_input("Till datum", value=None)

            filtered = filter_revenue(
                revenue_data["intakter"], search, filter_kategori, start_date, end_date)

            if not filtered:
                st.info("Inga intäkter matchar sökningen.")
            else:
                total_filtered = sum(i["belopp"] for i in filtered)
                total_moms = sum(i["moms"] for i in filtered)
                col1, col2, col3 = st.columns(3)
                col1.metric("Antal intäkter", len(filtered))
                col2.metric("Total inkl. moms", f"{total_filtered:.2f} kr")
                col3.metric("Total moms", f"{total_moms:.2f} kr")

                st.markdown("---")

                for idx, intakt in enumerate(filtered):
                    file_icon = "📄" if intakt.get(
                        "filtyp") == "pdf" else "📷" if intakt.get("bild") else ""
                    with st.expander(f"{file_icon} {intakt['datum']} - {intakt['kund']} - {intakt['beskrivning']} - {intakt['belopp']:.2f} kr"):
                        col1, col2 = st.columns([2, 1])

                        with col1:
                            st.write(f"**Datum:** {intakt['datum']}")
                            st.write(
                                f"**Beskrivning:** {intakt['beskrivning']}")
                            st.write(f"**Kund:** {intakt['kund']}")
                            st.write(f"**Kategori:** {intakt['kategori']}")
                            st.write(
                                f"**Fakturanummer:** {intakt.get('fakturanr', '-')}")
                            st.write(
                                f"**Betalningsmetod:** {intakt['betalningsmetod']}")
                            st.write(
                                f"**Belopp (inkl. moms):** {intakt['belopp']:.2f} kr")
                            st.write(f"**Momssats:** {intakt['momssats']}%")
                            st.write(f"**Moms:** {intakt['moms']:.2f} kr")
                            st.write(
                                f"**Exkl. moms:** {intakt['exkl_moms']:.2f} kr")
                            st.write(
                                f"**Registrerad av:** {intakt.get('registrerad_av', '-')}")

                            if st.button(f"🗑️ Ta bort", key=f"del_rev_{idx}"):
                                delete_revenue(revenue_data, idx)
                                st.success("Intäkt borttagen!")
                                st.rerun()

                        with col2:
                            if intakt.get("bild"):
                                display_file(
                                    intakt["bild"], REVENUE_IMAGES_DIR)

                st.markdown("---")
                if st.button("📥 Exportera till Excel"):
                    excel_data = export_revenue_to_excel(revenue_data)
                    st.download_button("Ladda ner intakter.xlsx", data=excel_data, file_name="intakter.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- ÖVERSIKT INTÄKTER ---
    elif revenue_page == "Översikt Intäkter":
        st.header("📊 Översikt Intäkter")

        if not revenue_data["intakter"]:
            st.info("Inga intäkter registrerade än.")
        else:
            # Statistik
            total = revenue_data["total"]
            total_moms = sum(i["moms"] for i in revenue_data["intakter"])
            total_exkl_moms = sum(i["exkl_moms"]
                                  for i in revenue_data["intakter"])

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total intäkter (inkl. moms)", f"{total:.2f} kr")
            col2.metric("Total moms", f"{total_moms:.2f} kr")
            col3.metric("Total exkl. moms", f"{total_exkl_moms:.2f} kr")
            col4.metric("Antal intäkter", len(revenue_data["intakter"]))

            # Per kategori
            st.markdown("---")
            st.subheader("Per kategori")
            kategori_stats = {}
            for intakt in revenue_data["intakter"]:
                kat = intakt["kategori"]
                if kat not in kategori_stats:
                    kategori_stats[kat] = 0
                kategori_stats[kat] += intakt["belopp"]

            for kat, summa in sorted(kategori_stats.items(), key=lambda x: x[1], reverse=True):
                st.write(
                    f"**{kat}:** {summa:.2f} kr ({(summa/total*100):.1f}%)")

            # Per månad
            st.markdown("---")
            st.subheader("Per månad")
            månad_stats = {}
            for intakt in revenue_data["intakter"]:
                månad = intakt["datum"][:7]  # YYYY-MM
                if månad not in månad_stats:
                    månad_stats[månad] = 0
                månad_stats[månad] += intakt["belopp"]

            for månad, summa in sorted(månad_stats.items(), reverse=True):
                st.write(f"**{månad}:** {summa:.2f} kr")

# --- KALENDER ---
elif main_menu == "📅 Kalender":
    calendar_page = st.sidebar.selectbox("Välj vy", [
        "Lägg Till Händelse",
        "Visa Händelser",
        "Månadvy",
        "Kommande Händelser"
    ])

    # --- LÄGG TILL HÄNDELSE ---
    if calendar_page == "Lägg Till Händelse":
        st.header("📅 Lägg till ny händelse")

        form_key = f"calendar_form_{st.session_state.get('calendar_form_counter', 0)}"

        with st.form(form_key):
            col1, col2 = st.columns(2)
            with col1:
                titel = st.text_input(
                    "Titel", placeholder="t.ex. Betala moms Q4")
                event_date = st.date_input("Datum", min_value=date.today())
                tid = st.time_input("Tid (valfritt)", value=None)
                beskrivning = st.text_area(
                    "Beskrivning/Anteckningar", placeholder="Valfritt")
            with col2:
                kategori = st.selectbox(
                    "Kategori", calendar_data["kategorier"])
                prioritet = st.selectbox("Prioritet", ["Hög", "Medel", "Låg"])
                återkommande = st.selectbox(
                    "Återkommande", ["Nej", "Dagligen", "Veckovis", "Månatligen", "Årligen"])
                påminnelse = st.number_input(
                    "Påminnelse (dagar innan)", min_value=0, max_value=30, value=1)

            uploaded_file = st.file_uploader("Bifoga fil (valfritt)", type=[
                                             "jpg", "jpeg", "png", "pdf"])
            submitted = st.form_submit_button("💾 Lägg till händelse")

            if submitted:
                if not titel:
                    st.error("Titel får inte vara tom!")
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_info = save_file(uploaded_file, titel.replace(
                        " ", "_"), timestamp, CALENDAR_FILES_DIR)
                    tid_str = tid.strftime("%H:%M") if tid else ""
                    add_calendar_event(calendar_data, titel, event_date, tid_str, beskrivning,
                                       kategori, prioritet, återkommande, påminnelse, file_info)
                    st.success(f"✅ Händelse '{titel}' tillagd!")

                    # Öka räknaren för att återställa formuläret
                    if 'calendar_form_counter' not in st.session_state:
                        st.session_state.calendar_form_counter = 0
                    st.session_state.calendar_form_counter += 1

                    st.rerun()

    # --- VISA HÄNDELSER ---
    elif calendar_page == "Visa Händelser":
        st.header("📋 Alla Händelser")

        if not calendar_data["händelser"]:
            st.info("Inga händelser registrerade än.")
        else:
            # Filtrering
            st.markdown("### 🔍 Filtrera händelser")
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                search = st.text_input("Sök")
            with col2:
                filter_kategori = st.selectbox(
                    "Kategori", ["Alla"] + calendar_data["kategorier"])
            with col3:
                filter_status = st.selectbox(
                    "Status", ["Alla", "Planerad", "Klar", "Försenad"])
            with col4:
                start_date = st.date_input("Från", value=None)
            with col5:
                end_date = st.date_input("Till", value=None)

            filtered = filter_calendar_events(calendar_data["händelser"], search, filter_kategori,
                                              filter_status, start_date, end_date)

            if not filtered:
                st.info("Inga händelser matchar sökningen.")
            else:
                st.metric("📊 Antal händelser", len(filtered))
                st.markdown("---")

                # Gruppera efter status
                planerade = [e for e in filtered if e["status"] == "Planerad"]
                klara = [e for e in filtered if e["status"] == "Klar"]

                if planerade:
                    st.subheader(f"📝 Planerade händelser ({len(planerade)})")

                    for event in sorted(planerade, key=lambda x: x["datum"]):
                        # Färgkodning baserat på prioritet
                        prioritet_color = {
                            "Hög": "#ff4b4b",
                            "Medel": "#ffa500",
                            "Låg": "#00cc00"
                        }
                        prioritet_icon = "🔴" if event["prioritet"] == "Hög" else "🟡" if event["prioritet"] == "Medel" else "🟢"
                        file_icon = "📄" if event.get(
                            "filtyp") == "pdf" else "📷" if event.get("bild") else ""

                        event_date = datetime.strptime(
                            event["datum"], "%Y-%m-%d").date()
                        days_until = (event_date - date.today()).days

                        if days_until < 0:
                            date_badge = f'<span style="background-color: #ff4b4b; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em;">⚠️ {abs(days_until)} dagar sen</span>'
                        elif days_until == 0:
                            date_badge = f'<span style="background-color: #ffa500; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em;">⏰ IDAG</span>'
                        else:
                            date_badge = f'<span style="background-color: #0066cc; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em;">📅 {days_until} dagar</span>'

                        # Stilad card
                        st.markdown(f"""
                        <div style="border-left: 4px solid {prioritet_color[event['prioritet']]}; 
                                    padding: 10px; 
                                    margin: 10px 0; 
                                    background-color: #f0f2f6; 
                                    border-radius: 5px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <h4 style="margin: 0;">{prioritet_icon} {file_icon} {event['titel']}</h4>
                                    <p style="margin: 5px 0; color: #666;">
                                        📅 {event['datum']} {f"🕐 {event['tid']}" if event.get('tid') else ''} | 
                                        
                                        🏷️ {event['kategori']} | 
                                        {date_badge}
                                    </p>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        with st.expander("📋 Detaljer och åtgärder"):
                            col1, col2 = st.columns([2, 1])

                            with col1:
                                st.write(f"**📅 Datum:** {event['datum']}")
                                if event.get("tid"):
                                    st.write(f"**🕐 Tid:** {event['tid']}")
                                st.write(
                                    f"**🏷️ Kategori:** {event['kategori']}")
                                st.write(
                                    f"**⚡ Prioritet:** {event['prioritet']}")
                                st.write(f"**📊 Status:** {event['status']}")
                                if event.get("beskrivning"):
                                    st.write(
                                        f"**📝 Beskrivning:** {event['beskrivning']}")
                                if event.get("återkommande") != "Nej":
                                    st.write(
                                        f"**🔁 Återkommande:** {event['återkommande']}")
                                st.write(
                                    f"**🔔 Påminnelse:** {event.get('påminnelse', 0)} dagar innan")

                                col_btn1, col_btn2 = st.columns(2)
                                with col_btn1:
                                    if st.button("✅ Markera som klar", key=f"done_{event['id']}", type="primary"):
                                        update_event_status(
                                            calendar_data, event['id'], "Klar")
                                        st.success(
                                            "Händelse markerad som klar!")
                                        st.rerun()
                                with col_btn2:
                                    if st.button("🗑️ Ta bort", key=f"del_{event['id']}", type="secondary"):
                                        delete_calendar_event(
                                            calendar_data, event['id'])
                                        st.success("Händelse borttagen!")
                                        st.rerun()

                            with col2:
                                if event.get("bild"):
                                    display_file(
                                        event["bild"], CALENDAR_FILES_DIR)

                if klara:
                    st.markdown("---")
                    st.subheader(f"✅ Klara händelser ({len(klara)})")

                    for event in sorted(klara, key=lambda x: x["datum"], reverse=True)[:10]:
                        st.markdown(f"""
                        <div style="padding: 8px; 
                                    margin: 5px 0; 
                                    background-color: #e8f5e9; 
                                    border-radius: 5px;
                                    border-left: 3px solid #4caf50;">
                            ✅ <strong>{event['datum']}</strong> - {event['titel']} <em>({event['kategori']})</em>
                        </div>
                        """, unsafe_allow_html=True)

                # Exportera
                st.markdown("---")
                if st.button("📥 Exportera till Excel", type="primary"):
                    excel_data = export_calendar_to_excel(calendar_data)
                    st.download_button("Ladda ner kalender.xlsx", data=excel_data, file_name="kalender.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- MÅNADVY ---
    elif calendar_page == "Månadvy":
        st.header("📅 Månadvy")

        col1, col2 = st.columns([1, 3])
        with col1:
            selected_year = st.selectbox("År", range(
                2020, 2031), index=date.today().year - 2020)
            selected_month = st.selectbox("Månad", range(1, 13), index=date.today().month - 1,
                                          format_func=lambda x: calendar.month_name[x])

        # Skapa kalendergrid
        cal = calendar.monthcalendar(selected_year, selected_month)

        st.markdown(
            f"### {calendar.month_name[selected_month]} {selected_year}")

        # CSS för kalendern
        st.markdown("""
        <style>
        .calendar-day {
            border: 1px solid #ddd;
            padding: 10px;
            min-height: 100px;
            background-color: white;
            border-radius: 5px;
            margin: 2px;
        }
        .calendar-day-header {
            font-weight: bold;
            font-size: 1.1em;
            margin-bottom: 5px;
        }
        .calendar-event {
            font-size: 0.85em;
            padding: 3px;
            margin: 2px 0;
            border-radius: 3px;
            background-color: #e3f2fd;
            border-left: 3px solid #2196f3;
        }
        .calendar-event-high {
            background-color: #ffebee;
            border-left: 3px solid #f44336;
        }
        .today {
            background-color: #fff3e0 !important;
            border: 2px solid #ff9800 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # Visa veckodagar
        cols = st.columns(7)
        weekdays = ["Måndag", "Tisdag", "Onsdag",
                    "Torsdag", "Fredag", "Lördag", "Söndag"]
        for i, day in enumerate(weekdays):
            cols[i].markdown(f"**{day}**")

        # Visa dagar med händelser
        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                if day == 0:
                    cols[i].markdown(
                        '<div class="calendar-day"></div>', unsafe_allow_html=True)
                else:
                    current_date = date(selected_year, selected_month, day)
                    day_events = [e for e in calendar_data["händelser"]
                                  if e["datum"] == current_date.strftime("%Y-%m-%d")]

                    is_today = current_date == date.today()
                    today_class = "today" if is_today else ""

                    with cols[i]:
                        if day_events:
                            event_count = len(day_events)

                            # Sortera händelser efter prioritet
                            high_priority = [
                                e for e in day_events if e["prioritet"] == "Hög"]
                            other_events = [
                                e for e in day_events if e["prioritet"] != "Hög"]

                            events_html = ""
                            # Max 2 hög-prio händelser
                            for e in high_priority[:2]:
                                emoji = "🔴" if e["prioritet"] == "Hög" else "🟡"
                                title = e['titel'][:12] + \
                                    "..." if len(
                                        e['titel']) > 12 else e['titel']
                                events_html += f'<div class="calendar-event calendar-event-high">{emoji} {title}</div>'

                            for e in other_events[:1]:  # Max 1 normal händelse
                                emoji = "🟡" if e["prioritet"] == "Medel" else "🟢"
                                title = e['titel'][:12] + \
                                    "..." if len(
                                        e['titel']) > 12 else e['titel']
                                events_html += f'<div class="calendar-event">{emoji} {title}</div>'

                            if event_count > 3:
                                events_html += f'<div style="font-size: 0.8em; color: #666; margin-top: 3px;">+{event_count-3} fler</div>'

                            st.markdown(f'''
                            <div class="calendar-day {today_class}">
                                <div class="calendar-day-header">{day}</div>
                                {events_html}
                            </div>
                            ''', unsafe_allow_html=True)
                        else:
                            st.markdown(f'''
                            <div class="calendar-day {today_class}">
                                <div class="calendar-day-header">{day}</div>
                            </div>
                            ''', unsafe_allow_html=True)

    # --- KOMMANDE HÄNDELSER ---
    elif calendar_page == "Kommande Händelser":
        st.header("📆 Kommande Händelser")

        tab1, tab2 = st.tabs(["📅 Kommande 7 dagar", "⚠️ Försenade"])

        with tab1:
            upcoming = get_upcoming_events(calendar_data, days=7)
            if not upcoming:
                st.info("Inga kommande händelser de närmaste 7 dagarna.")
            else:
                for event in upcoming:
                    prioritet_color = {
                        "Hög": "#ff4b4b",
                        "Medel": "#ffa500",
                        "Låg": "#00cc00"
                    }
                    prioritet_icon = "🔴" if event["prioritet"] == "Hög" else "🟡" if event["prioritet"] == "Medel" else "🟢"
                    event_date = datetime.strptime(
                        event["datum"], "%Y-%m-%d").date()
                    days_until = (event_date - date.today()).days

                    st.markdown(f"""
                    <div style="border-left: 4px solid {prioritet_color[event['prioritet']]}; 
                                padding: 15px; 
                                margin: 10px 0; 
                                background-color: #f8f9fa; 
                                border-radius: 5px;">
                        <h4 style="margin: 0;">{prioritet_icon} {event['titel']}</h4>
                        <p style="margin: 5px 0;">
                            📅 <strong>{event['datum']}</strong> 
                            ({days_until} dagar) | 
                            🏷️ {event['kategori']}
                        </p>
                        {f'<p style="margin: 5px 0; color: #666;">{event["beskrivning"]}</p>' if event.get('beskrivning') else ''}
                    </div>
                    """, unsafe_allow_html=True)

        with tab2:
            overdue = get_overdue_events(calendar_data)
            if not overdue:
                st.success("✅ Inga försenade händelser!")
            else:
                st.warning(f"⚠️ {len(overdue)} försenade händelser")

                for event in overdue:
                    event_date = datetime.strptime(
                        event["datum"], "%Y-%m-%d").date()
                    days_late = (date.today() - event_date).days

                    st.markdown(f"""
                    <div style="border-left: 4px solid #d32f2f; 
                                padding: 15px; 
                                margin: 10px 0; 
                                background-color: #ffebee; 
                                border-radius: 5px;">
                        <h4 style="margin: 0; color: #d32f2f;">⚠️ {event['titel']}</h4>
                        <p style="margin: 5px 0;">
                            📅 <strong>{event['datum']}</strong> 
                            ({days_late} dagar sen) | 
                            🏷️ {event['kategori']}
                        </p>
                        {f'<p style="margin: 5px 0;">{event["beskrivning"]}</p>' if event.get('beskrivning') else ''}
                    </div>
                    """, unsafe_allow_html=True)

                    col1, col2 = st.columns([3, 1])
                    with col2:
                        if st.button(f"✅ Klar", key=f"done_late_{event['id']}", type="primary"):
                            update_event_status(
                                calendar_data, event['id'], "Klar")
                            st.success("Händelse markerad som klar!")
                            st.rerun()

                    st.markdown("---")

# Lägg till HÄR (efter rad 2211, före "# Exportera allt")

# --- NY SEKTION: FÖRETAGSUTGIFTER ---
elif main_menu == "🏢 Företagsutgifter":
    st.header("🏢 Företagsutgifter")

    company_page = st.sidebar.selectbox("Välj vy", [
        "Registrera Utgift",
        "Visa Utgifter",
        "Budget per Verksamhet",
        "Jämför Verksamheter"
    ])

    if company_page == "Registrera Utgift":
        st.subheader("💼 Registrera ny företagsutgift")

        form_key = f"company_expense_form_{st.session_state.get('company_expense_counter', 0)}"

        with st.form(form_key):
            col1, col2 = st.columns(2)

            with col1:
                verksamhet = st.selectbox("🏢 Verksamhet", BUSINESSES)
                kategori = st.selectbox(
                    "🏷️ Kategori", company_expenses["kategorier"])
                beskrivning = st.text_input(
                    "📝 Beskrivning", placeholder="t.ex. Facebook-annons kampanj")

            with col2:
                leverantor = st.text_input(
                    "🏪 Leverantör/Mottagare", placeholder="t.ex. Meta Business")
                belopp = st.number_input(
                    "💰 Belopp (kr)", min_value=0.0, step=0.01, format="%.2f")
                uploaded_file = st.file_uploader(
                    "📎 Ladda upp kvitto/faktura", type=["jpg", "jpeg", "png", "pdf"])

            submitted = st.form_submit_button(
                "💾 Registrera utgift", type="primary")

            if submitted:
                if not beskrivning:
                    st.error("Beskrivning får inte vara tom!")
                elif not leverantor:
                    st.error("Leverantör måste anges!")
                elif belopp <= 0:
                    st.error("Belopp måste vara större än 0!")
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_info = save_file(uploaded_file, f"{verksamhet}_{leverantor}".replace(
                        " ", "_"), timestamp, COMPANY_FILES_DIR)
                    add_company_expense(
                        company_expenses, verksamhet, kategori, beskrivning, leverantor, belopp, file_info)
                    st.success(
                        f"✅ Utgift på {belopp:.2f} kr registrerad för {verksamhet}!")

                    if 'company_expense_counter' not in st.session_state:
                        st.session_state.company_expense_counter = 0
                    st.session_state.company_expense_counter += 1
                    st.rerun()

    elif company_page == "Visa Utgifter":
        st.subheader("📋 Företagsutgifter")

        view_option = st.selectbox(
            "Visa", ["Alla verksamheter", "Unithread", "Merchoteket"])
        businesses_to_show = BUSINESSES if view_option == "Alla verksamheter" else [
            view_option]

        col1, col2, col3 = st.columns(3)
        with col1:
            filter_kategori = st.selectbox(
                "Kategori", ["Alla"] + company_expenses["kategorier"])
        with col2:
            filter_search = st.text_input("Sök beskrivning/leverantör")
        with col3:
            filter_month = st.date_input(
                "Månad", value=date.today()).strftime("%Y-%m")

        for business in businesses_to_show:
            st.markdown(
                f"### {'🏢' if business == 'Unithread' else '🏬'} {business}")

            utgifter = company_expenses[business]["utgifter"]
            filtered_utgifter = [u for u in utgifter if (filter_kategori == "Alla" or u["kategori"] == filter_kategori) and (not filter_search or filter_search.lower(
            ) in u["beskrivning"].lower() or filter_search.lower() in u["leverantor"].lower()) and u["datum"].startswith(filter_month)]

            if not filtered_utgifter:
                st.info(f"Inga utgifter för {business} matchar filtren")
            else:
                total_filtered = sum(u["belopp"] for u in filtered_utgifter)
                st.metric(f"Total ({filter_month})",
                          f"{total_filtered:.2f} kr")

                for idx, utgift in enumerate(filtered_utgifter):
                    file_icon = "📄" if utgift.get(
                        "filtyp") == "pdf" else "📷" if utgift.get("bild") else ""

                    with st.expander(f"{file_icon} {utgift['datum']} - {utgift['kategori']} - {utgift['beskrivning']} - {utgift['belopp']:.2f} kr"):
                        col1, col2 = st.columns([2, 1])

                        with col1:
                            st.write(f"**📅 Datum:** {utgift['datum']}")
                            st.write(f"**🏷️ Kategori:** {utgift['kategori']}")
                            st.write(
                                f"**📝 Beskrivning:** {utgift['beskrivning']}")
                            st.write(
                                f"**🏪 Leverantör:** {utgift['leverantor']}")
                            st.write(
                                f"**💰 Belopp:** {utgift['belopp']:.2f} kr")

                            if st.button(f"🗑️ Ta bort", key=f"del_company_{business}_{idx}"):
                                delete_company_expense(
                                    company_expenses, business, idx)
                                st.success("Utgift borttagen!")
                                st.rerun()

                        with col2:
                            if utgift.get("bild"):
                                display_file(utgift["bild"], COMPANY_FILES_DIR)

            st.markdown("---")

    elif company_page == "Budget per Verksamhet":
        st.subheader("💳 Budget per verksamhet")

        tab1, tab2 = st.tabs(["Ställ in Budget", "Visa Budget"])

        with tab1:
            for business in BUSINESSES:
                st.markdown(
                    f"#### {'🏢' if business == 'Unithread' else '🏬'} {business}")

                if business not in company_budget:
                    company_budget[business] = {"total": 0, "kategorier": {}}

                current_total = company_budget[business].get("total", 0)
                new_total = st.number_input(f"Total månadsbudget (kr)", min_value=0.0, value=float(
                    current_total), step=1000.0, key=f"total_budget_{business}")
                company_budget[business]["total"] = new_total

                with st.expander(f"Fördela budget på kategorier - {business}"):
                    if "kategorier" not in company_budget[business]:
                        company_budget[business]["kategorier"] = {}

                    allocated = 0
                    for kategori in company_expenses["kategorier"]:
                        current_cat = company_budget[business]["kategorier"].get(
                            kategori, 0)
                        new_cat = st.number_input(f"{kategori}", min_value=0.0, value=float(
                            current_cat), step=100.0, key=f"cat_budget_{business}_{kategori}")
                        company_budget[business]["kategorier"][kategori] = new_cat
                        allocated += new_cat

                    remaining = new_total - allocated
                    if remaining < 0:
                        st.error(
                            f"⚠️ Överallokerat med {abs(remaining):.2f} kr")
                    elif remaining > 0:
                        st.info(f"Kvar att fördela: {remaining:.2f} kr")
                    else:
                        st.success("✅ Helt fördelat")

                st.markdown("---")

            if st.button("💾 Spara budgetar", type="primary"):
                save_company_budget(company_budget)
                st.success("✅ Budgetar sparade!")
                st.rerun()

        with tab2:
            current_month = date.today().strftime("%Y-%m")

            for business in BUSINESSES:
                st.markdown(
                    f"#### {'🏢' if business == 'Unithread' else '🏬'} {business}")

                if business not in company_budget or company_budget[business].get("total", 0) == 0:
                    st.info(f"Ingen budget uppsatt för {business}")
                    continue

                total_budget = company_budget[business]["total"]
                month_expenses = sum(u["belopp"] for u in company_expenses[business]
                                     ["utgifter"] if u["datum"].startswith(current_month))

                percentage = (month_expenses / total_budget *
                              100) if total_budget > 0 else 0
                remaining = total_budget - month_expenses

                col1, col2, col3 = st.columns(3)
                col1.metric("Budget", f"{total_budget:.2f} kr")
                col2.metric("Använt", f"{month_expenses:.2f} kr")
                col3.metric("Kvar", f"{remaining:.2f} kr")

                if percentage >= 100:
                    st.error(f"⚠️ Budget överskriden!")
                elif percentage >= 80:
                    st.warning(f"⚠️ {percentage:.1f}% använt")
                else:
                    st.success(f"✅ {percentage:.1f}% använt")

                st.progress(min(percentage / 100, 1.0))

                if "kategorier" in company_budget[business]:
                    with st.expander(f"Budget per kategori - {business}"):
                        category_expenses = get_company_category_expenses(
                            company_expenses, business, current_month)

                        for kategori, budget in company_budget[business]["kategorier"].items():
                            if budget > 0:
                                spent = category_expenses.get(kategori, 0)
                                cat_perc = (spent / budget *
                                            100) if budget > 0 else 0
                                st.write(
                                    f"**{kategori}:** {spent:.2f} / {budget:.2f} kr ({cat_perc:.1f}%)")
                                st.progress(min(cat_perc / 100, 1.0))

                st.markdown("---")

    elif company_page == "Jämför Verksamheter":
        st.subheader("📊 Jämför verksamheter")

        period = st.selectbox(
            "Tidsperiod", ["Denna månad", "Detta kvartal", "Detta år", "Totalt"])

        if period == "Denna månad":
            start_date = date.today().replace(day=1).strftime("%Y-%m-%d")
        elif period == "Detta kvartal":
            month = date.today().month
            quarter_start = ((month - 1) // 3) * 3 + 1
            start_date = date.today().replace(month=quarter_start, day=1).strftime("%Y-%m-%d")
        elif period == "Detta år":
            start_date = date.today().replace(month=1, day=1).strftime("%Y-%m-%d")
        else:
            start_date = "2000-01-01"

        comparison_data = []
        for business in BUSINESSES:
            business_revenue = sum(i["belopp"] for i in revenue_data["intakter"] if i.get(
                "verksamhet") == business and i["datum"] >= start_date)
            business_expenses = sum(
                u["belopp"] for u in company_expenses[business]["utgifter"] if u["datum"] >= start_date)
            business_profit = business_revenue - business_expenses
            business_margin = (
                business_profit / business_revenue * 100) if business_revenue > 0 else 0

            comparison_data.append({
                "Verksamhet": business,
                "Intäkter": f"{business_revenue:.2f} kr",
                "Utgifter": f"{business_expenses:.2f} kr",
                "Vinst": f"{business_profit:.2f} kr",
                "Marginal": f"{business_margin:.1f}%"
            })

        df = pd.DataFrame(comparison_data)
        st.dataframe(df, use_container_width=True)

        st.markdown("---")
        comparison_chart = create_business_comparison_chart(
            company_expenses, revenue_data)
        if comparison_chart:
            st.plotly_chart(comparison_chart, use_container_width=True)

# ...existing code...

# --- BUDGET (PERSONLIG) ---
elif main_menu == "💳 Budget":
    st.header("💳 Budgethantering")

    budget_page = st.sidebar.selectbox("Välj vy", [
        "Visa Budget",
        "Ställ in Total Budget",
        "Ställ in Kategoribudget",
        "Hantera Kategorier"
    ])

    if budget_page == "Ställ in Total Budget":
        st.subheader("💰 Ställ in total månadsbudget")

        if not data:
            st.warning("Inga användare registrerade än")
        else:
            st.info(
                "💡 Sätt en total månadsbudget för varje användare. Du kan sedan dela upp denna på kategorier.")

            for username in data.keys():
                current_budget = budget_data["budgets"].get(
                    username, {}).get("total", 0)

                with st.expander(f"👤 {username}"):
                    new_budget = st.number_input(
                        f"Total budget (kr/månad)",
                        min_value=0.0,
                        value=float(current_budget),
                        step=100.0,
                        key=f"total_budget_user_{username}"
                    )

                    if username not in budget_data["budgets"]:
                        budget_data["budgets"][username] = {
                            "total": 0, "kategorier": {}}

                    budget_data["budgets"][username]["total"] = new_budget

            if st.button("💾 Spara budgetar", type="primary"):
                save_budget_data(budget_data)
                st.success("✅ Budgetar sparade!")
                st.rerun()

    elif budget_page == "Ställ in Kategoribudget":
        st.subheader("🏷️ Ställ in budget per kategori")

        if not data:
            st.warning("Inga användare registrerade än")
        else:
            username = st.selectbox("Välj användare", list(data.keys()))

            if username not in budget_data["budgets"]:
                budget_data["budgets"][username] = {
                    "total": 0, "kategorier": {}}

            user_budget = budget_data["budgets"][username]
            total_budget = user_budget.get("total", 0)

            st.info(
                f"💰 Total månadsbudget för {username}: {total_budget:.2f} kr")

            if "kategorier" not in user_budget:
                user_budget["kategorier"] = {}

            st.markdown("---")
            st.subheader("Fördela budget på kategorier")

            allocated_sum = 0
            for kategori in categories["utgifter"].keys():
                current_cat_budget = user_budget["kategorier"].get(kategori, 0)

                col1, col2 = st.columns([3, 1])
                with col1:
                    new_cat_budget = st.number_input(
                        f"💵 {kategori}",
                        min_value=0.0,
                        value=float(current_cat_budget),
                        step=100.0,
                        key=f"cat_budget_user_{username}_{kategori}"
                    )
                    user_budget["kategorier"][kategori] = new_cat_budget
                    allocated_sum += new_cat_budget

                with col2:
                    if total_budget > 0:
                        percentage = (new_cat_budget / total_budget) * 100
                        st.metric("% av total", f"{percentage:.1f}%")

            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total budget", f"{total_budget:.2f} kr")
            col2.metric("Fördelat", f"{allocated_sum:.2f} kr")

            remaining = total_budget - allocated_sum
            if remaining < 0:
                col3.metric("Över budget", f"{abs(remaining):.2f} kr")
                st.error(
                    f"⚠️ Du har fördelat {abs(remaining):.2f} kr mer än total budget!")
            elif remaining > 0:
                col3.metric("Kvar att fördela", f"{remaining:.2f} kr")
            else:
                col3.metric("✅ Helt fördelat", "0 kr")

            st.markdown("---")
            if st.button("💾 Spara kategoribudget", type="primary"):
                budget_data["budgets"][username] = user_budget
                save_budget_data(budget_data)
                st.success("✅ Kategoribudget sparad!")
                st.rerun()

    elif budget_page == "Hantera Kategorier":
        st.subheader("🏷️ Hantera budgetkategorier")

        st.info(
            "💡 Kategorierna används både för utgifter och budget. Lägg till eller ta bort kategorier här.")

        for kategori, nyckelord in categories["utgifter"].items():
            with st.expander(f"📁 {kategori}"):
                st.write("**Nyckelord för automatisk kategorisering:**")
                st.write(", ".join(nyckelord)
                         if nyckelord else "Inga nyckelord")

                new_keyword = st.text_input(
                    f"Lägg till nyckelord",
                    key=f"keyword_{kategori}",
                    placeholder="t.ex. ICA, Willys"
                )
                if st.button(f"➕ Lägg till nyckelord", key=f"add_keyword_{kategori}"):
                    if new_keyword and new_keyword not in categories["utgifter"][kategori]:
                        categories["utgifter"][kategori].append(new_keyword)
                        save_categories(categories)
                        st.success(f"✅ '{new_keyword}' tillagt i {kategori}")
                        st.rerun()

                if nyckelord:
                    keyword_to_remove = st.selectbox(
                        "Ta bort nyckelord",
                        ["Välj..."] + nyckelord,
                        key=f"remove_keyword_{kategori}"
                    )
                    if keyword_to_remove != "Välj..." and st.button(f"🗑️ Ta bort", key=f"remove_btn_{kategori}"):
                        categories["utgifter"][kategori].remove(
                            keyword_to_remove)
                        save_categories(categories)
                        st.success(
                            f"✅ '{keyword_to_remove}' borttaget från {kategori}")
                        st.rerun()

        st.markdown("---")
        st.subheader("➕ Lägg till ny kategori")
        col1, col2 = st.columns([2, 1])
        with col1:
            new_category = st.text_input(
                "Kategorinamn", placeholder="t.ex. Resor")
        with col2:
            st.write("")
            st.write("")
            if st.button("✅ Skapa kategori", type="primary"):
                if new_category and new_category not in categories["utgifter"]:
                    categories["utgifter"][new_category] = []
                    save_categories(categories)
                    st.success(f"✅ Kategori '{new_category}' skapad!")
                    st.rerun()
                elif not new_category:
                    st.error("Kategorinamn får inte vara tomt!")
                else:
                    st.warning("Kategorin finns redan!")

    elif budget_page == "Visa Budget":
        st.subheader("📊 Budgetöversikt")

        if not data:
            st.warning("Inga användare registrerade än")
        else:
            current_month = date.today().strftime("%Y-%m")

            username = st.selectbox("Välj användare", list(data.keys()))

            if username not in budget_data["budgets"]:
                st.info("Ingen budget uppsatt för denna användare.")
                st.markdown("---")
                st.write(
                    "💡 Gå till **'Ställ in Total Budget'** för att komma igång.")
            else:
                user_budget = budget_data["budgets"][username]
                total_budget = user_budget.get("total", 0)

                if total_budget == 0:
                    st.warning("Total budget är 0 kr. Sätt en budget först!")
                else:
                    month_expenses = sum(
                        k["belopp"] for k in data[username]["kvitton"]
                        if k["datum"].startswith(current_month)
                    )

                    st.markdown("### 💰 Total budget")
                    percentage = (month_expenses / total_budget *
                                  100) if total_budget > 0 else 0
                    remaining = total_budget - month_expenses

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Budget", f"{total_budget:.2f} kr")
                    col2.metric("Använt", f"{month_expenses:.2f} kr")
                    col3.metric("Kvar", f"{remaining:.2f} kr")

                    if percentage >= 100:
                        st.error(
                            f"⚠️ Budget överskriden med {abs(remaining):.2f} kr!")
                    elif percentage >= 80:
                        st.warning(f"⚠️ {percentage:.1f}% av budget använd")
                    else:
                        st.success(f"✅ {percentage:.1f}% av budget använd")

                    st.progress(min(percentage / 100, 1.0))

                    if "kategorier" in user_budget and user_budget["kategorier"]:
                        st.markdown("---")
                        st.markdown("### 🏷️ Budget per kategori")

                        category_expenses = get_category_expenses(
                            data, username, categories, current_month)

                        for kategori, budget in user_budget["kategorier"].items():
                            if budget > 0:
                                spent = category_expenses.get(kategori, 0)
                                cat_percentage = (spent / budget) * 100
                                cat_remaining = budget - spent

                                with st.expander(f"📁 {kategori} - {spent:.2f} / {budget:.2f} kr ({cat_percentage:.1f}%)"):
                                    col1, col2, col3 = st.columns(3)
                                    col1.metric("Budget", f"{budget:.2f} kr")
                                    col2.metric("Använt", f"{spent:.2f} kr")
                                    col3.metric(
                                        "Kvar", f"{cat_remaining:.2f} kr")

                                    if cat_percentage >= 100:
                                        st.error(
                                            f"⚠️ Budget överskriden med {abs(cat_remaining):.2f} kr!")
                                    elif cat_percentage >= 80:
                                        st.warning(
                                            f"⚠️ {cat_percentage:.1f}% använt")
                                    else:
                                        st.info(
                                            f"{cat_percentage:.1f}% använt")

                                    st.progress(min(cat_percentage / 100, 1.0))

                        st.markdown("---")
                        st.markdown("### 📊 Visuell översikt")
                        chart = create_category_budget_chart(
                            data, budget_data, categories, username)
                        if chart:
                            st.plotly_chart(chart, use_container_width=True)
                    else:
                        st.info(
                            "💡 Ingen kategoribudget uppsatt. Gå till **'Ställ in Kategoribudget'** för att fördela budgeten.")

# --- RAPPORTER ---
elif main_menu == "📊 Rapporter":
    st.header("📊 Rapporter")

    report_type = st.sidebar.selectbox("Välj rapport", [
        "Månadsrapport",
        "Kvartalsrapport",
        "Årsrapport",
        "Skatterapport",
        "Jämförelserapport"
    ])

    if report_type == "Månadsrapport":
        st.subheader("📅 Månadsrapport")

        col1, col2 = st.columns([1, 3])
        with col1:
            selected_month = st.date_input(
                "Välj månad", value=date.today()).strftime("%Y-%m")

        if st.button("📊 Generera rapport", type="primary"):
            st.markdown("---")

            # Beräkna siffror
            total_expenses = sum(
                k["belopp"] for user in data.values()
                for k in user["kvitton"] if k["datum"].startswith(selected_month)
            )
            total_revenue = sum(
                i["belopp"] for i in revenue_data["intakter"]
                if i["datum"].startswith(selected_month)
            )
            netto = total_revenue - total_expenses

            # KPI:er
            st.markdown("### 📊 Sammanfattning")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💰 Intäkter", f"{total_revenue:.2f} kr")
            col2.metric("🧾 Utgifter", f"{total_expenses:.2f} kr")
            col3.metric("📈 Netto", f"{netto:.2f} kr", delta=f"{netto:.2f} kr")
            col4.metric(
                "📊 Marginal", f"{(netto/total_revenue*100 if total_revenue > 0 else 0):.1f}%")

            st.markdown("---")

            # Detaljerad rapport
            report_df = generate_monthly_report(
                data, revenue_data, selected_month)

            if not report_df.empty:
                st.markdown("### 📋 Detaljerad rapport")
                st.dataframe(report_df, use_container_width=True)

                # Export
                st.markdown("---")
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    report_df.to_excel(writer, index=False,
                                       sheet_name='Månadsrapport')

                    # Lägg till sammanfattning
                    summary_df = pd.DataFrame({
                        "Kategori": ["Totala intäkter", "Totala utgifter", "Netto", "Marginal"],
                        "Belopp": [f"{total_revenue:.2f} kr", f"{total_expenses:.2f} kr",
                                   f"{netto:.2f} kr", f"{(netto/total_revenue*100 if total_revenue > 0 else 0):.1f}%"]
                    })
                    summary_df.to_excel(writer, index=False,
                                        sheet_name='Sammanfattning')

                st.download_button(
                    label="📥 Ladda ner rapport (Excel)",
                    data=output.getvalue(),
                    file_name=f"månadsrapport_{selected_month}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("Ingen data för vald månad")

    elif report_type == "Kvartalsrapport":
        st.subheader("📊 Kvartalsrapport")

        col1, col2 = st.columns([1, 3])
        with col1:
            year = st.selectbox("År", range(2020, 2031),
                                index=date.today().year - 2020)
            quarter = st.selectbox("Kvartal", ["Q1", "Q2", "Q3", "Q4"])

        if st.button("📊 Generera rapport", type="primary"):
            # Beräkna månader för kvartalet
            quarter_months = {
                "Q1": ["01", "02", "03"],
                "Q2": ["04", "05", "06"],
                "Q3": ["07", "08", "09"],
                "Q4": ["10", "11", "12"]
            }

            months = [f"{year}-{m}" for m in quarter_months[quarter]]

            st.markdown("---")
            st.markdown(f"### 📅 {quarter} {year}")

            # Samla data per månad
            monthly_data = []
            for month in months:
                month_revenue = sum(
                    i["belopp"] for i in revenue_data["intakter"] if i["datum"].startswith(month))
                month_expenses = sum(k["belopp"] for user in data.values(
                ) for k in user["kvitton"] if k["datum"].startswith(month))
                month_netto = month_revenue - month_expenses

                monthly_data.append({
                    "Månad": month,
                    "Intäkter": f"{month_revenue:.2f} kr",
                    "Utgifter": f"{month_expenses:.2f} kr",
                    "Netto": f"{month_netto:.2f} kr",
                    "Marginal": f"{(month_netto/month_revenue*100 if month_revenue > 0 else 0):.1f}%"
                })

            df = pd.DataFrame(monthly_data)
            st.dataframe(df, use_container_width=True)

            # Totalt för kvartalet
            st.markdown("---")
            total_revenue = sum(i["belopp"] for i in revenue_data["intakter"] if any(
                i["datum"].startswith(m) for m in months))
            total_expenses = sum(k["belopp"] for user in data.values(
            ) for k in user["kvitton"] if any(k["datum"].startswith(m) for m in months))
            total_netto = total_revenue - total_expenses

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Intäkter", f"{total_revenue:.2f} kr")
            col2.metric("Utgifter", f"{total_expenses:.2f} kr")
            col3.metric("Netto", f"{total_netto:.2f} kr")
            col4.metric(
                "Marginal", f"{(total_netto/total_revenue*100 if total_revenue > 0 else 0):.1f}%")

    elif report_type == "Årsrapport":
        st.subheader("📊 Årsrapport")

        year = st.selectbox("Välj år", range(2020, 2031),
                            index=date.today().year - 2020)

        if st.button("📊 Generera rapport", type="primary"):
            st.markdown("---")

            # Beräkna årsdata
            year_revenue = sum(
                i["belopp"] for i in revenue_data["intakter"] if i["datum"].startswith(str(year)))
            year_expenses = sum(k["belopp"] for user in data.values(
            ) for k in user["kvitton"] if k["datum"].startswith(str(year)))
            year_netto = year_revenue - year_expenses

            st.markdown(f"### 📅 Årssammanfattning {year}")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Intäkter", f"{year_revenue:.2f} kr")
            col2.metric("Utgifter", f"{year_expenses:.2f} kr")
            col3.metric("Netto", f"{year_netto:.2f} kr")
            col4.metric(
                "Marginal", f"{(year_netto/year_revenue*100 if year_revenue > 0 else 0):.1f}%")

            st.markdown("---")

            # Per månad
            st.markdown("### 📈 Månadsutveckling")
            monthly_stats = []
            for month in range(1, 13):
                month_str = f"{year}-{month:02d}"
                m_revenue = sum(
                    i["belopp"] for i in revenue_data["intakter"] if i["datum"].startswith(month_str))
                m_expenses = sum(k["belopp"] for user in data.values(
                ) for k in user["kvitton"] if k["datum"].startswith(month_str))

                monthly_stats.append({
                    "Månad": calendar.month_name[month],
                    "Intäkter": m_revenue,
                    "Utgifter": m_expenses,
                    "Netto": m_revenue - m_expenses
                })

            df = pd.DataFrame(monthly_stats)

            # Diagram
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='Intäkter', x=df['Månad'], y=df['Intäkter'], marker_color='#00cc00'))
            fig.add_trace(go.Bar(
                name='Utgifter', x=df['Månad'], y=df['Utgifter'], marker_color='#ff4b4b'))
            fig.add_trace(go.Scatter(
                name='Netto', x=df['Månad'], y=df['Netto'], mode='lines+markers', line=dict(color='#0066cc', width=3)))

            fig.update_layout(
                title=f"Ekonomisk utveckling {year}",
                barmode='group',
                xaxis_title="Månad",
                yaxis_title="Belopp (kr)"
            )

            st.plotly_chart(fig, use_container_width=True)

    elif report_type == "Skatterapport":
        st.subheader("💰 Skatterapport")

        year = st.selectbox("Välj år", range(2020, 2031),
                            index=date.today().year - 2020)

        if st.button("📊 Generera skatterapport", type="primary"):
            st.markdown("---")

            # Beräkna momsunderlag
            total_moms = sum(
                i["moms"] for i in revenue_data["intakter"]
                if i["datum"].startswith(str(year))
            )

            total_intakter_exkl_moms = sum(
                i["exkl_moms"] for i in revenue_data["intakter"]
                if i["datum"].startswith(str(year))
            )

            total_utgifter = sum(
                k["belopp"] for user in data.values()
                for k in user["kvitton"] if k["datum"].startswith(str(year))
            )

            beskattningsbar_vinst = total_intakter_exkl_moms - total_utgifter

            st.markdown(f"### 📋 Skatteunderlag {year}")

            col1, col2, col3 = st.columns(3)
            col1.metric("Intäkter (exkl. moms)",
                        f"{total_intakter_exkl_moms:.2f} kr")
            col2.metric("Avdragsgilla utgifter", f"{total_utgifter:.2f} kr")
            col3.metric("Beskattningsbar vinst",
                        f"{beskattningsbar_vinst:.2f} kr")

            st.markdown("---")
            st.markdown("### 💵 Momsredovisning")

            col1, col2 = st.columns(2)
            col1.metric("Total moms att betala", f"{total_moms:.2f} kr")
            col2.metric("Intäkter inkl. moms",
                        f"{total_intakter_exkl_moms + total_moms:.2f} kr")

            st.markdown("---")
            st.info("💡 **OBS:** Denna rapport är endast vägledande. Konsultera en revisor eller skatterådgivare för officiell skattedeklaration.")

    elif report_type == "Jämförelserapport":
        st.subheader("📊 Jämförelserapport")

        st.markdown("### Välj perioder att jämföra")

        col1, col2 = st.columns(2)
        with col1:
            st.write("**Period 1**")
            period1_type = st.selectbox(
                "Typ", ["Månad", "Kvartal", "År"], key="p1_type")

            if period1_type == "Månad":
                period1 = st.date_input(
                    "Välj månad", key="p1_month").strftime("%Y-%m")
            elif period1_type == "Kvartal":
                year1 = st.selectbox("År", range(2020, 2031), key="p1_year")
                quarter1 = st.selectbox(
                    "Kvartal", ["Q1", "Q2", "Q3", "Q4"], key="p1_q")
                period1 = f"{year1}-{quarter1}"
            else:
                period1 = str(st.selectbox(
                    "År", range(2020, 2031), key="p1_year_only"))

        with col2:
            st.write("**Period 2**")
            period2_type = st.selectbox(
                "Typ", ["Månad", "Kvartal", "År"], key="p2_type")

            if period2_type == "Månad":
                period2 = st.date_input(
                    "Välj månad", key="p2_month").strftime("%Y-%m")
            elif period2_type == "Kvartal":
                year2 = st.selectbox("År", range(2020, 2031), key="p2_year")
                quarter2 = st.selectbox(
                    "Kvartal", ["Q1", "Q2", "Q3", "Q4"], key="p2_q")
                period2 = f"{year2}-{quarter2}"
            else:
                period2 = str(st.selectbox(
                    "År", range(2020, 2031), key="p2_year_only"))

        if st.button("📊 Jämför perioder", type="primary"):
            st.markdown("---")

            # Enkel jämförelse (detta kan göras mer avancerat)
            st.info(
                "Jämförelsefunktionalitet implementeras här baserat på valda perioder.")
            st.write(f"Period 1: {period1}")
            st.write(f"Period 2: {period2}")

# ...existing code...

# --- INSTÄLLNINGAR ---
# ...existing code...

# --- INSTÄLLNINGAR (KOMPLETT VERSION) ---
elif main_menu == "⚙️ Inställningar":
    st.header("⚙️ Inställningar")

    settings_page = st.sidebar.selectbox("Välj kategori", [
        "💾 Backup & Återställning",
        "🏷️ Kategorier",
        "👤 Användare",
        "🏢 Verksamheter",
        "⚙️ System",
        "🔔 Notifikationer"
    ])

    # --- BACKUP & ÅTERSTÄLLNING ---
    if settings_page == "💾 Backup & Återställning":
        st.subheader("💾 Backup & Återställning")

        tab1, tab2, tab3 = st.tabs(
            ["📦 Skapa Backup", "📥 Återställ", "📜 Historik"])

        with tab1:
            st.markdown("### 📦 Skapa backup av all data")

            st.info(
                "💡 Backupen innehåller: Kvitton, Intäkter, Kalender, Budget, Kategorier, Företagsutgifter och Företagsbudget")

            # Visa vad som inkluderas
            col1, col2, col3 = st.columns(3)
            col1.metric("Användare", len(data))
            col2.metric("Kvitton", sum(len(u["kvitton"])
                        for u in data.values()))
            col3.metric("Intäkter", len(revenue_data["intakter"]))

            col1, col2, col3 = st.columns(3)
            col1.metric("Kalenderhändelser", len(calendar_data["händelser"]))
            col2.metric("Kategorier", len(categories["utgifter"]))
            col3.metric("Verksamheter", len(BUSINESSES))

            st.markdown("---")

            if st.button("📦 Skapa komplett backup", type="primary"):
                backup = {
                    "version": "1.0",
                    "backup_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "kvitton": data,
                    "intakter": revenue_data,
                    "kalender": calendar_data,
                    "budget": budget_data,
                    "kategorier": categories,
                    "foretagsutgifter": company_expenses,
                    "foretagsbudget": company_budget,
                    "statistics": {
                        "total_users": len(data),
                        "total_receipts": sum(len(u["kvitton"]) for u in data.values()),
                        "total_revenue": revenue_data["total"],
                        "total_events": len(calendar_data["händelser"])
                    }
                }

                backup_json = json.dumps(backup, indent=2, ensure_ascii=False)

                st.success("✅ Backup skapad!")
                st.download_button(
                    label="💾 Ladda ner backup",
                    data=backup_json,
                    file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )

        with tab2:
            st.markdown("### 📥 Återställ från backup")

            st.warning(
                "⚠️ **VARNING:** Detta kommer att ersätta ALL befintlig data!")

            uploaded_backup = st.file_uploader(
                "Välj backup-fil (.json)", type=["json"])

            if uploaded_backup:
                try:
                    backup = json.load(uploaded_backup)

                    # Visa information om backupen
                    st.info(
                        f"📅 Backup skapad: {backup.get('backup_date', 'Okänt')}")
                    st.info(f"🔢 Version: {backup.get('version', 'Okänt')}")

                    if "statistics" in backup:
                        st.markdown("**Innehåll:**")
                        col1, col2, col3 = st.columns(3)
                        col1.metric(
                            "Användare", backup["statistics"].get("total_users", 0))
                        col2.metric("Kvitton", backup["statistics"].get(
                            "total_receipts", 0))
                        col3.metric(
                            "Intäkter", f"{backup['statistics'].get('total_revenue', 0):.2f} kr")

                    st.markdown("---")

                    st.error(
                        "⚠️ Detta kommer permanent ersätta all befintlig data!")

                    confirm = st.checkbox(
                        "Jag förstår att detta tar bort all nuvarande data")

                    if confirm and st.button("📥 Återställ data", type="primary"):
                        # Återställ data
                        if "kvitton" in backup:
                            save_data(backup["kvitton"])
                        if "intakter" in backup:
                            save_revenue_data(backup["intakter"])
                        if "kalender" in backup:
                            save_calendar_data(backup["kalender"])
                        if "budget" in backup:
                            save_budget_data(backup["budget"])
                        if "kategorier" in backup:
                            save_categories(backup["kategorier"])
                        if "foretagsutgifter" in backup:
                            save_company_expenses(backup["foretagsutgifter"])
                        if "foretagsbudget" in backup:
                            save_company_budget(backup["foretagsbudget"])

                        st.success("✅ Data återställd från backup!")
                        st.balloons()
                        st.rerun()

                except Exception as e:
                    st.error(f"❌ Kunde inte läsa backup-filen: {e}")

        with tab3:
            st.markdown("### 📜 Backup-historik")
            st.info("Visa tidigare backups (funktion kommer snart)")

    # --- KATEGORIER ---
    elif settings_page == "🏷️ Kategorier":
        st.subheader("🏷️ Hantera kategorier")

        tab1, tab2, tab3 = st.tabs(
            ["Utgiftskategorier", "Intäktskategorier", "Kalenderkategorier"])

        with tab1:
            st.markdown("### 📤 Utgiftskategorier")

            for kategori, nyckelord in categories["utgifter"].items():
                with st.expander(f"📁 {kategori}"):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.write("**Nyckelord för automatisk kategorisering:**")
                        if nyckelord:
                            for word in nyckelord:
                                st.write(f"• {word}")
                        else:
                            st.write("*Inga nyckelord*")

                        new_keyword = st.text_input(
                            "Lägg till nyckelord",
                            key=f"expense_keyword_{kategori}",
                            placeholder="t.ex. ICA, Willys, Hemköp"
                        )

                        if st.button(f"➕ Lägg till", key=f"add_expense_{kategori}"):
                            if new_keyword and new_keyword not in categories["utgifter"][kategori]:
                                categories["utgifter"][kategori].append(
                                    new_keyword)
                                save_categories(categories)
                                st.success(f"✅ '{new_keyword}' tillagt!")
                                st.rerun()

                    with col2:
                        if nyckelord:
                            keyword_to_remove = st.selectbox(
                                "Ta bort nyckelord",
                                ["Välj..."] + nyckelord,
                                key=f"remove_expense_{kategori}"
                            )
                            if keyword_to_remove != "Välj..." and st.button(f"🗑️ Ta bort", key=f"del_expense_{kategori}"):
                                categories["utgifter"][kategori].remove(
                                    keyword_to_remove)
                                save_categories(categories)
                                st.success(f"✅ Borttaget!")
                                st.rerun()

            st.markdown("---")
            st.markdown("### ➕ Skapa ny utgiftskategori")

            col1, col2 = st.columns([3, 1])
            with col1:
                new_expense_category = st.text_input(
                    "Kategorinamn", placeholder="t.ex. Resor", key="new_expense_cat")
            with col2:
                st.write("")
                st.write("")
                if st.button("➕ Skapa", type="primary", key="create_expense_cat"):
                    if new_expense_category and new_expense_category not in categories["utgifter"]:
                        categories["utgifter"][new_expense_category] = []
                        save_categories(categories)
                        st.success(
                            f"✅ Kategori '{new_expense_category}' skapad!")
                        st.rerun()

        with tab2:
            st.markdown("### 💰 Intäktskategorier")

            for kategori in revenue_data["kategorier"]:
                with st.expander(f"💵 {kategori}"):
                    st.write(f"**Kategori:** {kategori}")

                    if st.button(f"🗑️ Ta bort kategori", key=f"del_revenue_{kategori}"):
                        revenue_data["kategorier"].remove(kategori)
                        save_revenue_data(revenue_data)
                        st.success("Kategori borttagen!")
                        st.rerun()

            st.markdown("---")
            st.markdown("### ➕ Skapa ny intäktskategori")

            col1, col2 = st.columns([3, 1])
            with col1:
                new_revenue_category = st.text_input(
                    "Kategorinamn", placeholder="t.ex. Produktförsäljning", key="new_revenue_cat")
            with col2:
                st.write("")
                st.write("")
                if st.button("➕ Skapa", type="primary", key="create_revenue_cat"):
                    if new_revenue_category and new_revenue_category not in revenue_data["kategorier"]:
                        revenue_data["kategorier"].append(new_revenue_category)
                        save_revenue_data(revenue_data)
                        st.success(
                            f"✅ Kategori '{new_revenue_category}' skapad!")
                        st.rerun()

        with tab3:
            st.markdown("### 📅 Kalenderkategorier")

            for kategori in calendar_data["kategorier"]:
                with st.expander(f"📌 {kategori}"):
                    st.write(f"**Kategori:** {kategori}")

                    if st.button(f"🗑️ Ta bort kategori", key=f"del_calendar_{kategori}"):
                        calendar_data["kategorier"].remove(kategori)
                        save_calendar_data(calendar_data)
                        st.success("Kategori borttagen!")
                        st.rerun()

            st.markdown("---")
            st.markdown("### ➕ Skapa ny kalenderkategori")

            col1, col2 = st.columns([3, 1])
            with col1:
                new_calendar_category = st.text_input(
                    "Kategorinamn", placeholder="t.ex. Kundmöte", key="new_calendar_cat")
            with col2:
                st.write("")
                st.write("")
                if st.button("➕ Skapa", type="primary", key="create_calendar_cat"):
                    if new_calendar_category and new_calendar_category not in calendar_data["kategorier"]:
                        calendar_data["kategorier"].append(
                            new_calendar_category)
                        save_calendar_data(calendar_data)
                        st.success(
                            f"✅ Kategori '{new_calendar_category}' skapad!")
                        st.rerun()

    # --- ANVÄNDARE ---
    elif settings_page == "👤 Användare":
        st.subheader("👤 Hantera användare")

        if not data:
            st.info("Inga användare registrerade än.")
        else:
            st.markdown("### 📋 Registrerade användare")

            for username, user_data in data.items():
                with st.expander(f"👤 {username}"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Kvitton", len(user_data["kvitton"]))
                    col2.metric("Total", f"{user_data['total']:.2f} kr")
                    col3.metric(
                        "Budget", f"{budget_data['budgets'].get(username, {}).get('total', 0):.2f} kr")

                    st.markdown("---")

                    # Ändra namn
                    new_name = st.text_input(
                        "Nytt användarnamn", value=username, key=f"rename_{username}")
                    if new_name != username and st.button(f"💾 Spara nytt namn", key=f"save_name_{username}"):
                        if new_name not in data:
                            data[new_name] = data.pop(username)
                            if username in budget_data["budgets"]:
                                budget_data["budgets"][new_name] = budget_data["budgets"].pop(
                                    username)
                            save_data(data)
                            save_budget_data(budget_data)
                            st.success(
                                f"✅ Användare omdöpt till '{new_name}'!")
                            st.rerun()
                        else:
                            st.error(f"Namnet '{new_name}' är redan upptaget!")

                    st.markdown("---")

                    # Ta bort användare
                    st.error("⚠️ Farlig zon")
                    if st.button(f"🗑️ Ta bort användare och all data", key=f"del_user_{username}", type="secondary"):
                        if delete_user(data, username):
                            # Ta även bort budget
                            if username in budget_data["budgets"]:
                                del budget_data["budgets"][username]
                                save_budget_data(budget_data)
                            st.success(f"✅ Användare '{username}' borttagen!")
                            st.rerun()

    # --- VERKSAMHETER ---
    elif settings_page == "🏢 Verksamheter":
        st.subheader("🏢 Hantera verksamheter")

        st.info("💡 Här kan du se och hantera dina verksamheter")

        for business in BUSINESSES:
            with st.expander(f"{'🏢' if business == 'Unithread' else '🏬'} {business}"):
                # Statistik
                total_expenses = company_expenses[business]["total"]
                total_revenue = sum(i["belopp"] for i in revenue_data["intakter"] if i.get(
                    "verksamhet") == business)

                col1, col2, col3 = st.columns(3)
                col1.metric("Utgifter", f"{total_expenses:.2f} kr")
                col2.metric("Intäkter", f"{total_revenue:.2f} kr")
                col3.metric(
                    "Vinst", f"{total_revenue - total_expenses:.2f} kr")

                st.write(
                    f"**Antal utgifter:** {len(company_expenses[business]['utgifter'])}")
                st.write(
                    f"**Budget:** {company_budget.get(business, {}).get('total', 0):.2f} kr/månad")

        st.markdown("---")
        st.info("🚧 Funktionalitet för att lägga till/ta bort verksamheter kommer snart")

    # --- SYSTEM ---
    elif settings_page == "⚙️ System":
        st.subheader("⚙️ Systeminställningar")

        tab1, tab2, tab3 = st.tabs(["💰 Valuta", "📅 Datum & Tid", "🎨 Utseende"])

        with tab1:
            st.markdown("### 💰 Valutainställningar")

            currency = st.selectbox(
                "Valuta", ["SEK (kr)", "EUR (€)", "USD ($)", "GBP (£)"], index=0)
            decimal_separator = st.selectbox(
                "Decimaltecken", ["Punkt (.)", "Komma (,)"], index=0)
            thousand_separator = st.selectbox(
                "Tusentalsavgränsare", ["Mellanslag", "Punkt", "Komma", "Ingen"], index=0)

            st.info(
                "💡 Valutainställningar sparas automatiskt (funktion kommer snart)")

        with tab2:
            st.markdown("### 📅 Datum- och tidsinställningar")

            date_format = st.selectbox(
                "Datumformat", ["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"], index=0)
            time_format = st.selectbox(
                "Tidsformat", ["24-timmars", "12-timmars"], index=0)
            first_day_of_week = st.selectbox(
                "Första dag i veckan", ["Måndag", "Söndag"], index=0)

            st.info("💡 Inställningar sparas automatiskt (funktion kommer snart)")

        with tab3:
            st.markdown("### 🎨 Utseende")

            theme = st.selectbox("Tema", ["Ljust", "Mörkt", "Auto"], index=0)

            st.info("💡 Temainställningar kräver omstart av appen")

    # --- NOTIFIKATIONER ---
    elif settings_page == "🔔 Notifikationer":
        st.subheader("🔔 Notifikationer")

        tab1, tab2, tab3 = st.tabs(["📧 E-post", "📅 Påminnelser", "💰 Budget"])

        with tab1:
            st.markdown("### 📧 E-postnotiser")

            email_enabled = st.checkbox("Aktivera e-postnotiser")

            if email_enabled:
                email = st.text_input(
                    "E-postadress", placeholder="din@email.com")

                st.markdown("**Skicka notiser för:**")
                notify_calendar = st.checkbox(
                    "Kommande kalenderhändelser", value=True)
                notify_budget = st.checkbox("Budgetvarningar", value=True)
                notify_reports = st.checkbox(
                    "Månatliga rapporter", value=False)

                if st.button("💾 Spara e-postinställningar", type="primary"):
                    st.success("✅ E-postinställningar sparade!")
                    st.info("🚧 E-postfunktionalitet kommer snart")

        with tab2:
            st.markdown("### 📅 Kalenderpåminnelser")

            default_reminder = st.number_input(
                "Standard påminnelse (dagar innan)", min_value=0, max_value=30, value=1)
            reminder_time = st.time_input(
                "Påminnelsetid", value=datetime.strptime("09:00", "%H:%M").time())

            st.markdown("**Påminn mig om:**")
            remind_overdue = st.checkbox("Försenade händelser", value=True)
            remind_today = st.checkbox("Dagens händelser", value=True)
            remind_week = st.checkbox("Veckans händelser", value=True)

            if st.button("💾 Spara påminnelseinställningar", type="primary"):
                st.success("✅ Påminnelseinställningar sparade!")

        with tab3:
            st.markdown("### 💰 Budgetnotiser")

            budget_alerts = st.checkbox("Aktivera budgetvarningar", value=True)

            if budget_alerts:
                alert_threshold = st.slider(
                    "Varna vid X% av budget använd", min_value=50, max_value=100, value=80, step=5)

                st.write(
                    f"**Du får varningar när budgeten når {alert_threshold}%**")

                st.markdown("**Varna för:**")
                warn_total = st.checkbox("Total budget", value=True)
                warn_category = st.checkbox("Kategoribudget", value=True)
                warn_company = st.checkbox("Företagsbudget", value=True)

                if st.button("💾 Spara budgetinställningar", type="primary"):
                    st.success("✅ Budgetinställningar sparade!")

# ...existing code... (Exportera allt)

# Fortsätt med befintlig "Exportera allt"-kod...


# Exportera allt
st.markdown("---")
st.header("📥 Exportera Data")

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("📥 Exportera alla utgifter"):
        excel_data = export_to_excel(data)
        st.download_button("Ladda ner utgifter.xlsx", data=excel_data, file_name="alla_utgifter.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
with col2:
    if revenue_data["intakter"] and st.button("📥 Exportera alla intäkter"):
        excel_data = export_revenue_to_excel(revenue_data)
        st.download_button("Ladda ner intäkter.xlsx", data=excel_data, file_name="alla_intakter.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
with col3:
    if calendar_data["händelser"] and st.button("📥 Exportera kalender"):
        excel_data = export_calendar_to_excel(calendar_data)
        st.download_button("Ladda ner kalender.xlsx", data=excel_data, file_name="kalender.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
