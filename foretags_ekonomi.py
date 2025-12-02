import streamlit as st
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import calendar
import numpy as np
from PIL import Image
import base64
import fitz  # PyMuPDF för PDF-hantering
import sys  # <-- LAGT TILL
import uuid
import auth

# --- KONFIGURATION ---
DATA_DIR = Path(__file__).parent / "foretag_data"
DATA_DIR.mkdir(exist_ok=True)

EXPENSES_FILE = DATA_DIR / "utgifter.json"
REVENUE_FILE = DATA_DIR / "intakter.json"
BUDGET_FILE = DATA_DIR / "budget.json"
FILES_DIR = DATA_DIR / "filer"
FILES_DIR.mkdir(exist_ok=True)

# Verksamheter
BUSINESSES = ["Unithread", "Merchoteket"]

# Kategorier
EXPENSE_CATEGORIES = [
    "Varuinköp",
    "Marknadsföring",
    "IT & Programvara",
    "Lokalhyra",
    "Transport & Logistik",
    "Design & Produktion",
    "Juridik & Konsulter",
    "Bank & Avgifter",
    "Övrigt"
]

REVENUE_CATEGORIES = [
    "Produktförsäljning",
    "Tjänster",
    "Konsultarvode",
    "Övrigt"
]

RECEIPTS_FILE = DATA_DIR / "kvitton.json"
RECEIPT_IMAGES_DIR = FILES_DIR / "kvitton"
RECEIPT_IMAGES_DIR.mkdir(exist_ok=True)

# Kalender
CALENDAR_FILE = DATA_DIR / "kalender.json"

# Admin-inställningar
ADMIN_PASSWORD = "Admin"
ADMIN_USERNAME = "Viktor"

# --- AUTHENTICATION FUNCTIONS ---


def check_admin_password() -> bool:
    """Kontrollerar admin-lösenord"""
    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False

    if st.session_state.admin_logged_in:
        return True

    st.subheader("🔒 Admin-inloggning")
    with st.form("admin_login"):
        username = st.text_input("👤 Användarnamn")
        password = st.text_input("🔑 Lösenord", type="password")
        submitted = st.form_submit_button("🔓 Logga in", type="primary")

        if submitted:
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.success("✅ Inloggad!")
                st.rerun()
            else:
                st.error("❌ Fel användarnamn eller lösenord")
                return False

    return False


def admin_logout():
    """Loggar ut admin"""
    st.session_state.admin_logged_in = False
    st.rerun()


# --- DATAHANTERING ---


def load_expenses() -> Dict:
    """Laddar utgifter från JSON"""
    if EXPENSES_FILE.exists():
        with open(EXPENSES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "Unithread": {"utgifter": [], "total": 0},
        "Merchoteket": {"utgifter": [], "total": 0}
    }


def save_expenses(data: Dict) -> None:
    """Sparar utgifter till JSON"""
    with open(EXPENSES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_revenue() -> Dict:
    """Laddar intäkter från JSON"""
    if REVENUE_FILE.exists():
        with open(REVENUE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"intakter": [], "total": 0}


def save_revenue(data: Dict) -> None:
    """Sparar intäkter till JSON"""
    with open(REVENUE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_budget() -> Dict:
    """Laddar budget från JSON"""
    if BUDGET_FILE.exists():
        with open(BUDGET_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "Unithread": {"total": 0, "kategorier": {}},
        "Merchoteket": {"total": 0, "kategorier": {}}
    }


def save_budget(data: Dict) -> None:
    """Sparar budget till JSON"""
    with open(BUDGET_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_receipts() -> Dict:
    """Laddar kvittodata från JSON"""
    if RECEIPTS_FILE.exists():
        with open(RECEIPTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "users": [],
        "receipts": []
    }


def save_receipts(data: Dict) -> None:
    """Sparar kvittodata till JSON"""
    with open(RECEIPTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_calendar() -> Dict:
    """Laddar kalenderdata från JSON"""
    if CALENDAR_FILE.exists():
        with open(CALENDAR_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"events": []}


def save_calendar(data: Dict) -> None:
    """Sparar kalenderdata till JSON"""
    with open(CALENDAR_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_receipt_image(uploaded_file, receipt_id: str) -> str:
    """Sparar kvittobild och returnerar filnamn"""
    if uploaded_file is None:
        return None

    file_extension = uploaded_file.name.split('.')[-1]
    filename = f"{receipt_id}.{file_extension}"
    filepath = RECEIPT_IMAGES_DIR / filename

    with open(filepath, 'wb') as f:
        f.write(uploaded_file.getbuffer())

    return filename


def display_receipt_image(filename: str):
    """Visar kvittobild eller PDF"""
    if not filename:
        return

    filepath = RECEIPT_IMAGES_DIR / filename
    if not filepath.exists():
        st.warning("Kvittofil hittades inte")
        return

    file_extension = filename.split('.')[-1].lower()

    if file_extension == 'pdf':
        try:
            pdf_document = fitz.open(filepath)
            page = pdf_document[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_data = pix.tobytes("png")
            st.image(img_data, caption="Kvitto (PDF)",
                     use_container_width=True)

            if len(pdf_document) > 1:
                st.info(
                    f"📄 PDF:en innehåller {len(pdf_document)} sidor (visar sida 1)")
                if st.checkbox("Visa alla sidor", key=f"show_all_{filename}"):
                    for page_num in range(1, len(pdf_document)):
                        page = pdf_document[page_num]
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        img_data = pix.tobytes("png")
                        st.image(
                            img_data, caption=f"Sida {page_num + 1}", use_container_width=True)

            pdf_document.close()

            with open(filepath, 'rb') as f:
                st.download_button("📥 Ladda ner PDF", data=f, file_name=filename,
                                   mime="application/pdf", key=f"download_{filename}")
        except Exception as e:
            st.error(f"Kunde inte läsa PDF: {e}")
    else:
        try:
            image = Image.open(filepath)
            st.image(image, caption="Kvitto", use_container_width=True)
        except Exception as e:
            st.error(f"Kunde inte läsa bild: {e}")


# --- AI PROGNOS FUNKTIONER ---


def calculate_historical_average(data: List[Dict], months: int = 3, category: str = None) -> float:
    """Beräknar genomsnittlig utgift för senaste X månader"""
    if not data:
        return 0

    cutoff_date = (date.today() - timedelta(days=months * 30)
                   ).strftime("%Y-%m-%d")

    if category:
        filtered = [d["belopp"] for d in data if d["datum"]
                    >= cutoff_date and d.get("kategori") == category]
    else:
        filtered = [d["belopp"] for d in data if d["datum"] >= cutoff_date]

    return sum(filtered) / months if filtered else 0


def calculate_trend(data: List[Dict], months: int = 6) -> float:
    """Beräknar trend (% ökning/minskning per månad)"""
    if len(data) < 2:
        return 0

    monthly_totals = {}
    for d in data:
        month = d["datum"][:7]
        monthly_totals[month] = monthly_totals.get(month, 0) + d["belopp"]

    if len(monthly_totals) < 2:
        return 0

    sorted_months = sorted(monthly_totals.items())[-months:]
    values = [v for _, v in sorted_months]

    changes = []
    for i in range(1, len(values)):
        if values[i-1] > 0:
            change = ((values[i] - values[i-1]) / values[i-1]) * 100
            changes.append(change)

    return np.mean(changes) if changes else 0


def detect_seasonality(data: List[Dict]) -> Dict[int, float]:
    """Detekterar säsongsmönster (per månad)"""
    if not data:
        return {}

    monthly_stats = {}
    for d in data:
        month = int(d["datum"][5:7])
        if month not in monthly_stats:
            monthly_stats[month] = []
        monthly_stats[month].append(d["belopp"])

    monthly_avg = {}
    overall_avg = sum(sum(v) for v in monthly_stats.values()) / \
        sum(len(v) for v in monthly_stats.values())

    for month, values in monthly_stats.items():
        month_avg = sum(values) / len(values)
        monthly_avg[month] = ((month_avg - overall_avg) /
                              overall_avg) * 100 if overall_avg > 0 else 0

    return monthly_avg


def generate_forecast(expenses: Dict, business: str, months_ahead: int = 3, category: str = None) -> Dict:
    """Genererar prognos för framtida utgifter"""
    data = expenses[business]["utgifter"]

    if not data:
        return {
            "method": "no_data",
            "forecast": 0,
            "base": 0,
            "trend": 0,
            "seasonal_factor": 1.0,
            "confidence": "låg",
            "data_points": 0
        }

    base_forecast = calculate_historical_average(
        data, months=3, category=category)
    trend = calculate_trend(data, months=6)
    trend_adjustment = (trend / 100) * months_ahead

    seasonality = detect_seasonality(data)
    target_month = (date.today().month + months_ahead - 1) % 12 + 1
    seasonal_factor = 1 + (seasonality.get(target_month, 0) / 100)

    forecast = base_forecast * (1 + trend_adjustment) * seasonal_factor

    data_points = len([d for d in data if d["datum"] >= (
        date.today() - timedelta(days=180)).strftime("%Y-%m-%d")])
    if data_points > 50:
        confidence = "hög"
    elif data_points > 20:
        confidence = "medel"
    else:
        confidence = "låg"

    return {
        "method": "ai_trend_seasonal",
        "forecast": forecast,
        "base": base_forecast,
        "trend": trend,
        "seasonal_factor": seasonal_factor,
        "confidence": confidence,
        "data_points": data_points
    }


def generate_budget_recommendation(expenses: Dict, business: str) -> Dict:
    """Genererar budgetrekommendation baserat på AI-prognos"""
    recommendations = {}

    for category in EXPENSE_CATEGORIES:
        forecast = generate_forecast(
            expenses, business, months_ahead=1, category=category)
        margin = 0.1 if forecast["confidence"] == "hög" else 0.15 if forecast["confidence"] == "medel" else 0.2
        recommended_budget = forecast["forecast"] * (1 + margin)

        recommendations[category] = {
            "prognos": forecast["forecast"],
            "rekommenderad_budget": recommended_budget,
            "marginal": margin * 100,
            "confidence": forecast["confidence"]
        }

    return recommendations


# --- DUPLICATE DETECTION FUNCTIONS ---


def find_duplicate_expenses(expenses: Dict) -> List[Dict]:
    """Hittar dubbletter i utgifter"""
    duplicates = []

    for business in BUSINESSES:
        utgifter = expenses[business]["utgifter"]

        for i in range(len(utgifter)):
            for j in range(i + 1, len(utgifter)):
                expense1 = utgifter[i]
                expense2 = utgifter[j]

                if (expense1["datum"] == expense2["datum"] and
                    expense1["belopp"] == expense2["belopp"] and
                        expense1["leverantor"] == expense2["leverantor"]):

                    duplicates.append({
                        "business": business,
                        "original": expense1,
                        "duplicate": expense2,
                        "original_index": i,
                        "duplicate_index": j
                    })

    return duplicates


def find_duplicate_revenue(revenue: Dict) -> List[Dict]:
    """Hittar dubbletter i intäkter"""
    duplicates = []
    intakter = revenue["intakter"]

    for i in range(len(intakter)):
        for j in range(i + 1, len(intakter)):
            revenue1 = intakter[i]
            revenue2 = intakter[j]

            if (revenue1["datum"] == revenue2["datum"] and
                revenue1["belopp"] == revenue2["belopp"] and
                revenue1["kund"] == revenue2["kund"] and
                    revenue1.get("verksamhet") == revenue2.get("verksamhet")):

                duplicates.append({
                    "original": revenue1,
                    "duplicate": revenue2,
                    "original_index": i,
                    "duplicate_index": j
                })

    return duplicates


def remove_expense_by_index(expenses: Dict, business: str, index: int) -> None:
    """Tar bort utgift baserat på index"""
    del expenses[business]["utgifter"][index]
    expenses[business]["total"] = sum(u["belopp"]
                                      for u in expenses[business]["utgifter"])


def remove_revenue_by_index(revenue: Dict, index: int) -> None:
    """Tar bort intäkt baserat på index"""
    del revenue["intakter"][index]
    revenue["total"] = sum(i["belopp"] for i in revenue["intakter"])


# --- RAPPORT-FUNKTIONER ---


def generate_monthly_report(expenses: Dict, revenue: Dict, month: str, business: str = None) -> Dict:
    """Genererar månadsrapport"""
    businesses_to_include = [business] if business else BUSINESSES

    report = {
        "period": month,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "businesses": {}
    }

    for biz in businesses_to_include:
        month_expenses = [e for e in expenses[biz]
                          ["utgifter"] if e["datum"].startswith(month)]
        total_expenses = sum(e["belopp"] for e in month_expenses)

        month_revenue = [r for r in revenue["intakter"] if r["datum"].startswith(
            month) and r.get("verksamhet") == biz]
        total_revenue = sum(r["belopp"] for r in month_revenue)

        profit = total_revenue - total_expenses
        margin = (profit / total_revenue * 100) if total_revenue > 0 else 0

        category_breakdown = {}
        for cat in EXPENSE_CATEGORIES:
            cat_total = sum(e["belopp"]
                            for e in month_expenses if e["kategori"] == cat)
            if cat_total > 0:
                category_breakdown[cat] = cat_total

        report["businesses"][biz] = {
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "profit": profit,
            "margin": margin,
            "category_breakdown": category_breakdown,
            "transaction_count": len(month_expenses) + len(month_revenue)
        }

    return report


def export_to_excel(data: Dict, filename: str) -> BytesIO:
    """Exporterar data till Excel"""
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Utgifter
        for business in BUSINESSES:
            if data[business]["utgifter"]:
                df = pd.DataFrame(data[business]["utgifter"])
                df.to_excel(
                    writer, sheet_name=f"{business}_Utgifter", index=False)

        # Intäkter (om det finns)
        if "intakter" in data:
            df_revenue = pd.DataFrame(data["intakter"])
            df_revenue.to_excel(writer, sheet_name="Intakter", index=False)

    output.seek(0)
    return output


# --- STREAMLIT APP ---
st.set_page_config(page_title="Företagsekonomi AI",
                   page_icon="🏢", layout="wide")

# Check login
current_user = auth.check_login()

# Sidebar user info
st.sidebar.write(f"Inloggad som: **{current_user}**")
if st.sidebar.button("Logga ut"):
    auth.logout()

# Ladda data
expenses = load_expenses()
revenue = load_revenue()
budget = load_budget()
receipts_data = load_receipts()
calendar_data = load_calendar()

# --- SIDEBAR ---
st.sidebar.title("🏢 Företagsekonomi")
st.sidebar.markdown("---")

main_menu = st.sidebar.radio("Huvudmeny", [
    "📊 Dashboard",
    "💰 Utgifter",
    "💵 Intäkter",
    "📈 Budget & Prognos",
    "📄 Kvittoredovisning",
    "📅 Kalender",
    "💬 Chatt",
    "👥 Användare",
    "📋 Rapporter",
    "🔍 Dubbletthantering",
    "⚙️ Inställningar"
])

# --- DASHBOARD ---
if main_menu == "📊 Dashboard":
    st.title("📊 Dashboard - Företagsöversikt")

    # Custom CSS för snyggare dashboard
    st.markdown("""
        <style>
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 10px;
            color: white;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }
        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
        }
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
            margin: 10px 0;
        }
        .metric-label {
            font-size: 0.9rem;
            opacity: 0.9;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        </style>
    """, unsafe_allow_html=True)

    # Beräkna totaler
    total_expenses = sum(expenses[b]["total"] for b in BUSINESSES)
    total_revenue = revenue["total"]
    total_profit = total_revenue - total_expenses
    profit_margin = (total_profit/total_revenue *
                     100 if total_revenue > 0 else 0)

    # Snygga gradient-kort
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                <div class="metric-label">💰 Total Intäkt</div>
                <div class="metric-value">{total_revenue:,.0f} kr</div>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                <div class="metric-label">💸 Total Utgift</div>
                <div class="metric-value">{total_expenses:,.0f} kr</div>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        profit_gradient = "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)" if total_profit > 0 else "linear-gradient(135deg, #f5576c 0%, #f093fb 100%)"
        st.markdown(f"""
            <div class="metric-card" style="background: {profit_gradient};">
                <div class="metric-label">📈 Nettovinst</div>
                <div class="metric-value">{total_profit:,.0f} kr</div>
            </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
                <div class="metric-label">📊 Marginal</div>
                <div class="metric-value">{profit_margin:.1f}%</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Tabs för olika vyer
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📈 Trendanalys", "🥧 Fördelning", "📊 Jämförelse", "🎯 Budget"])

    with tab1:
        st.subheader("📈 Intäkter & Utgifter - Senaste 6 månaderna")

        # Beräkna månadsdata
        months = []
        revenue_by_month = []
        expenses_by_month = []
        profit_by_month = []

        for i in range(5, -1, -1):
            month_date = date.today() - timedelta(days=i*30)
            month = month_date.strftime("%Y-%m")
            month_name = month_date.strftime("%b %Y")
            months.append(month_name)

            month_rev = sum(i["belopp"] for i in revenue["intakter"]
                            if i["datum"].startswith(month))
            month_exp = sum(sum(u["belopp"] for u in expenses[b]["utgifter"]
                            if u["datum"].startswith(month)) for b in BUSINESSES)

            revenue_by_month.append(month_rev)
            expenses_by_month.append(month_exp)
            profit_by_month.append(month_rev - month_exp)

        # Skapa interaktiv graf
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=months,
            y=revenue_by_month,
            mode='lines+markers',
            name='Intäkter',
            line=dict(color='#667eea', width=3),
            marker=dict(size=10, symbol='circle'),
            hovertemplate='<b>%{x}</b><br>Intäkter: %{y:,.0f} kr<extra></extra>'
        ))

        fig.add_trace(go.Scatter(
            x=months,
            y=expenses_by_month,
            mode='lines+markers',
            name='Utgifter',
            line=dict(color='#f5576c', width=3),
            marker=dict(size=10, symbol='square'),
            hovertemplate='<b>%{x}</b><br>Utgifter: %{y:,.0f} kr<extra></extra>'
        ))

        fig.add_trace(go.Scatter(
            x=months,
            y=profit_by_month,
            mode='lines+markers',
            name='Vinst',
            line=dict(color='#43e97b', width=3, dash='dash'),
            marker=dict(size=10, symbol='diamond'),
            hovertemplate='<b>%{x}</b><br>Vinst: %{y:,.0f} kr<extra></extra>'
        ))

        fig.update_layout(
            title="Utveckling över tid",
            xaxis_title="Månad",
            yaxis_title="Belopp (kr)",
            hovermode='x unified',
            template="plotly_white",
            height=500,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        st.plotly_chart(fig, use_container_width=True)

        # Snabb-statistik
        col1, col2, col3 = st.columns(3)

        avg_revenue = sum(revenue_by_month) / \
            len(revenue_by_month) if revenue_by_month else 0
        avg_expenses = sum(expenses_by_month) / \
            len(expenses_by_month) if expenses_by_month else 0
        trend = ((revenue_by_month[-1] - revenue_by_month[0]) / revenue_by_month[0]
                 * 100) if revenue_by_month and revenue_by_month[0] > 0 else 0

        col1.metric("📊 Genomsnittlig intäkt/mån", f"{avg_revenue:,.0f} kr")
        col2.metric("📊 Genomsnittlig utgift/mån", f"{avg_expenses:,.0f} kr")
        col3.metric("📈 Trend (6 mån)", f"{trend:+.1f}%")

    with tab2:
        st.subheader("🥧 Utgiftsfördelning")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Per kategori")

            # Samla utgifter per kategori
            category_totals = {}
            for business in BUSINESSES:
                for utgift in expenses[business]["utgifter"]:
                    cat = utgift["kategori"]
                    category_totals[cat] = category_totals.get(
                        cat, 0) + utgift["belopp"]

            if category_totals:
                fig = px.pie(
                    values=list(category_totals.values()),
                    names=list(category_totals.keys()),
                    title="Utgifter per kategori",
                    color_discrete_sequence=px.colors.qualitative.Set3,
                    hole=0.4
                )
                fig.update_traces(textposition='inside',
                                  textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Ingen data att visa")

        with col2:
            st.markdown("#### Per verksamhet")

            business_totals = {
                business: expenses[business]["total"] for business in BUSINESSES}

            if any(business_totals.values()):
                fig = px.pie(
                    values=list(business_totals.values()),
                    names=list(business_totals.keys()),
                    title="Utgifter per verksamhet",
                    color_discrete_sequence=['#667eea', '#f5576c'],
                    hole=0.4
                )
                fig.update_traces(textposition='inside',
                                  textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Ingen data att visa")

        # Top 5 leverantörer
        st.markdown("---")
        st.markdown("#### 🏪 Top 5 Leverantörer")

        supplier_totals = {}
        for business in BUSINESSES:
            for utgift in expenses[business]["utgifter"]:
                supplier = utgift["leverantor"]
                supplier_totals[supplier] = supplier_totals.get(
                    supplier, 0) + utgift["belopp"]

        if supplier_totals:
            top_suppliers = sorted(
                supplier_totals.items(), key=lambda x: x[1], reverse=True)[:5]

            suppliers = [s[0] for s in top_suppliers]
            amounts = [s[1] for s in top_suppliers]

            fig = go.Figure(data=[go.Bar(
                x=amounts,
                y=suppliers,
                orientation='h',
                marker=dict(
                    color=amounts,
                    colorscale='Viridis',
                    showscale=False
                ),
                text=[f"{a:,.0f} kr" for a in amounts],
                textposition='auto',
            )])

            fig.update_layout(
                title="Högsta utgifter per leverantör",
                xaxis_title="Belopp (kr)",
                yaxis_title="",
                height=300,
                template="plotly_white"
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Ingen leverantörsdata att visa")

    with tab3:
        st.subheader("📊 Verksamhetsjämförelse")

        # Jämförelse Unithread vs Merchoteket
        comparison_data = []
        for business in BUSINESSES:
            business_revenue = sum(
                i["belopp"] for i in revenue["intakter"] if i.get("verksamhet") == business)
            business_expenses = expenses[business]["total"]
            business_profit = business_revenue - business_expenses

            comparison_data.append({
                "Verksamhet": business,
                "Intäkter": business_revenue,
                "Utgifter": business_expenses,
                "Vinst": business_profit
            })

        df = pd.DataFrame(comparison_data)

        # Grouped bar chart
        fig = go.Figure()

        fig.add_trace(go.Bar(
            name='Intäkter',
            x=df["Verksamhet"],
            y=df["Intäkter"],
            marker_color='#667eea',
            text=df["Intäkter"].apply(lambda x: f"{x:,.0f} kr"),
            textposition='auto',
        ))

        fig.add_trace(go.Bar(
            name='Utgifter',
            x=df["Verksamhet"],
            y=df["Utgifter"],
            marker_color='#f5576c',
            text=df["Utgifter"].apply(lambda x: f"{x:,.0f} kr"),
            textposition='auto',
        ))

        fig.add_trace(go.Bar(
            name='Vinst',
            x=df["Verksamhet"],
            y=df["Vinst"],
            marker_color='#43e97b',
            text=df["Vinst"].apply(lambda x: f"{x:,.0f} kr"),
            textposition='auto',
        ))

        fig.update_layout(
            title="Verksamhetsjämförelse",
            xaxis_title="Verksamhet",
            yaxis_title="Belopp (kr)",
            barmode='group',
            template="plotly_white",
            height=500,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        st.plotly_chart(fig, use_container_width=True)

        # Detaljerad tabell
        st.markdown("---")
        st.markdown("#### 📋 Detaljerad jämförelse")

        for business in BUSINESSES:
            with st.expander(f"🏢 {business}"):
                business_revenue = sum(
                    i["belopp"] for i in revenue["intakter"] if i.get("verksamhet") == business)
                business_expenses = expenses[business]["total"]
                business_profit = business_revenue - business_expenses
                profit_margin = (
                    business_profit / business_revenue * 100) if business_revenue > 0 else 0

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Intäkter", f"{business_revenue:,.0f} kr")
                col2.metric("Utgifter", f"{business_expenses:,.0f} kr")
                col3.metric("Vinst", f"{business_profit:,.0f} kr")
                col4.metric("Marginal", f"{profit_margin:.1f}%")

    with tab4:
        st.subheader("🎯 Budgetuppföljning")

        for business in BUSINESSES:
            st.markdown(f"### {business}")

            total_budget = budget[business].get("total", 0)
            current_expenses = expenses[business]["total"]

            if total_budget > 0:
                percentage = (current_expenses / total_budget) * 100
                remaining = total_budget - current_expenses

                # Färgkodning baserat på användning
                if percentage < 70:
                    color = "#43e97b"
                    gradient = "linear-gradient(90deg, #43e97b 0%, #38f9d7 100%)"
                    status = "🟢 Inom budget"
                    status_color = "#43e97b"
                elif percentage < 90:
                    color = "#ffbb33"
                    gradient = "linear-gradient(90deg, #ffbb33 0%, #ff8800 100%)"
                    status = "🟡 Nära budget"
                    status_color = "#ffbb33"
                else:
                    color = "#f5576c"
                    gradient = "linear-gradient(90deg, #f5576c 0%, #f093fb 100%)"
                    status = "🔴 Över budget"
                    status_color = "#f5576c"

                # Snygg progress bar med gradient
                st.markdown(f"""
                    <div style="background-color: #f0f0f0; border-radius: 10px; padding: 3px; margin: 10px 0;">
                        <div style="background: {gradient}; 
                                    width: {min(percentage, 100)}%; 
                                    border-radius: 8px; 
                                    padding: 15px; 
                                    color: white; 
                                    font-weight: bold;
                                    text-align: center;
                                    transition: width 0.5s ease;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            {percentage:.1f}% använt
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                # Statistik
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("💰 Budget", f"{total_budget:,.0f} kr")
                col2.metric("💸 Använt", f"{current_expenses:,.0f} kr")
                col3.metric("💵 Kvar", f"{max(remaining, 0):,.0f} kr",
                            delta=f"{-percentage:.1f}%" if percentage > 100 else None)
                col4.markdown(
                    f"<div style='padding: 20px; text-align: center; font-weight: bold; color: {status_color};'>{status}</div>", unsafe_allow_html=True)

                # Per kategori progress
                st.markdown("#### Budget per kategori")

                category_budget = budget[business].get("kategorier", {})
                if category_budget:
                    for kategori in EXPENSE_CATEGORIES:
                        cat_budget = category_budget.get(kategori, 0)
                        if cat_budget > 0:
                            cat_expenses = sum(
                                u["belopp"] for u in expenses[business]["utgifter"] if u["kategori"] == kategori)
                            cat_percentage = (
                                cat_expenses / cat_budget * 100) if cat_budget > 0 else 0

                            # Mini progress bar
                            if cat_percentage < 80:
                                bar_color = "#43e97b"
                            elif cat_percentage < 100:
                                bar_color = "#ffbb33"
                            else:
                                bar_color = "#f5576c"

                            with st.container():
                                col_a, col_b = st.columns([3, 1])
                                with col_a:
                                    st.markdown(f"**{kategori}**")
                                    st.markdown(f"""
                                        <div style="background-color: #f0f0f0; border-radius: 5px; padding: 2px; margin: 5px 0;">
                                            <div style="background-color: {bar_color}; 
                                                        width: {min(cat_percentage, 100)}%; 
                                                        border-radius: 3px; 
                                                        padding: 5px; 
                                                        color: white; 
                                                        font-size: 0.8rem;
                                                        text-align: center;">
                                                {cat_percentage:.0f}%
                                            </div>
                                        </div>
                                    """, unsafe_allow_html=True)
                                with col_b:
                                    st.caption(
                                        f"{cat_expenses:,.0f} / {cat_budget:,.0f} kr")
                else:
                    st.info("Ingen kategoribudget satt")
            else:
                st.warning("⚠️ Ingen budget satt för denna verksamhet")
                if st.button(f"➕ Sätt budget för {business}", key=f"set_budget_{business}"):
                    st.info("Gå till 'Budget & Prognos' för att sätta budget")

            st.markdown("---")

    st.markdown("---")

    # AI Prognos
    st.subheader("🤖 AI-Prognos: Nästa månad")

    col1, col2 = st.columns(2)
    for idx, business in enumerate(BUSINESSES):
        with [col1, col2][idx]:
            forecast = generate_forecast(expenses, business, months_ahead=1)

            st.markdown(f"#### {business}")

            col_a, col_b = st.columns(2)
            col_a.metric("Prognostiserad utgift",
                         f"{forecast['forecast']:,.0f} kr")
            col_b.metric("Trend", f"{forecast['trend']:+.1f}%/mån")

            st.caption(
                f"Confidence: {forecast['confidence'].upper()} | {forecast['data_points']} datapunkter")

            # Varning om stor ökning
            if forecast['trend'] > 10:
                st.error(
                    f"⚠️ Utgifterna ökar med {forecast['trend']:.1f}% per månad")
            elif forecast['trend'] > 5:
                st.warning(
                    f"⚠️ Utgifterna ökar med {forecast['trend']:.1f}% per månad")
            elif forecast['trend'] < -5:
                st.success(
                    f"✅ Utgifterna minskar med {abs(forecast['trend']):.1f}% per månad")

# --- UTGIFTER ---
elif main_menu == "💰 Utgifter":
    st.title("💰 Utgifter")

    tab1, tab2 = st.tabs(["📝 Registrera", "📋 Visa"])

    with tab1:
        st.subheader("Registrera ny utgift")

        with st.form("expense_form"):
            col1, col2 = st.columns(2)

            with col1:
                verksamhet = st.selectbox("🏢 Verksamhet", BUSINESSES)
                kategori = st.selectbox("📁 Kategori", EXPENSE_CATEGORIES)
                beskrivning = st.text_input("📝 Beskrivning")

            with col2:
                leverantor = st.text_input("🏪 Leverantör")
                belopp = st.number_input(
                    "💰 Belopp (kr)", min_value=0.0, step=0.01, format="%.2f")

            submitted = st.form_submit_button("💾 Registrera", type="primary")

            if submitted and beskrivning and leverantor and belopp > 0:
                utgift = {
                    "datum": datetime.now().strftime("%Y-%m-%d"),
                    "kategori": kategori,
                    "beskrivning": beskrivning,
                    "leverantor": leverantor,
                    "belopp": belopp
                }
                expenses[verksamhet]["utgifter"].append(utgift)
                expenses[verksamhet]["total"] = sum(
                    u["belopp"] for u in expenses[verksamhet]["utgifter"])
                save_expenses(expenses)
                st.success(
                    f"✅ Utgift på {belopp:,.2f} kr registrerad för {verksamhet}!")
                st.rerun()

    with tab2:
        st.subheader("Visa utgifter")

        view_business = st.selectbox("Verksamhet", ["Alla"] + BUSINESSES)
        filter_month = st.date_input(
            "Månad", value=date.today()).strftime("%Y-%m")

        businesses_to_show = BUSINESSES if view_business == "Alla" else [
            view_business]

        for business in businesses_to_show:
            st.markdown(f"### {business}")

            filtered = [u for u in expenses[business]["utgifter"]
                        if u["datum"].startswith(filter_month)]

            if filtered:
                total = sum(u["belopp"] for u in filtered)
                st.metric(f"Total ({filter_month})", f"{total:,.2f} kr")

                df = pd.DataFrame(filtered)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Inga utgifter för vald period")

# --- INTÄKTER ---
elif main_menu == "💵 Intäkter":
    st.title("💵 Intäkter")

    tab1, tab2 = st.tabs(["📝 Registrera", "📋 Visa"])

    with tab1:
        st.subheader("Registrera ny intäkt")

        with st.form("revenue_form"):
            col1, col2 = st.columns(2)

            with col1:
                verksamhet = st.selectbox("🏢 Verksamhet", BUSINESSES)
                kategori = st.selectbox("📁 Kategori", REVENUE_CATEGORIES)
                beskrivning = st.text_input("📝 Beskrivning")

            with col2:
                kund = st.text_input("👤 Kund")
                belopp = st.number_input(
                    "💰 Belopp (kr)", min_value=0.0, step=0.01, format="%.2f")

            submitted = st.form_submit_button("💾 Registrera", type="primary")

            if submitted and beskrivning and kund and belopp > 0:
                intakt = {
                    "datum": datetime.now().strftime("%Y-%m-%d"),
                    "verksamhet": verksamhet,
                    "kategori": kategori,
                    "beskrivning": beskrivning,
                    "kund": kund,
                    "belopp": belopp
                }
                revenue["intakter"].append(intakt)
                revenue["total"] = sum(i["belopp"]
                                       for i in revenue["intakter"])
                save_revenue(revenue)
                st.success(
                    f"✅ Intäkt på {belopp:,.2f} kr registrerad för {verksamhet}!")
                st.rerun()

    with tab2:
        st.subheader("Visa intäkter")

        view_business = st.selectbox(
            "Verksamhet", ["Alla"] + BUSINESSES, key="revenue_view")
        filter_month = st.date_input(
            "Månad", value=date.today(), key="revenue_month").strftime("%Y-%m")

        if view_business == "Alla":
            filtered = [i for i in revenue["intakter"]
                        if i["datum"].startswith(filter_month)]
        else:
            filtered = [i for i in revenue["intakter"] if i["datum"].startswith(
                filter_month) and i.get("verksamhet") == view_business]

        if filtered:
            total = sum(i["belopp"] for i in filtered)
            st.metric(f"Total ({filter_month})", f"{total:,.2f} kr")

            df = pd.DataFrame(filtered)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Inga intäkter för vald period")

# --- BUDGET & PROGNOS ---
elif main_menu == "📈 Budget & Prognos":
    st.title("📈 Budget & Prognos")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["💳 Sätt Budget", "🤖 AI-Prognos", "📊 Jämför", "💡 Rekommendationer"])

    with tab1:
        st.subheader("Sätt månadsbudget")

        business = st.selectbox("Välj verksamhet", BUSINESSES)

        st.markdown("### Total budget")
        total_budget = st.number_input("Total månadsbudget (kr)", min_value=0.0, value=float(
            budget[business].get("total", 0)), step=1000.0)
        budget[business]["total"] = total_budget

        st.markdown("### Budget per kategori")

        if "kategorier" not in budget[business]:
            budget[business]["kategorier"] = {}

        allocated = 0
        for kategori in EXPENSE_CATEGORIES:
            current = budget[business]["kategorier"].get(kategori, 0)
            new_budget = st.number_input(f"{kategori}", min_value=0.0, value=float(
                current), step=100.0, key=f"budget_{business}_{kategori}")
            budget[business]["kategorier"][kategori] = new_budget
            allocated += new_budget

        remaining = total_budget - allocated

        col1, col2, col3 = st.columns(3)
        col1.metric("Total budget", f"{total_budget:,.2f} kr")
        col2.metric("Fördelat", f"{allocated:,.2f} kr")

        if remaining < 0:
            col3.metric("Överallokerat", f"{abs(remaining):,.2f} kr")
            st.error("⚠️ Du har överallokerat budgeten!")
        else:
            col3.metric("Kvar", f"{remaining:,.2f} kr")

        if st.button("💾 Spara budget", type="primary"):
            save_budget(budget)
            st.success("✅ Budget sparad!")
            st.rerun()

    with tab2:
        st.subheader("🤖 AI-Prognos")

        business = st.selectbox(
            "Välj verksamhet", BUSINESSES, key="prognos_business")
        months_ahead = st.slider("Prognos för antal månader framåt", 1, 12, 3)

        if st.button("🔮 Generera prognos", type="primary"):
            forecast = generate_forecast(
                expenses, business, months_ahead=months_ahead)

            st.markdown("---")
            st.markdown(
                f"### Prognos för {business} - {months_ahead} månad(er) framåt")

            col1, col2, col3 = st.columns(3)
            col1.metric("Prognostiserad utgift",
                        f"{forecast['forecast']:,.2f} kr")
            col2.metric("Trend", f"{forecast['trend']:+.1f}% per månad")
            col3.metric("Confidence", forecast['confidence'].upper())

            st.markdown("---")
            st.markdown("### Detaljer")
            st.write(
                f"**Basutgift (senaste 3 mån):** {forecast['base']:,.2f} kr")
            st.write(f"**Säsongsfaktor:** {forecast['seasonal_factor']:.2f}x")
            st.write(
                f"**Datapunkter:** {forecast['data_points']} st (senaste 6 mån)")

            if forecast['trend'] > 15:
                st.error(
                    f"⚠️ **VARNING:** Utgifterna ökar kraftigt med {forecast['trend']:.1f}% per månad!")
            elif forecast['trend'] > 5:
                st.warning(
                    f"⚠️ Utgifterna ökar med {forecast['trend']:.1f}% per månad")
            elif forecast['trend'] < -5:
                st.success(
                    f"✅ Utgifterna minskar med {abs(forecast['trend']):.1f}% per månad")

            # Per kategori
            st.markdown("---")
            st.markdown("### Prognos per kategori")

            for kategori in EXPENSE_CATEGORIES:
                cat_forecast = generate_forecast(
                    expenses, business, months_ahead=months_ahead, category=kategori)
                if cat_forecast['forecast'] > 0:
                    with st.expander(f"📁 {kategori} - {cat_forecast['forecast']:,.2f} kr"):
                        st.write(
                            f"**Prognos:** {cat_forecast['forecast']:,.2f} kr")
                        st.write(f"**Trend:** {cat_forecast['trend']:+.1f}%")
                        st.write(
                            f"**Confidence:** {cat_forecast['confidence']}")

    with tab3:
        st.subheader("📊 Jämför perioder")

        col1, col2 = st.columns(2)
        with col1:
            period1 = st.date_input(
                "Period 1", value=date.today() - timedelta(days=30)).strftime("%Y-%m")
        with col2:
            period2 = st.date_input(
                "Period 2", value=date.today()).strftime("%Y-%m")

        if st.button("📊 Jämför", type="primary"):
            comparison_data = []

            for business in BUSINESSES:
                period1_expenses = sum(
                    u["belopp"] for u in expenses[business]["utgifter"] if u["datum"].startswith(period1))
                period2_expenses = sum(
                    u["belopp"] for u in expenses[business]["utgifter"] if u["datum"].startswith(period2))
                change = period2_expenses - period1_expenses
                change_pct = (change / period1_expenses *
                              100) if period1_expenses > 0 else 0

                comparison_data.append({
                    "Verksamhet": business,
                    period1: f"{period1_expenses:,.2f} kr",
                    period2: f"{period2_expenses:,.2f} kr",
                    "Förändring": f"{change:+,.2f} kr ({change_pct:+.1f}%)"
                })

            df = pd.DataFrame(comparison_data)
            st.dataframe(df, use_container_width=True)

    with tab4:
        st.subheader("💡 AI-Budget-rekommendationer")

        business = st.selectbox(
            "Välj verksamhet", BUSINESSES, key="rec_business")

        if st.button("💡 Generera rekommendationer", type="primary"):
            recommendations = generate_budget_recommendation(
                expenses, business)

            st.markdown(f"### Budgetrekommendationer för {business}")
            st.info(
                "Baserat på historisk data, trend och säsongsmönster + säkerhetsmarginal")

            total_recommended = sum(r["rekommenderad_budget"]
                                    for r in recommendations.values())
            st.metric("Total rekommenderad månadsbudget",
                      f"{total_recommended:,.2f} kr")

            st.markdown("---")

            for kategori, rec in recommendations.items():
                if rec["prognos"] > 0:
                    with st.expander(f"📁 {kategori} - Rekommenderad: {rec['rekommenderad_budget']:,.2f} kr"):
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Prognos", f"{rec['prognos']:,.2f} kr")
                        col2.metric("Marginal", f"{rec['marginal']:.0f}%")
                        col3.metric("Confidence", rec['confidence'].upper())

                        st.write(
                            f"**Rekommenderad budget:** {rec['rekommenderad_budget']:,.2f} kr")

# --- KVITTOREDOVISNING ---
elif main_menu == "📄 Kvittoredovisning":
    st.title("📄 Kvittoredovisning")

    receipts_data = load_receipts()

    # Välj roll
    user_role = st.sidebar.selectbox("Välj roll", ["Admin", "Användare"])

    if user_role == "Admin":
        # Kräv lösenord för admin
        if not check_admin_password():
            st.stop()

        # Logout-knapp i sidebar
        if st.sidebar.button("🚪 Logga ut", key="admin_logout"):
            admin_logout()

        st.sidebar.markdown("---")
        st.sidebar.success(f"✅ Inloggad som: **{ADMIN_USERNAME}**")

        admin_tab = st.sidebar.selectbox("Admin-meny", [
            "👥 Hantera Användare",
            "✅ Granska Kvitton",
            "📊 Översikt"
        ])

        # --- HANTERA ANVÄNDARE ---
        if admin_tab == "👥 Hantera Användare":
            st.subheader("👥 Hantera användare")

            tab1, tab2 = st.tabs(["➕ Lägg till", "📋 Lista"])

            with tab1:
                st.markdown("### ➕ Lägg till ny användare")

                with st.form("add_user_form"):
                    col1, col2 = st.columns(2)

                    with col1:
                        new_username = st.text_input(
                            "👤 Användarnamn", placeholder="t.ex. Viktor")
                        new_email = st.text_input(
                            "📧 E-post", placeholder="t.ex. viktor@exempel.se")

                    with col2:
                        new_role = st.selectbox(
                            "🏢 Roll", ["Anställd", "Konsult", "Partner"])
                        new_business = st.selectbox("🏢 Verksamhet", BUSINESSES)

                    submitted = st.form_submit_button(
                        "✅ Skapa användare", type="primary")

                    if submitted and new_username and new_email:
                        # Kolla om användare redan finns
                        if any(u["username"] == new_username for u in receipts_data["users"]):
                            st.error(
                                f"❌ Användare '{new_username}' finns redan!")
                        else:
                            user = {
                                "id": len(receipts_data["users"]) + 1,
                                "username": new_username,
                                "email": new_email,
                                "role": new_role,
                                "business": new_business,
                                "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            receipts_data["users"].append(user)
                            save_receipts(receipts_data)
                            st.success(f"✅ Användare '{new_username}' skapad!")
                            st.rerun()

            with tab2:
                st.markdown("### 📋 Registrerade användare")

                if not receipts_data["users"]:
                    st.info("Inga användare registrerade än")
                else:
                    for user in receipts_data["users"]:
                        with st.expander(f"👤 {user['username']} ({user['role']})"):
                            col1, col2 = st.columns(2)
                            col1.write(f"**E-post:** {user['email']}")
                            col2.write(f"**Verksamhet:** {user['business']}")
                            col1.write(f"**Roll:** {user['role']}")
                            col2.write(f"**Skapad:** {user['created']}")

                            # Statistik
                            user_receipts = [
                                r for r in receipts_data["receipts"] if r["user_id"] == user["id"]]
                            pending = len(
                                [r for r in user_receipts if r["status"] == "pending"])
                            approved = len(
                                [r for r in user_receipts if r["status"] == "approved"])
                            rejected = len(
                                [r for r in user_receipts if r["status"] == "rejected"])

                            st.markdown("---")
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Väntande", pending)
                            col2.metric("Godkända", approved)
                            col3.metric("Avslagna", rejected)

                            if st.button(f"🗑️ Ta bort användare", key=f"del_user_{user['id']}"):
                                receipts_data["users"] = [
                                    u for u in receipts_data["users"] if u["id"] != user["id"]]
                                save_receipts(receipts_data)
                                st.success("✅ Användare borttagen!")
                                st.rerun()

        # --- GRANSKA KVITTON ---
        elif admin_tab == "✅ Granska Kvitton":
            st.subheader("✅ Granska kvitton")

            tab1, tab2, tab3 = st.tabs(
                ["⏳ Väntande", "✅ Godkända", "❌ Avslagna"])

            with tab1:
                pending_receipts = [
                    r for r in receipts_data["receipts"] if r["status"] == "pending"]

                if not pending_receipts:
                    st.info("Inga kvitton väntar på godkännande")
                else:
                    st.write(
                        f"**{len(pending_receipts)} kvitton väntar på godkännande**")

                    for receipt in pending_receipts:
                        user = next(
                            (u for u in receipts_data["users"] if u["id"] == receipt["user_id"]), None)

                        with st.expander(f"🧾 {receipt['beskrivning']} - {receipt['belopp']:,.2f} kr ({user['username'] if user else 'Okänd'})"):
                            col1, col2 = st.columns([2, 1])

                            with col1:
                                st.write(
                                    f"**Användare:** {user['username'] if user else 'Okänd'}")
                                st.write(
                                    f"**Verksamhet:** {receipt['business']}")
                                st.write(
                                    f"**Kategori:** {receipt['kategori']}")
                                st.write(
                                    f"**Beskrivning:** {receipt['beskrivning']}")
                                st.write(
                                    f"**Leverantör:** {receipt['leverantor']}")
                                st.write(
                                    f"**Belopp:** {receipt['belopp']:,.2f} kr")
                                st.write(f"**Datum:** {receipt['datum']}")
                                st.write(
                                    f"**Inlämnad:** {receipt['submitted']}")

                                col_a, col_b = st.columns(2)

                                if col_a.button(f"✅ Godkänn", key=f"approve_{receipt['id']}", type="primary"):
                                    # Godkänn kvitto
                                    for r in receipts_data["receipts"]:
                                        if r["id"] == receipt["id"]:
                                            r["status"] = "approved"
                                            r["reviewed_date"] = datetime.now().strftime(
                                                "%Y-%m-%d %H:%M:%S")

                                    # Lägg till i företagets utgifter
                                    utgift = {
                                        "datum": receipt["datum"],
                                        "kategori": receipt["kategori"],
                                        "beskrivning": f"{receipt['beskrivning']} (från {user['username']})",
                                        "leverantor": receipt["leverantor"],
                                        "belopp": receipt["belopp"]
                                    }
                                    expenses[receipt["business"]
                                             ]["utgifter"].append(utgift)
                                    expenses[receipt["business"]
                                             ]["total"] += receipt["belopp"]

                                    save_receipts(receipts_data)
                                    save_expenses(expenses)

                                    st.success(
                                        "✅ Kvitto godkänt och tillagt i utgifter!")
                                    st.rerun()

                                if col_b.button(f"❌ Avslå", key=f"reject_{receipt['id']}", type="secondary"):
                                    for r in receipts_data["receipts"]:
                                        if r["id"] == receipt["id"]:
                                            r["status"] = "rejected"
                                            r["reviewed_date"] = datetime.now().strftime(
                                                "%Y-%m-%d %H:%M:%S")

                                    save_receipts(receipts_data)
                                    st.warning("❌ Kvitto avslaget")
                                    st.rerun()

                            with col2:
                                if receipt.get("image"):
                                    display_receipt_image(receipt["image"])

            with tab2:
                approved = [r for r in receipts_data["receipts"]
                            if r["status"] == "approved"]
                if approved:
                    df = pd.DataFrame([{
                        "Användare": next((u["username"] for u in receipts_data["users"] if u["id"] == r["user_id"]), "Okänd"),
                        "Verksamhet": r["business"],
                        "Beskrivning": r["beskrivning"],
                        "Belopp": f"{r['belopp']:,.2f} kr",
                        "Datum": r["datum"],
                        "Godkänd": r.get("reviewed_date", "N/A")
                    } for r in approved])
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("Inga godkända kvitton")

            with tab3:
                rejected = [r for r in receipts_data["receipts"]
                            if r["status"] == "rejected"]
                if rejected:
                    df = pd.DataFrame([{
                        "Användare": next((u["username"] for u in receipts_data["users"] if u["id"] == r["user_id"]), "Okänd"),
                        "Verksamhet": r["business"],
                        "Beskrivning": r["beskrivning"],
                        "Belopp": f"{r['belopp']:,.2f} kr",
                        "Datum": r["datum"],
                        "Avslagen": r.get("reviewed_date", "N/A")
                    } for r in rejected])
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("Inga avslagna kvitton")

        # --- ÖVERSIKT ---
        elif admin_tab == "📊 Översikt":
            st.subheader("📊 Kvittoöversikt")

            total_pending = len(
                [r for r in receipts_data["receipts"] if r["status"] == "pending"])
            total_approved = len(
                [r for r in receipts_data["receipts"] if r["status"] == "approved"])
            total_rejected = len(
                [r for r in receipts_data["receipts"] if r["status"] == "rejected"])

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("👥 Användare", len(receipts_data["users"]))
            col2.metric("⏳ Väntande", total_pending)
            col3.metric("✅ Godkända", total_approved)
            col4.metric("❌ Avslagna", total_rejected)

            st.markdown("---")

            # Per verksamhet
            for business in BUSINESSES:
                business_receipts = [r for r in receipts_data["receipts"]
                                     if r["business"] == business and r["status"] == "approved"]
                total_amount = sum(r["belopp"] for r in business_receipts)

                st.markdown(f"### {business}")
                col1, col2 = st.columns(2)
                col1.metric("Antal godkända kvitton", len(business_receipts))
                col2.metric("Total summa", f"{total_amount:,.2f} kr")

    # --- ANVÄNDARE ---
    else:
        if not receipts_data["users"]:
            st.warning("Inga användare registrerade än. Kontakta admin.")
        else:
            selected_user = st.sidebar.selectbox(
                "Välj användare",
                receipts_data["users"],
                format_func=lambda u: f"{u['username']} ({u['role']})"
            )

            user_tab = st.sidebar.selectbox("Meny", [
                "📤 Ladda upp kvitto",
                "📋 Mina kvitton"
            ])

            # --- LADDA UPP KVITTO ---
            if user_tab == "📤 Ladda upp kvitto":
                st.subheader(
                    f"📤 Ladda upp kvitto ({selected_user['username']})")

                with st.form("upload_receipt_form"):
                    col1, col2 = st.columns(2)

                    with col1:
                        business = st.selectbox(
                            "🏢 Verksamhet", BUSINESSES, index=BUSINESSES.index(selected_user["business"]))
                        kategori = st.selectbox(
                            "📁 Kategori", EXPENSE_CATEGORIES)
                        beskrivning = st.text_input(
                            "📝 Beskrivning", placeholder="t.ex. Möte med kund")

                    with col2:
                        leverantor = st.text_input(
                            "🏪 Leverantör", placeholder="t.ex. Restaurang X")
                        belopp = st.number_input(
                            "💰 Belopp (kr)", min_value=0.0, step=0.01, format="%.2f")
                        receipt_date = st.date_input(
                            "📅 Kvittodatum", value=date.today())

                    uploaded_image = st.file_uploader("📷 Ladda upp kvittobild", type=[
                                                      "jpg", "jpeg", "png", "pdf"])

                    submitted = st.form_submit_button(
                        "📤 Skicka in kvitto", type="primary")

                    if submitted and beskrivning and leverantor and belopp > 0:
                        receipt_id = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{selected_user['id']}"
                        image_filename = save_receipt_image(
                            uploaded_image, receipt_id) if uploaded_image else None

                        receipt = {
                            "id": receipt_id,
                            "user_id": selected_user["id"],
                            "business": business,
                            "kategori": kategori,
                            "beskrivning": beskrivning,
                            "leverantor": leverantor,
                            "belopp": belopp,
                            "datum": receipt_date.strftime("%Y-%m-%d"),
                            "submitted": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "status": "pending",
                            "image": image_filename
                        }

                        receipts_data["receipts"].append(receipt)
                        save_receipts(receipts_data)

                        st.success(
                            f"✅ Kvitto på {belopp:,.2f} kr skickat för godkännande!")
                        st.balloons()
                        st.rerun()

            # --- MINA KVITTON ---
            elif user_tab == "📋 Mina kvitton":
                st.subheader(f"📋 Mina kvitton ({selected_user['username']})")

                user_receipts = [r for r in receipts_data["receipts"]
                                 if r["user_id"] == selected_user["id"]]

                if not user_receipts:
                    st.info("Du har inga inlämnade kvitton än")
                else:
                    tab1, tab2, tab3 = st.tabs(
                        ["⏳ Väntande", "✅ Godkända", "❌ Avslagna"])

                    with tab1:
                        pending = [
                            r for r in user_receipts if r["status"] == "pending"]
                        if pending:
                            for r in pending:
                                with st.expander(f"🧾 {r['beskrivning']} - {r['belopp']:,.2f} kr"):
                                    col1, col2 = st.columns([2, 1])
                                    with col1:
                                        st.write(
                                            f"**Kategori:** {r['kategori']}")
                                        st.write(
                                            f"**Leverantör:** {r['leverantor']}")
                                        st.write(
                                            f"**Belopp:** {r['belopp']:,.2f} kr")
                                        st.write(
                                            f"**Inlämnad:** {r['submitted']}")
                                    with col2:
                                        if r.get("image"):
                                            display_receipt_image(r["image"])
                        else:
                            st.info("Inga väntande kvitton")

                    with tab2:
                        approved = [
                            r for r in user_receipts if r["status"] == "approved"]
                        if approved:
                            total = sum(r["belopp"] for r in approved)
                            st.metric("Total godkänd summa",
                                      f"{total:,.2f} kr")
                            df = pd.DataFrame([{
                                "Beskrivning": r["beskrivning"],
                                "Belopp": f"{r['belopp']:,.2f} kr",
                                "Datum": r["datum"],
                                "Godkänd": r.get("reviewed_date", "N/A")
                            } for r in approved])
                            st.dataframe(df, use_container_width=True)
                        else:
                            st.info("Inga godkända kvitton")

                    with tab3:
                        rejected = [
                            r for r in user_receipts if r["status"] == "rejected"]
                        if rejected:
                            df = pd.DataFrame([{
                                "Beskrivning": r["beskrivning"],
                                "Belopp": f"{r['belopp']:,.2f} kr",
                                "Datum": r["datum"],
                                "Avslagen": r.get("reviewed_date", "N/A")
                            } for r in rejected])
                            st.dataframe(df, use_container_width=True)
                        else:
                            st.info("Inga avslagna kvitton")

# --- KALENDER ---
elif main_menu == "📅 Kalender":
    st.title("📅 Kalender & Viktiga datum")

    # Custom CSS för snyggare kalender
    st.markdown("""
        <style>
        .calendar-day {
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            min-height: 80px;
            border: 1px solid #e0e0e0;
        }
        .calendar-day-today {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: bold;
        }
        .calendar-day-event {
            background-color: #f0f8ff;
            border: 2px solid #4a90e2;
        }
        .event-badge {
            font-size: 0.75rem;
            padding: 2px 6px;
            border-radius: 4px;
            display: inline-block;
            margin-top: 4px;
        }
        </style>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(
        ["📅 Månadsbild", "📝 Hantera händelser", "📋 Händelselista"])

    with tab1:
        # Header med navigering
        col1, col2, col3 = st.columns([1, 3, 1])

        with col2:
            month_year_col1, month_year_col2 = st.columns(2)
            with month_year_col1:
                selected_month = st.selectbox("📆 Månad", [
                    "Januari", "Februari", "Mars", "April", "Maj", "Juni",
                    "Juli", "Augusti", "September", "Oktober", "November", "December"
                ], index=date.today().month - 1, label_visibility="collapsed")

            with month_year_col2:
                selected_year = st.number_input(
                    "År",
                    min_value=2020,
                    max_value=2035,
                    value=date.today().year,
                    label_visibility="collapsed"
                )

        # Konvertera månad till nummer
        month_num = ["Januari", "Februari", "Mars", "April", "Maj", "Juni",
                     "Juli", "Augusti", "September", "Oktober", "November", "December"].index(selected_month) + 1

        # Skapa kalender
        cal = calendar.monthcalendar(selected_year, month_num)

        # Hämta händelser för vald månad
        month_str = f"{selected_year}-{month_num:02d}"
        month_events = [e for e in calendar_data["events"]
                        if e["datum"].startswith(month_str)]

        # Skapa dict med datum som nyckel (stöd för flera händelser per dag)
        events_by_date = {}
        for event in month_events:
            if event["datum"] not in events_by_date:
                events_by_date[event["datum"]] = []
            events_by_date[event["datum"]].append(event)

        # Visa månadens namn stor och fin
        st.markdown(
            f"<h2 style='text-align: center; color: #667eea;'>{selected_month} {selected_year}</h2>", unsafe_allow_html=True)

        st.markdown("---")

        # Veckodagar header
        weekdays = ["Måndag", "Tisdag", "Onsdag",
                    "Torsdag", "Fredag", "Lördag", "Söndag"]
        cols = st.columns(7)
        for i, day in enumerate(weekdays):
            with cols[i]:
                st.markdown(
                    f"<div style='text-align: center; font-weight: bold; color: #667eea; padding: 10px;'>{day[:3]}</div>", unsafe_allow_html=True)

        # Visa datum
        for week_idx, week in enumerate(cal):
            cols = st.columns(7)
            for day_idx, day in enumerate(week):
                with cols[day_idx]:
                    if day == 0:
                        st.write("")
                    else:
                        date_str = f"{selected_year}-{month_num:02d}-{day:02d}"
                        is_today = date_str == date.today().strftime("%Y-%m-%d")

                        # Container för dagen
                        if is_today:
                            st.markdown(
                                f"<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 8px; border-radius: 8px; text-align: center; min-height: 70px;'>", unsafe_allow_html=True)
                            st.markdown(
                                f"<div style='font-size: 1.5rem; font-weight: bold;'>{day}</div>", unsafe_allow_html=True)
                            st.markdown(
                                "<div style='font-size: 0.7rem;'>IDAG</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(
                                f"<div style='padding: 8px; border-radius: 8px; text-align: center; min-height: 70px; border: 1px solid #e0e0e0;'>", unsafe_allow_html=True)
                            st.markdown(
                                f"<div style='font-size: 1.2rem; font-weight: bold;'>{day}</div>", unsafe_allow_html=True)

                        # Visa händelser för dagen
                        if date_str in events_by_date:
                            # Max 2 händelser per dag i vyn
                            for event in events_by_date[date_str][:2]:
                                # Färgkodning
                                if event["typ"] == "Faktura förfaller":
                                    badge_color = "#ff4444"
                                    icon = "💸"
                                elif event["typ"] == "Möte":
                                    badge_color = "#ffbb33"
                                    icon = "👥"
                                elif event["typ"] == "Deadline":
                                    badge_color = "#ff8800"
                                    icon = "⏰"
                                elif event["typ"] == "Betalning":
                                    badge_color = "#00C851"
                                    icon = "💰"
                                elif event["typ"] == "Moms":
                                    badge_color = "#aa66cc"
                                    icon = "📋"
                                else:
                                    badge_color = "#33b5e5"
                                    icon = "📌"

                                st.markdown(
                                    f"<div style='background-color: {badge_color}; color: white; font-size: 0.65rem; padding: 3px 6px; border-radius: 4px; margin-top: 4px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;'>"
                                    f"{icon} {event['titel'][:12]}"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )

                            # Om fler än 2 händelser
                            if len(events_by_date[date_str]) > 2:
                                st.markdown(
                                    f"<div style='font-size: 0.6rem; color: #666; margin-top: 2px;'>+{len(events_by_date[date_str]) - 2} fler</div>",
                                    unsafe_allow_html=True
                                )

                        st.markdown("</div>", unsafe_allow_html=True)

        # Legend
        st.markdown("---")
        st.markdown("### 🏷️ Färgkodning")

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.markdown("💸 **Faktura**")
        col2.markdown("👥 **Möte**")
        col3.markdown("⏰ **Deadline**")
        col4.markdown("💰 **Betalning**")
        col5.markdown("📋 **Moms**")
        col6.markdown("📌 **Övrigt**")

    with tab2:
        st.subheader("📝 Lägg till ny händelse")

        with st.form("calendar_event_form", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                event_date = st.date_input("📅 Datum", value=date.today())
                event_title = st.text_input(
                    "📌 Titel *", placeholder="t.ex. Möte med kund")
                event_type = st.selectbox("🏷️ Typ *", [
                    "Faktura förfaller",
                    "Möte",
                    "Deadline",
                    "Betalning",
                    "Bokslut",
                    "Skatteinbetalning",
                    "Moms",
                    "Lönehantering",
                    "Revision",
                    "Övrigt"
                ])

            with col2:
                event_business = st.selectbox(
                    "🏢 Verksamhet", ["Alla"] + BUSINESSES)
                event_time = st.time_input("🕐 Tid (valfri)", value=None)
                event_priority = st.select_slider(
                    "⭐ Prioritet", options=["Låg", "Medel", "Hög"], value="Medel")

            event_description = st.text_area(
                "📝 Beskrivning (valfri)", placeholder="Lägg till detaljer om händelsen...")
            event_reminder = st.checkbox("🔔 Påminnelse (kommande funktion)")

            col_submit, col_clear = st.columns([3, 1])
            with col_submit:
                submitted = st.form_submit_button(
                    "💾 Lägg till händelse", type="primary", use_container_width=True)
            with col_clear:
                cleared = st.form_submit_button(
                    "🗑️ Rensa", use_container_width=True)

            if submitted and event_title:
                event = {
                    "id": len(calendar_data["events"]) + 1,
                    "datum": event_date.strftime("%Y-%m-%d"),
                    "tid": event_time.strftime("%H:%M") if event_time else None,
                    "titel": event_title,
                    "typ": event_type,
                    "verksamhet": event_business,
                    "prioritet": event_priority,
                    "beskrivning": event_description,
                    "reminder": event_reminder,
                    "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                calendar_data["events"].append(event)
                save_calendar(calendar_data)

                st.success(
                    f"✅ Händelse '{event_title}' tillagd för {event_date.strftime('%Y-%m-%d')}!")
                st.balloons()
                st.rerun()

    with tab3:
        st.subheader("📋 Alla händelser")

        # Avancerade filter
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            filter_business = st.selectbox(
                "🏢 Verksamhet", ["Alla"] + BUSINESSES, key="filter_business")
        with col2:
            filter_type = st.selectbox("🏷️ Typ", ["Alla"] + [
                "Faktura förfaller", "Möte", "Deadline", "Betalning", "Bokslut",
                "Skatteinbetalning", "Moms", "Lönehantering", "Revision", "Övrigt"
            ], key="filter_type")
        with col3:
            filter_priority = st.selectbox(
                "⭐ Prioritet", ["Alla", "Låg", "Medel", "Hög"], key="filter_priority")
        with col4:
            show_past = st.checkbox("📅 Visa tidigare", value=False)

        # Filtrera händelser
        filtered_events = calendar_data["events"].copy()

        if filter_business != "Alla":
            filtered_events = [e for e in filtered_events if e.get("verksamhet") in [
                filter_business, "Alla"]]

        if filter_type != "Alla":
            filtered_events = [
                e for e in filtered_events if e["typ"] == filter_type]

        if filter_priority != "Alla":
            filtered_events = [e for e in filtered_events if e.get(
                "prioritet", "Medel") == filter_priority]

        if not show_past:
            today = date.today().strftime("%Y-%m-%d")
            filtered_events = [
                e for e in filtered_events if e["datum"] >= today]

        # Sortera efter datum
        filtered_events.sort(key=lambda x: x["datum"])

        if not filtered_events:
            st.info("Inga händelser att visa med valda filter")
        else:
            st.metric("📊 Antal händelser", len(filtered_events))
            st.markdown("---")

            # Gruppera per månad
            events_by_month = {}
            for event in filtered_events:
                month = event["datum"][:7]  # YYYY-MM
                if month not in events_by_month:
                    events_by_month[month] = []
                events_by_month[month].append(event)

            # Visa per månad
            for month, events in sorted(events_by_month.items()):
                month_name = datetime.strptime(
                    month, "%Y-%m").strftime("%B %Y")

                with st.expander(f"📅 **{month_name}** ({len(events)} händelse{'r' if len(events) > 1 else ''})", expanded=True):
                    for event in events:
                        # Färgikon baserat på typ
                        icon_map = {
                            "Faktura förfaller": "💸",
                            "Möte": "👥",
                            "Deadline": "⏰",
                            "Betalning": "💰",
                            "Moms": "📋",
                            "Bokslut": "📊",
                            "Skatteinbetalning": "🏛️",
                            "Lönehantering": "💼",
                            "Revision": "🔍",
                            "Övrigt": "📌"
                        }
                        icon = icon_map.get(event["typ"], "📌")

                        # Prioritetsfärg
                        priority_color = {
                            "Hög": "🔴",
                            "Medel": "🟡",
                            "Låg": "🟢"
                        }.get(event.get("prioritet", "Medel"), "🟡")

                        with st.container():
                            col_main, col_actions = st.columns([4, 1])

                            with col_main:
                                st.markdown(
                                    f"{icon} **{event['titel']}** {priority_color}  \n"
                                    f"📅 {event['datum']}" +
                                    (f" 🕐 {event['tid']}" if event.get('tid') else "") +
                                    f" | 🏢 {event.get('verksamhet', 'Alla')} | 🏷️ {event['typ']}"
                                )

                                if event.get('beskrivning'):
                                    st.caption(f"💬 {event['beskrivning']}")

                            with col_actions:
                                if st.button("🗑️", key=f"delete_{event['id']}", help="Ta bort händelse"):
                                    calendar_data["events"] = [
                                        e for e in calendar_data["events"] if e["id"] != event["id"]]
                                    save_calendar(calendar_data)
                                    st.success("✅ Händelse borttagen!")
                                    st.rerun()

                            st.markdown("---")

    # Kommande händelser i sidebar (förbättrad)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📅 Kommande händelser")

    today = date.today().strftime("%Y-%m-%d")
    upcoming = [e for e in calendar_data["events"] if e["datum"] >= today]
    upcoming.sort(key=lambda x: x["datum"])

    if upcoming[:5]:
        for event in upcoming[:5]:
            days_until = (datetime.strptime(
                event["datum"], "%Y-%m-%d").date() - date.today()).days

            # Färgkodning baserat på tid kvar
            if days_until == 0:
                badge = "🔴"
                text = "IDAG"
            elif days_until == 1:
                badge = "🟠"
                text = "IMORGON"
            elif days_until <= 3:
                badge = "🟡"
                text = f"{days_until} dagar"
            elif days_until <= 7:
                badge = "🟢"
                text = f"{days_until} dagar"
            else:
                badge = "⚪"
                text = f"{days_until} dagar"

            st.sidebar.markdown(
                f"{badge} **{text}**  \n"
                f"{event['titel']}  \n"
                f"*{event['datum']} - {event['typ']}*"
            )
            st.sidebar.markdown("---")
    else:
        st.sidebar.info("Inga kommande händelser")

# --- DUBBLETTHANTERING ---
elif main_menu == "🔍 Dubbletthantering":
    st.title("🔍 Dubbletthantering")

    st.info(
        "💡 **Dubbletter detekteras baserat på:**\n"
        "- Samma datum\n"
        "- Samma belopp\n"
        "- Samma leverantör/kund\n"
        "- Samma verksamhet"
    )

    tab1, tab2 = st.tabs(["💸 Utgifter", "💰 Intäkter"])

    with tab1:
        st.subheader("💸 Dubbletter i utgifter")

        # Hitta dubbletter
        expense_duplicates = find_duplicate_expenses(expenses)

        if not expense_duplicates:
            st.success("✅ Inga dubbletter hittade i utgifter!")
        else:
            st.warning(
                f"⚠️ Hittade {len(expense_duplicates)} potentiella dubbletter")

            # Gruppera per verksamhet
            for business in BUSINESSES:
                business_dupes = [
                    d for d in expense_duplicates if d["business"] == business]

                if business_dupes:
                    st.markdown(
                        f"### {business} ({len(business_dupes)} dubbletter)")

                    for dupe in business_dupes:
                        original = dupe["original"]
                        duplicate = dupe["duplicate"]

                        with st.expander(f"🔄 {original['datum']} - {original['leverantor']} - {original['belopp']:,.2f} kr"):
                            col1, col2 = st.columns(2)

                            with col1:
                                st.markdown("#### 📄 Original")
                                st.write(f"**Datum:** {original['datum']}")
                                st.write(
                                    f"**Kategori:** {original['kategori']}")
                                st.write(
                                    f"**Beskrivning:** {original['beskrivning']}")
                                st.write(
                                    f"**Leverantör:** {original['leverantor']}")
                                st.write(
                                    f"**Belopp:** {original['belopp']:,.2f} kr")

                            with col2:
                                st.markdown("#### 🔄 Dublett")
                                st.write(f"**Datum:** {duplicate['datum']}")
                                st.write(
                                    f"**Kategori:** {duplicate['kategori']}")
                                st.write(
                                    f"**Beskrivning:** {duplicate['beskrivning']}")
                                st.write(
                                    f"**Leverantör:** {duplicate['leverantor']}")
                                st.write(
                                    f"**Belopp:** {duplicate['belopp']:,.2f} kr")

                            st.markdown("---")
                            col_a, col_b, col_c = st.columns(3)

                            if col_a.button("🗑️ Ta bort dubbletten", key=f"del_dupe_{business}_{dupe['duplicate_index']}", type="primary"):
                                remove_expense_by_index(
                                    expenses, business, dupe["duplicate_index"])
                                save_expenses(expenses)
                                st.success("✅ Dublett borttagen!")
                                st.rerun()

                            if col_b.button("🗑️ Ta bort originalet", key=f"del_orig_{business}_{dupe['original_index']}", type="secondary"):
                                remove_expense_by_index(
                                    expenses, business, dupe["original_index"])
                                save_expenses(expenses)
                                st.success("✅ Original borttagen!")
                                st.rerun()

                            if col_c.button("✅ Behåll båda", key=f"keep_{business}_{dupe['duplicate_index']}"):
                                st.info("Behåller båda transaktionerna")

            # Bulk-radering
            st.markdown("---")
            st.markdown("### 🗑️ Rensa alla dubbletter")
            st.warning(
                "⚠️ **VARNING:** Detta tar bort ALLA dubbletter automatiskt (behåller alltid originalet)")

            if st.button("🗑️ Ta bort alla dubbletter", type="secondary"):
                removed_count = 0

                # Sortera i omvänd ordning för att inte påverka index
                for dupe in sorted(expense_duplicates, key=lambda x: x["duplicate_index"], reverse=True):
                    remove_expense_by_index(
                        expenses, dupe["business"], dupe["duplicate_index"])
                    removed_count += 1

                save_expenses(expenses)
                st.success(f"✅ {removed_count} dubbletter borttagna!")
                st.balloons()
                st.rerun()

    with tab2:
        st.subheader("💰 Dubbletter i intäkter")

        revenue_duplicates = find_duplicate_revenue(revenue)

        if not revenue_duplicates:
            st.success("✅ Inga dubbletter hittade i intäkter!")
        else:
            st.warning(
                f"⚠️ Hittade {len(revenue_duplicates)} potentiella dubbletter")

            for dupe in revenue_duplicates:
                original = dupe["original"]
                duplicate = dupe["duplicate"]

                with st.expander(f"🔄 {original['datum']} - {original['kund']} - {original['belopp']:,.2f} kr"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("#### 📄 Original")
                        st.write(f"**Datum:** {original['datum']}")
                        st.write(
                            f"**Verksamhet:** {original.get('verksamhet', 'N/A')}")
                        st.write(f"**Kategori:** {original['kategori']}")
                        st.write(f"**Beskrivning:** {original['beskrivning']}")
                        st.write(f"**Kund:** {original['kund']}")
                        st.write(f"**Belopp:** {original['belopp']:,.2f} kr")

                    with col2:
                        st.markdown("#### 🔄 Dublett")
                        st.write(f"**Datum:** {duplicate['datum']}")
                        st.write(
                            f"**Verksamhet:** {duplicate.get('verksamhet', 'N/A')}")
                        st.write(f"**Kategori:** {duplicate['kategori']}")
                        st.write(
                            f"**Beskrivning:** {duplicate['beskrivning']}")
                        st.write(f"**Kund:** {duplicate['kund']}")
                        st.write(f"**Belopp:** {duplicate['belopp']:,.2f} kr")

                    st.markdown("---")
                    col_a, col_b, col_c = st.columns(3)

                    if col_a.button("🗑️ Ta bort dubbletten", key=f"del_rev_dupe_{dupe['duplicate_index']}", type="primary"):
                        remove_revenue_by_index(
                            revenue, dupe["duplicate_index"])
                        save_revenue(revenue)
                        st.success("✅ Dublett borttagen!")
                        st.rerun()

                    if col_b.button("🗑️ Ta bort originalet", key=f"del_rev_orig_{dupe['original_index']}", type="secondary"):
                        remove_revenue_by_index(
                            revenue, dupe["original_index"])
                        save_revenue(revenue)
                        st.success("✅ Original borttagen!")
                        st.rerun()

                    if col_c.button("✅ Behåll båda", key=f"keep_rev_{dupe['duplicate_index']}"):
                        st.info("Behåller båda transaktionerna")

            # Bulk-radering
            st.markdown("---")
            st.markdown("### 🗑️ Rensa alla dubbletter")
            st.warning(
                "⚠️ **VARNING:** Detta tar bort ALLA dubbletter automatiskt (behåller alltid originalet)")

            if st.button("🗑️ Ta bort alla intäktsdubbletter", type="secondary"):
                removed_count = 0

                # Sortera i omvänd ordning
                for dupe in sorted(revenue_duplicates, key=lambda x: x["duplicate_index"], reverse=True):
                    remove_revenue_by_index(revenue, dupe["duplicate_index"])
                    removed_count += 1

                save_revenue(revenue)
                st.success(f"✅ {removed_count} dubbletter borttagna!")
                st.balloons()
                st.rerun()

    # Statistik
    st.markdown("---")
    st.markdown("### 📊 Statistik")

    total_expenses_dupes = len(expense_duplicates)
    total_revenue_dupes = len(revenue_duplicates)

    col1, col2, col3 = st.columns(3)
    col1.metric("💸 Utgiftsdubbletter", total_expenses_dupes)
    col2.metric("💰 Intäktsdubbletter", total_revenue_dupes)
    col3.metric("📊 Totalt dubbletter",
                total_expenses_dupes + total_revenue_dupes)

    if total_expenses_dupes > 0 or total_revenue_dupes > 0:
        st.warning(
            "💡 **Tips:** Dubbletter uppstår ofta vid CSV-import eller manuell registrering av samma transaktion flera gånger.")

# --- RAPPORT-FUNKTIONER (LÄGG TILL VID RAD 205, EFTER remove_revenue_by_index) ---


def generate_monthly_report(expenses: Dict, revenue: Dict, month: str, business: str = None) -> Dict:
    """Genererar månadsrapport"""

    businesses_to_include = [business] if business else BUSINESSES

    report = {
        "period": month,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "businesses": {}
    }

    for biz in businesses_to_include:
        # Utgifter för månaden
        month_expenses = [e for e in expenses[biz]
                          ["utgifter"] if e["datum"].startswith(month)]
        total_expenses = sum(e["belopp"] for e in month_expenses)

        # Intäkter för månaden
        month_revenue = [r for r in revenue["intakter"] if r["datum"].startswith(
            month) and r.get("verksamhet") == biz]
        total_revenue = sum(r["belopp"] for r in month_revenue)

        # Vinst
        profit = total_revenue - total_expenses
        margin = (profit / total_revenue * 100) if total_revenue > 0 else 0

        # Per kategori
        category_breakdown = {}
        for cat in EXPENSE_CATEGORIES:
            cat_total = sum(e["belopp"]
                            for e in month_expenses if e["kategori"] == cat)
            if cat_total > 0:
                category_breakdown[cat] = cat_total

        report["businesses"][biz] = {
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "profit": profit,
            "margin": margin,
            "category_breakdown": category_breakdown,
            "transaction_count": len(month_expenses) + len(month_revenue)
        }

    return report


def export_to_excel(data: Dict, filename: str) -> BytesIO:
    """Exporterar data till Excel"""
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Utgifter
        for business in BUSINESSES:
            if data[business]["utgifter"]:
                df = pd.DataFrame(data[business]["utgifter"])
                df.to_excel(
                    writer, sheet_name=f"{business}_Utgifter", index=False)

        # Intäkter (om det finns)
        if "intakter" in data:
            df_revenue = pd.DataFrame(data["intakter"])
            df_revenue.to_excel(writer, sheet_name="Intakter", index=False)

    output.seek(0)
    return output


# --- STREAMLIT APP (fortsätter här som vanligt) ---
st.set_page_config(page_title="Företagsekonomi AI",
                   page_icon="🏢", layout="wide")

# Ladda data
expenses = load_expenses()
revenue = load_revenue()
budget = load_budget()
receipts_data = load_receipts()
calendar_data = load_calendar()

# --- SIDEBAR ---
st.sidebar.title("🏢 Företagsekonomi")
st.sidebar.markdown("---")

main_menu = st.sidebar.radio("Huvudmeny", [
    "📊 Dashboard",
    "💰 Utgifter",
    "💵 Intäkter",
    "📈 Budget & Prognos",
    "📄 Kvittoredovisning",
    "📅 Kalender",
    "💬 Chatt",
    "👥 Användare",
    "📋 Rapporter",
    "🔍 Dubbletthantering",
    "⚙️ Inställningar"
])

# --- DASHBOARD ---
if main_menu == "📊 Dashboard":
    st.title("📊 Dashboard - Företagsöversikt")

    # Custom CSS för snyggare dashboard
    st.markdown("""
        <style>
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 10px;
            color: white;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }
        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
        }
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
            margin: 10px 0;
        }
        .metric-label {
            font-size: 0.9rem;
            opacity: 0.9;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        </style>
    """, unsafe_allow_html=True)

    # Beräkna totaler
    total_expenses = sum(expenses[b]["total"] for b in BUSINESSES)
    total_revenue = revenue["total"]
    total_profit = total_revenue - total_expenses
    profit_margin = (total_profit/total_revenue *
                     100 if total_revenue > 0 else 0)

    # Snygga gradient-kort
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                <div class="metric-label">💰 Total Intäkt</div>
                <div class="metric-value">{total_revenue:,.0f} kr</div>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                <div class="metric-label">💸 Total Utgift</div>
                <div class="metric-value">{total_expenses:,.0f} kr</div>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        profit_gradient = "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)" if total_profit > 0 else "linear-gradient(135deg, #f5576c 0%, #f093fb 100%)"
        st.markdown(f"""
            <div class="metric-card" style="background: {profit_gradient};">
                <div class="metric-label">📈 Nettovinst</div>
                <div class="metric-value">{total_profit:,.0f} kr</div>
            </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
                <div class="metric-label">📊 Marginal</div>
                <div class="metric-value">{profit_margin:.1f}%</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Tabs för olika vyer
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📈 Trendanalys", "🥧 Fördelning", "📊 Jämförelse", "🎯 Budget"])

    with tab1:
        st.subheader("📈 Intäkter & Utgifter - Senaste 6 månaderna")

        # Beräkna månadsdata
        months = []
        revenue_by_month = []
        expenses_by_month = []
        profit_by_month = []

        for i in range(5, -1, -1):
            month_date = date.today() - timedelta(days=i*30)
            month = month_date.strftime("%Y-%m")
            month_name = month_date.strftime("%b %Y")
            months.append(month_name)

            month_rev = sum(i["belopp"] for i in revenue["intakter"]
                            if i["datum"].startswith(month))
            month_exp = sum(sum(u["belopp"] for u in expenses[b]["utgifter"]
                            if u["datum"].startswith(month)) for b in BUSINESSES)

            revenue_by_month.append(month_rev)
            expenses_by_month.append(month_exp)
            profit_by_month.append(month_rev - month_exp)

        # Skapa interaktiv graf
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=months,
            y=revenue_by_month,
            mode='lines+markers',
            name='Intäkter',
            line=dict(color='#667eea', width=3),
            marker=dict(size=10, symbol='circle'),
            hovertemplate='<b>%{x}</b><br>Intäkter: %{y:,.0f} kr<extra></extra>'
        ))

        fig.add_trace(go.Scatter(
            x=months,
            y=expenses_by_month,
            mode='lines+markers',
            name='Utgifter',
            line=dict(color='#f5576c', width=3),
            marker=dict(size=10, symbol='square'),
            hovertemplate='<b>%{x}</b><br>Utgifter: %{y:,.0f} kr<extra></extra>'
        ))

        fig.add_trace(go.Scatter(
            x=months,
            y=profit_by_month,
            mode='lines+markers',
            name='Vinst',
            line=dict(color='#43e97b', width=3, dash='dash'),
            marker=dict(size=10, symbol='diamond'),
            hovertemplate='<b>%{x}</b><br>Vinst: %{y:,.0f} kr<extra></extra>'
        ))

        fig.update_layout(
            title="Utveckling över tid",
            xaxis_title="Månad",
            yaxis_title="Belopp (kr)",
            hovermode='x unified',
            template="plotly_white",
            height=500,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        st.plotly_chart(fig, use_container_width=True)

        # Snabb-statistik
        col1, col2, col3 = st.columns(3)

        avg_revenue = sum(revenue_by_month) / \
            len(revenue_by_month) if revenue_by_month else 0
        avg_expenses = sum(expenses_by_month) / \
            len(expenses_by_month) if expenses_by_month else 0
        trend = ((revenue_by_month[-1] - revenue_by_month[0]) / revenue_by_month[0]
                 * 100) if revenue_by_month and revenue_by_month[0] > 0 else 0

        col1.metric("📊 Genomsnittlig intäkt/mån", f"{avg_revenue:,.0f} kr")
        col2.metric("📊 Genomsnittlig utgift/mån", f"{avg_expenses:,.0f} kr")
        col3.metric("📈 Trend (6 mån)", f"{trend:+.1f}%")

    with tab2:
        st.subheader("🥧 Utgiftsfördelning")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Per kategori")

            # Samla utgifter per kategori
            category_totals = {}
            for business in BUSINESSES:
                for utgift in expenses[business]["utgifter"]:
                    cat = utgift["kategori"]
                    category_totals[cat] = category_totals.get(
                        cat, 0) + utgift["belopp"]

            if category_totals:
                fig = px.pie(
                    values=list(category_totals.values()),
                    names=list(category_totals.keys()),
                    title="Utgifter per kategori",
                    color_discrete_sequence=px.colors.qualitative.Set3,
                    hole=0.4
                )
                fig.update_traces(textposition='inside',
                                  textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Ingen data att visa")

        with col2:
            st.markdown("#### Per verksamhet")

            business_totals = {
                business: expenses[business]["total"] for business in BUSINESSES}

            if any(business_totals.values()):
                fig = px.pie(
                    values=list(business_totals.values()),
                    names=list(business_totals.keys()),
                    title="Utgifter per verksamhet",
                    color_discrete_sequence=['#667eea', '#f5576c'],
                    hole=0.4
                )
                fig.update_traces(textposition='inside',
                                  textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Ingen data att visa")

        # Top 5 leverantörer
        st.markdown("---")
        st.markdown("#### 🏪 Top 5 Leverantörer")

        supplier_totals = {}
        for business in BUSINESSES:
            for utgift in expenses[business]["utgifter"]:
                supplier = utgift["leverantor"]
                supplier_totals[supplier] = supplier_totals.get(
                    supplier, 0) + utgift["belopp"]

        if supplier_totals:
            top_suppliers = sorted(
                supplier_totals.items(), key=lambda x: x[1], reverse=True)[:5]

            suppliers = [s[0] for s in top_suppliers]
            amounts = [s[1] for s in top_suppliers]

            fig = go.Figure(data=[go.Bar(
                x=amounts,
                y=suppliers,
                orientation='h',
                marker=dict(
                    color=amounts,
                    colorscale='Viridis',
                    showscale=False
                ),
                text=[f"{a:,.0f} kr" for a in amounts],
                textposition='auto',
            )])

            fig.update_layout(
                title="Högsta utgifter per leverantör",
                xaxis_title="Belopp (kr)",
                yaxis_title="",
                height=300,
                template="plotly_white"
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Ingen leverantörsdata att visa")

    with tab3:
        st.subheader("📊 Verksamhetsjämförelse")

        # Jämförelse Unithread vs Merchoteket
        comparison_data = []
        for business in BUSINESSES:
            business_revenue = sum(
                i["belopp"] for i in revenue["intakter"] if i.get("verksamhet") == business)
            business_expenses = expenses[business]["total"]
            business_profit = business_revenue - business_expenses

            comparison_data.append({
                "Verksamhet": business,
                "Intäkter": business_revenue,
                "Utgifter": business_expenses,
                "Vinst": business_profit
            })

        df = pd.DataFrame(comparison_data)

        # Grouped bar chart
        fig = go.Figure()

        fig.add_trace(go.Bar(
            name='Intäkter',
            x=df["Verksamhet"],
            y=df["Intäkter"],
            marker_color='#667eea',
            text=df["Intäkter"].apply(lambda x: f"{x:,.0f} kr"),
            textposition='auto',
        ))

        fig.add_trace(go.Bar(
            name='Utgifter',
            x=df["Verksamhet"],
            y=df["Utgifter"],
            marker_color='#f5576c',
            text=df["Utgifter"].apply(lambda x: f"{x:,.0f} kr"),
            textposition='auto',
        ))

        fig.add_trace(go.Bar(
            name='Vinst',
            x=df["Verksamhet"],
            y=df["Vinst"],
            marker_color='#43e97b',
            text=df["Vinst"].apply(lambda x: f"{x:,.0f} kr"),
            textposition='auto',
        ))

        fig.update_layout(
            title="Verksamhetsjämförelse",
            xaxis_title="Verksamhet",
            yaxis_title="Belopp (kr)",
            barmode='group',
            template="plotly_white",
            height=500,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        st.plotly_chart(fig, use_container_width=True)

        # Detaljerad tabell
        st.markdown("---")
        st.markdown("#### 📋 Detaljerad jämförelse")

        for business in BUSINESSES:
            with st.expander(f"🏢 {business}"):
                business_revenue = sum(
                    i["belopp"] for i in revenue["intakter"] if i.get("verksamhet") == business)
                business_expenses = expenses[business]["total"]
                business_profit = business_revenue - business_expenses
                profit_margin = (
                    business_profit / business_revenue * 100) if business_revenue > 0 else 0

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Intäkter", f"{business_revenue:,.0f} kr")
                col2.metric("Utgifter", f"{business_expenses:,.0f} kr")
                col3.metric("Vinst", f"{business_profit:,.0f} kr")
                col4.metric("Marginal", f"{profit_margin:.1f}%")

    with tab4:
        st.subheader("🎯 Budgetuppföljning")

        for business in BUSINESSES:
            st.markdown(f"### {business}")

            total_budget = budget[business].get("total", 0)
            current_expenses = expenses[business]["total"]

            if total_budget > 0:
                percentage = (current_expenses / total_budget) * 100
                remaining = total_budget - current_expenses

                # Färgkodning baserat på användning
                if percentage < 70:
                    color = "#43e97b"
                    gradient = "linear-gradient(90deg, #43e97b 0%, #38f9d7 100%)"
                    status = "🟢 Inom budget"
                    status_color = "#43e97b"
                elif percentage < 90:
                    color = "#ffbb33"
                    gradient = "linear-gradient(90deg, #ffbb33 0%, #ff8800 100%)"
                    status = "🟡 Nära budget"
                    status_color = "#ffbb33"
                else:
                    color = "#f5576c"
                    gradient = "linear-gradient(90deg, #f5576c 0%, #f093fb 100%)"
                    status = "🔴 Över budget"
                    status_color = "#f5576c"

                # Snygg progress bar med gradient
                st.markdown(f"""
                    <div style="background-color: #f0f0f0; border-radius: 10px; padding: 3px; margin: 10px 0;">
                        <div style="background: {gradient}; 
                                    width: {min(percentage, 100)}%; 
                                    border-radius: 8px; 
                                    padding: 15px; 
                                    color: white; 
                                    font-weight: bold;
                                    text-align: center;
                                    transition: width 0.5s ease;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            {percentage:.1f}% använt
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                # Statistik
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("💰 Budget", f"{total_budget:,.0f} kr")
                col2.metric("💸 Använt", f"{current_expenses:,.0f} kr")
                col3.metric("💵 Kvar", f"{max(remaining, 0):,.0f} kr",
                            delta=f"{-percentage:.1f}%" if percentage > 100 else None)
                col4.markdown(
                    f"<div style='padding: 20px; text-align: center; font-weight: bold; color: {status_color};'>{status}</div>", unsafe_allow_html=True)

                # Per kategori progress
                st.markdown("#### Budget per kategori")

                category_budget = budget[business].get("kategorier", {})
                if category_budget:
                    for kategori in EXPENSE_CATEGORIES:
                        cat_budget = category_budget.get(kategori, 0)
                        if cat_budget > 0:
                            cat_expenses = sum(
                                u["belopp"] for u in expenses[business]["utgifter"] if u["kategori"] == kategori)
                            cat_percentage = (
                                cat_expenses / cat_budget * 100) if cat_budget > 0 else 0

                            # Mini progress bar
                            if cat_percentage < 80:
                                bar_color = "#43e97b"
                            elif cat_percentage < 100:
                                bar_color = "#ffbb33"
                            else:
                                bar_color = "#f5576c"

                            with st.container():
                                col_a, col_b = st.columns([3, 1])
                                with col_a:
                                    st.markdown(f"**{kategori}**")
                                    st.markdown(f"""
                                        <div style="background-color: #f0f0f0; border-radius: 5px; padding: 2px; margin: 5px 0;">
                                            <div style="background-color: {bar_color}; 
                                                        width: {min(cat_percentage, 100)}%; 
                                                        border-radius: 3px; 
                                                        padding: 5px; 
                                                        color: white; 
                                                        font-size: 0.8rem;
                                                        text-align: center;">
                                                {cat_percentage:.0f}%
                                            </div>
                                        </div>
                                    """, unsafe_allow_html=True)
                                with col_b:
                                    st.caption(
                                        f"{cat_expenses:,.0f} / {cat_budget:,.0f} kr")
                else:
                    st.info("Ingen kategoribudget satt")
            else:
                st.warning("⚠️ Ingen budget satt för denna verksamhet")
                if st.button(f"➕ Sätt budget för {business}", key=f"set_budget_{business}"):
                    st.info("Gå till 'Budget & Prognos' för att sätta budget")

            st.markdown("---")

    st.markdown("---")

    # AI Prognos
    st.subheader("🤖 AI-Prognos: Nästa månad")

    col1, col2 = st.columns(2)
    for idx, business in enumerate(BUSINESSES):
        with [col1, col2][idx]:
            forecast = generate_forecast(expenses, business, months_ahead=1)

            st.markdown(f"#### {business}")

            col_a, col_b = st.columns(2)
            col_a.metric("Prognostiserad utgift",
                         f"{forecast['forecast']:,.0f} kr")
            col_b.metric("Trend", f"{forecast['trend']:+.1f}%/mån")

            st.caption(
                f"Confidence: {forecast['confidence'].upper()} | {forecast['data_points']} datapunkter")

            # Varning om stor ökning
            if forecast['trend'] > 10:
                st.error(
                    f"⚠️ Utgifterna ökar med {forecast['trend']:.1f}% per månad")
            elif forecast['trend'] > 5:
                st.warning(
                    f"⚠️ Utgifterna ökar med {forecast['trend']:.1f}% per månad")
            elif forecast['trend'] < -5:
                st.success(
                    f"✅ Utgifterna minskar med {abs(forecast['trend']):.1f}% per månad")

# --- CHATT ---
elif main_menu == "💬 Chatt":
    st.title("💬 Chatt")

    # Ladda chattdata
    chatt_data = load_chat()

    # Välj chattgrupp
    if chatt_data["groups"]:
        group_names = [g["name"] for g in chatt_data["groups"]]
        selected_group = st.selectbox("Välj chattgrupp", group_names)

        # Hämta vald grupps medlemmar
        group_members = next(
            (g["members"] for g in chatt_data["groups"] if g["name"] == selected_group), [])

        # Visa meddelanden i vald grupp
        st.markdown(f"### Meddelanden i '{selected_group}'")

        group_messages = [m for m in chatt_data["messages"]
                          if m["group_id"] == selected_group]

        if group_messages:
            for msg in group_messages:
                is_sender = msg["sender"] == auth.get_current_user()
                align = "right" if is_sender else "left"

                # Meddelande-bubble
                st.markdown(f"""
                    <div style="text-align: {align}; margin-bottom: 10px;">
                        <div style="display: inline-block; padding: 10px; border-radius: 10px;
                                    background-color: {'#dcf8c6' if is_sender else '#f1f0f0'};
                                    max-width: 80%;">
                            <strong>{msg['sender']}:</strong> {msg['content']}<br>
                            <span style="font-size: 0.8rem; color: #888;">{msg['timestamp']}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Inga meddelanden i denna grupp")

        # Nytt meddelande
        st.markdown("---")
        st.subheader("Skicka nytt meddelande")

        with st.form("new_message_form"):
            message_content = st.text_area("Meddelande", "")
            submitted = st.form_submit_button("Skicka")

            if submitted and message_content:
                # Hämta grupp-id
                group_id = next(
                    (g["id"] for g in chatt_data["groups"] if g["name"] == selected_group), None)

                if group_id:
                    send_message(group_id, auth.get_current_user(), message_content)

                    st.success("Meddelande skickat!")
                    st.session_state.messages = load_chat()["messages"]  # Uppdatera meddelanden
                    st.text_area("Meddelande", "", key="new_message")  # Rensa fält
                else:
                    st.error("Kunde inte hitta grupp-id")

    else:
        st.info("Inga chattgrupper hittade. Skapa en ny grupp.")

    # Hantera nya chattgrupper
    st.markdown("---")
    st.subheader("Hantera chattgrupper")

    with st.form("chat_group_form"):
        new_group_name = st.text_input("Ny gruppnamn", "")
        members = st.multiselect("Välj medlemmar", [u["username"] for u in receipts_data["users"]])
        create_group = st.form_submit_button("Skapa grupp")

        if create_group and new_group_name and members:
            group_id = create_chat_group(new_group_name, members, auth.get_current_user())
            st.success(f"Grupp '{new_group_name}' skapad!")
            st.session_state.groups = load_chat()["groups"]  # Uppdatera grupper
        elif create_group:
            st.error("Fyll i alla fält för att skapa en grupp")

    # Visa befintliga grupper
    st.markdown("---")
    st.markdown("### Dina chattgrupper")

    if chatt_data["groups"]:
        for group in chatt_data["groups"]:
            with st.expander(group["name"], expanded=False):
                st.write("Medlemmar:")
                for member in group["members"]:
                    st.write(f"- {member}")

                # Arkivera/återställ knapp
                if st.button(f"{ 'Återställ' if group['archived'] else 'Arkivera' } grupp", key=f"archive_{group['id']}"):
                    new_status = "active" if group["archived"] else "archived"