import streamlit as st
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import calendar as cal_module  # Renamed to avoid conflict
import numpy as np
from PIL import Image
import base64
import fitz  # PyMuPDF för PDF-hantering
import sys
import time
import uuid
import auth
from db_handler import db  # Importera vår nya databashanterare

# --- AUTHENTICATION ---
if not auth.check_login():
    st.stop()

# --- CSS STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global Styles */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main {
        background-color: #f8fafc;
    }

    h1, h2, h3 {
        color: #0f172a;
        font-weight: 700;
        letter-spacing: -0.025em;
    }

    h1 { font-size: 2.5rem; }
    h2 { font-size: 1.8rem; }
    h3 { font-size: 1.4rem; }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }

    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }

    /* Custom Radio Button Styling (Sidebar Menu) */
    .stRadio > div[role="radiogroup"] > label {
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 10px 15px;
        margin-bottom: 4px;
        transition: all 0.2s ease;
        color: #475569;
        font-weight: 500;
        cursor: pointer;
    }

    .stRadio > div[role="radiogroup"] > label:hover {
        background-color: #f1f5f9;
        color: #0f172a;
    }

    /* Active State for Radio Buttons (Approximation via CSS is hard, but we can style the selected one if Streamlit adds a class, otherwise we rely on the dot) */
    /* Streamlit's radio button structure is complex, but we can hide the circle and style the label */
    .stRadio > div[role="radiogroup"] > label > div:first-child {
        display: none; /* Hide the radio circle */
    }

    .stRadio > div[role="radiogroup"] > label[data-baseweb="radio"] {
        width: 100%;
    }

    /* Cards */
    .metric-card {
        background: white;
        padding: 24px;
        border-radius: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border: 1px solid #f1f5f9;
        transition: all 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.02);
        border-color: #e2e8f0;
    }
    .metric-value {
        font-size: 2.5rem;
        font-weight: 800;
        color: #0f172a;
        margin: 12px 0;
        letter-spacing: -0.03em;
    }
    .metric-label {
        font-size: 0.875rem;
        color: #64748b;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-delta {
        font-size: 0.875rem;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 9999px;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .delta-positive {
        background-color: #dcfce7;
        color: #15803d;
    }
    .delta-negative {
        background-color: #fee2e2;
        color: #b91c1c;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #f1f5f9;
        padding: 4px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 8px;
        color: #64748b;
        font-weight: 600;
        border: none;
        padding: 0 20px;
        transition: all 0.2s;
    }
    .stTabs [aria-selected="true"] {
        background-color: white !important;
        color: #0f172a !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }

    /* Buttons */
    .stButton button {
        border-radius: 10px;
        font-weight: 600;
        padding: 0.6rem 1.2rem;
        transition: all 0.2s;
        border: none;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    /* Primary Button */
    .stButton button[kind="primary"] {
        background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
        color: white;
    }

    /* Dataframes */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }

    /* Calendar */
    .cal-container {
        background: white;
        padding: 24px;
        border-radius: 20px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
        border: 1px solid #f1f5f9;
    }
    .cal-header {
        background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
        color: white;
        padding: 24px;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 24px;
        box-shadow: 0 10px 15px -3px rgba(79, 70, 229, 0.2);
    }
    .cal-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 12px;
        margin-top: 20px;
    }
    .cal-weekday {
        background: #f8fafc;
        padding: 14px;
        text-align: center;
        font-weight: 700;
        color: #64748b;
        border-radius: 10px;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .cal-day {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        min-height: 140px;
        padding: 10px;
        transition: all 0.2s ease;
        display: flex;
        flex-direction: column;
    }
    .cal-day:hover {
        border-color: #667eea;
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        z-index: 10;
    }
    .cal-day.empty {
        background: #f8fafc;
        border: 1px dashed #cbd5e1;
        opacity: 0.6;
    }
    .cal-day.today {
        background: #eff6ff;
        border: 2px solid #3b82f6;
        box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1);
    }
    .cal-day.selected {
        border-color: #667eea;
        background-color: #f0fdf4;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.3);
    }
    .cal-day-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
        padding-bottom: 6px;
        border-bottom: 1px solid #f1f5f9;
    }
    .cal-day-num {
        font-size: 1.2rem;
        font-weight: 700;
        color: #334155;
    }
    .cal-day.today .cal-day-num {
        color: #2563eb;
    }
    .cal-event-pill {
        font-size: 0.75rem;
        padding: 4px 8px;
        border-radius: 6px;
        margin-bottom: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        color: white;
        font-weight: 500;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .pill-deadline { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }
    .pill-mote { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }
    .pill-paminnelse { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }
    .pill-ovrigt { background: linear-gradient(135deg, #64748b 0%, #475569 100%); }
    .cal-more-events {
        font-size: 0.7rem;
        color: #64748b;
        text-align: center;
        margin-top: auto;
        padding-top: 4px;
        font-weight: 500;
    }

    /* Chat Styles */
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 20px;
        padding-bottom: 100px; /* Space for chat input */
        background: transparent;
        border-radius: 16px;
        margin-bottom: 20px;
    }

    .chat-bubble {
        padding: 12px 18px;
        border-radius: 18px;
        max-width: 75%;
        position: relative;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        line-height: 1.5;
    }

    .chat-bubble-me {
        background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
        color: white;
        align-self: flex-end;
        border-bottom-right-radius: 4px;
        margin-left: auto;
    }

    .chat-bubble-other {
        background-color: white;
        color: #1e293b;
        align-self: flex-start;
        border-bottom-left-radius: 4px;
        border: 1px solid #e2e8f0;
    }

    .chat-meta {
        font-size: 0.7rem;
        margin-bottom: 4px;
        opacity: 0.8;
        display: flex;
        justify-content: space-between;
        gap: 10px;
    }

    .chat-avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 600;
        font-size: 0.85rem;
        margin-right: 10px;
        color: white;
        border: 2px solid white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        text-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }

    .chat-row {
        display: flex;
        align-items: flex-end;
        margin-bottom: 8px;
        width: 100%;
    }

    .chat-row.me {
        justify-content: flex-end;
    }

    .chat-header {
        padding: 16px;
        background: white;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        position: sticky;
        top: 0;
        z-index: 100;
    }

    .chat-date-divider {
        text-align: center;
        margin: 24px 0;
        position: relative;
    }

    .chat-date-divider span {
        background: #e2e8f0;
        color: #64748b;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    /* Floating Chat */
    .floating-chat-container {
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 350px;
        max-width: 90%;
        background: white;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        transition: transform 0.3s ease;
    }

    .floating-chat-header {
        background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
        color: white;
        padding: 12px;
        border-radius: 12px 12px 0 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .floating-chat-close {
        background: transparent;
        border: none;
        color: white;
        font-size: 1.2rem;
        cursor: pointer;
    }

    .floating-chat-body {
        padding: 16px;
        flex-grow: 1;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
    }

    .floating-chat-footer {
        display: flex;
        padding: 10px;
        border-top: 1px solid #e2e8f0;
    }

    .floating-chat-input {
        flex-grow: 1;
        padding: 10px;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        margin-right: 10px;
    }

    .floating-chat-send {
        background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 8px;
        cursor: pointer;
        transition: background 0.3s ease;
    }

    .floating-chat-send:hover {
        background: linear-gradient(135deg, #4338ca 0%, #4f46e5 100%);
    }

    /* Tables */
    .dataframe {
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
    }
    .dataframe th, .dataframe td {
        padding: 12px 15px;
        border: 1px solid #e2e8f0;
        text-align: left;
    }
    .dataframe th {
        background-color: #f1f5f9;
        color: #334155;
        font-weight: 600;
    }
    .dataframe tr:nth-child(even) {
        background-color: #f9fafb;
    }
    .dataframe tr:hover {
        background-color: #f1f5f9;
    }

    /* Misc */
    hr {
        border: 0;
        height: 1px;
        background: #e2e8f0;
        margin: 20px 0;
    }

    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #f1f5f9;
    }
    ::-webkit-scrollbar-thumb {
        background: #4f46e5;
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #4338ca;
    }
</style>
""", unsafe_allow_html=True)


# --- KONFIGURATION ---
DATA_DIR = Path(__file__).parent / "foretag_data"
DATA_DIR.mkdir(exist_ok=True)

EXPENSES_FILE = DATA_DIR / "utgifter.json"
REVENUE_FILE = DATA_DIR / "intakter.json"
BUDGET_FILE = DATA_DIR / "budget.json"
ACTIVITY_LOG_FILE = DATA_DIR / "aktivitetslogg.json"  # NY
GOALS_FILE = DATA_DIR / "mal.json"  # NY
CHATT_FILE = DATA_DIR / "chatt.json"  # NY
FILES_DIR = DATA_DIR / "filer"
FILES_DIR.mkdir(exist_ok=True)

# Bokföringsstöd
BOKFORING_FILE = DATA_DIR / "bokforing.json"
BOKFORING_FILES_DIR = FILES_DIR / "bokforing"
BOKFORING_FILES_DIR.mkdir(exist_ok=True)

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


class User:
    """Representerar en systemanvändare"""

    def __init__(self, username: str, role: str, permissions: List[str] = None):
        self.username = username
        self.role = role
        self.permissions = permissions or []


class UserManager:
    """Hanterar systemanvändare via auth-modulen"""

    def __init__(self):
        self.users = {}
        self.load_users()

    def load_users(self):
        """Laddar användare via auth"""
        users_data = auth.load_users()
        self.users = {}
        for username, info in users_data.items():
            self.users[username] = User(
                username,
                info.get("role", "user"),
                info.get("permissions", [])
            )

    def save_users(self):
        """Sparar användare via auth"""
        # Vi måste läsa in nuvarande data först för att inte tappa lösenordshashar
        current_data = auth.load_users()

        for username, user in self.users.items():
            if username not in current_data:
                current_data[username] = {}
            current_data[username]["role"] = user.role
            current_data[username]["permissions"] = user.permissions

        # Ta bort användare som inte finns kvar
        for username in list(current_data.keys()):
            if username not in self.users:
                del current_data[username]

        auth.save_users(current_data)

    def add_user(self, username: str, role: str) -> str:
        """Lägger till ny användare"""
        if username in self.users:
            return f"Användare '{username}' finns redan"

        # Sätt standardlösenord "1234"
        auth.create_user(username, "1234", role)
        self.load_users()  # Ladda om för att få med den nya
        return f"Användare '{username}' tillagd med roll '{role}' och lösenord '1234'"

    def remove_user(self, username: str) -> str:
        """Tar bort användare"""
        if username not in self.users:
            return f"Användare '{username}' finns inte"
        if username == "admin" or username == "Viktor":  # Skydda admin
            return "Kan inte ta bort admin-användare"
        del self.users[username]
        self.save_users()
        return f"Användare '{username}' borttagen"

    def change_user_role(self, username: str, new_role: str) -> str:
        """Ändrar användarroll"""
        if username not in self.users:
            return f"Användare '{username}' finns inte"
        self.users[username].role = new_role
        self.save_users()
        return f"Roll för '{username}' ändrad till '{new_role}'"

    def update_permissions(self, username: str, permissions: List[str]) -> str:
        """Uppdaterar rättigheter"""
        if username not in self.users:
            return f"Användare '{username}' finns inte"
        self.users[username].permissions = permissions
        self.save_users()
        return f"Rättigheter uppdaterade för '{username}'"

    def change_password(self, username: str, new_password: str) -> str:
        """Ändrar lösenord för användare"""
        if username not in self.users:
            return f"Användare '{username}' finns inte"
        if auth.update_password(username, new_password):
            return f"Lösenord ändrat för '{username}'"
        return "Kunde inte ändra lösenord"


class AccessControl:
    """Hanterar behörigheter"""

    def __init__(self):
        self.permissions = {
            'admin': ['add_user', 'remove_user', 'change_user_role', 'view_all', 'export_data', 'import_data', 'delete_data'],
            'user': ['view_own', 'export_own']
        }

    def can_access(self, role: str, action: str) -> bool:
        """Kontrollerar om roll har behörighet"""
        return action in self.permissions.get(role, [])


class ChatManager:
    """Hanterar chattfunktioner"""

    def __init__(self):
        self.load_data()

    def load_data(self):
        """Laddar chattdata"""
        data = load_chat_data()
        self.groups = data.get("groups", [])
        self.messages = data.get("messages", [])

    def save_data(self):
        """Sparar chattdata"""
        data = {
            "groups": self.groups,
            "messages": self.messages
        }
        save_chat_data(data)

    def create_group(self, name: str, creator: str, members: List[str]) -> str:
        """Skapar ny chattgrupp"""
        group_id = str(uuid.uuid4())
        new_group = {
            "id": group_id,
            "name": name,
            "created_by": creator,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "members": members,
            "archived": False
        }
        self.groups.append(new_group)
        self.save_data()
        return group_id

    def add_message(self, group_id: str, sender: str, content: str):
        """Lägger till meddelande"""
        message = {
            "id": str(uuid.uuid4()),
            "group_id": group_id,
            "sender": sender,
            "content": content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.messages.append(message)
        self.save_data()

    def get_user_groups(self, username: str) -> List[Dict]:
        """Hämtar grupper för en användare"""
        return [g for g in self.groups if username in g.get("members", []) and not g.get("archived", False)]

    def get_archived_groups(self, username: str) -> List[Dict]:
        """Hämtar arkiverade grupper för en användare"""
        return [g for g in self.groups if username in g.get("members", []) and g.get("archived", False)]

    def get_group_messages(self, group_id: str) -> List[Dict]:
        """Hämtar meddelanden för en grupp"""
        return [m for m in self.messages if m["group_id"] == group_id]

    def archive_group(self, group_id: str):
        """Arkiverar en grupp"""
        for group in self.groups:
            if group["id"] == group_id:
                group["archived"] = True
                self.save_data()
                break

# --- ACTIVITY LOG FUNCTIONS ---


@st.cache_data(ttl=300)
def load_activity_log() -> List[Dict]:
    """Laddar aktivitetslogg från Google Sheets"""
    try:
        return db.load_data("aktivitetslogg")
    except Exception:
        return []


def save_activity_log(data: List[Dict]) -> None:
    """Sparar aktivitetslogg till Google Sheets"""
    try:
        db.save_data("aktivitetslogg", data)
        load_activity_log.clear()
    except Exception as e:
        print(f"Kunde inte spara aktivitetslogg: {e}")


def add_activity(user: str, action: str, details: str = "") -> None:
    """Lägger till en aktivitet i loggen"""
    # Vi måste ladda utan cache här för att vara säkra på att vi har senaste,
    # eller så litar vi på cachen och riskerar att skriva över om någon annan lagt till.
    # För logg är det kanske ok att bara appenda.
    # Men load_activity_log() returnerar en lista.
    # Om vi använder cache, får vi den cachade listan.
    # Om vi lägger till och sparar, skriver vi över hela listan.
    # Detta är en risk i multi-user miljö.
    # Bäst vore att bara appenda en rad till sheetet utan att läsa allt.
    # Men db_handler.save_data skriver över allt.
    # db_handler borde ha en append_row funktion.

    # För nu, låt oss rensa cachen innan vi laddar för att vara säkra.
    load_activity_log.clear()
    activity_log = load_activity_log()
    activity = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": user,
        "action": action,
        "details": details
    }
    activity_log.append(activity)
    # Behåll bara senaste 100 aktiviteter
    if len(activity_log) > 100:
        activity_log = activity_log[-100:]
    save_activity_log(activity_log)

# --- GOALS FUNCTIONS ---


@st.cache_data(ttl=300)
def load_goals() -> Dict:
    """Laddar mål från Google Sheets"""
    default_goals = {
        "Unithread": {"annual_revenue": 0, "annual_profit": 0},
        "Merchoteket": {"annual_revenue": 0, "annual_profit": 0}
    }
    try:
        rows = db.load_data("mal")
        for row in rows:
            bolag = row.get("bolag")
            if bolag in default_goals:
                default_goals[bolag]["annual_revenue"] = row.get(
                    "annual_revenue", 0)
                default_goals[bolag]["annual_profit"] = row.get(
                    "annual_profit", 0)
        return default_goals
    except Exception:
        return default_goals


def save_goals(data: Dict) -> None:
    """Sparar mål till Google Sheets"""
    rows = []
    for bolag, goals in data.items():
        row = {
            "bolag": bolag,
            "annual_revenue": goals.get("annual_revenue", 0),
            "annual_profit": goals.get("annual_profit", 0)
        }
        rows.append(row)

    try:
        db.save_data("mal", rows)
        load_goals.clear()
    except Exception as e:
        st.error(f"Kunde inte spara mål: {e}")


def calculate_yoy_change(current_data: List[Dict], last_year_data: List[Dict]) -> float:
    """Beräknar Year-over-Year förändring i procent"""
    current_total = sum(d["belopp"] for d in current_data)
    last_year_total = sum(d["belopp"] for d in last_year_data)

    if last_year_total == 0:
        return 0

    return ((current_total - last_year_total) / last_year_total) * 100

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
                add_activity(username, "Inloggning",
                             "Admin loggade in")  # NY RAD
                st.success("✅ Inloggad!")
                st.rerun()
            else:
                st.error("❌ Fel användarnamn eller lösenord")
                return False

    return False


def admin_logout():
    """Loggar ut admin"""
    add_activity(ADMIN_USERNAME, "Utloggning", "Admin loggade ut")  # NY RAD
    st.session_state.admin_logged_in = False
    st.rerun()


# --- DATAHANTERING (GOOGLE SHEETS) ---

@st.cache_data(ttl=300)
def load_expenses() -> Dict:
    """Laddar utgifter från Google Sheets och formaterar om till appens struktur"""
    default_data = {
        "Unithread": {"utgifter": [], "total": 0},
        "Merchoteket": {"utgifter": [], "total": 0}
    }

    try:
        rows = db.load_data("utgifter")

        # Bygg upp strukturen igen
        for row in rows:
            bolag = row.get("bolag")
            if bolag in default_data:
                # Ta bort 'bolag' från objektet innan vi lägger till det i listan (för att matcha gammal struktur)
                expense_item = {k: v for k, v in row.items() if k != "bolag"}
                default_data[bolag]["utgifter"].append(expense_item)

        # Beräkna totaler
        for bolag in default_data:
            default_data[bolag]["total"] = sum(
                e["belopp"] for e in default_data[bolag]["utgifter"])

        return default_data
    except Exception as e:
        st.error(f"Kunde inte ladda utgifter från databasen: {e}")
        return default_data


def save_expenses(data: Dict) -> None:
    """Sparar utgifter till Google Sheets (plattar ut strukturen)"""
    rows = []
    for bolag, content in data.items():
        for item in content["utgifter"]:
            row = item.copy()
            row["bolag"] = bolag
            rows.append(row)

    try:
        db.save_data("utgifter", rows)
        load_expenses.clear()
    except Exception as e:
        st.error(f"Kunde inte spara utgifter till databasen: {e}")


@st.cache_data(ttl=300)
def load_revenue() -> Dict:
    """Laddar intäkter från Google Sheets"""
    default_revenue = {"intakter": [], "total": 0}
    try:
        rows = db.load_data("intakter")
        default_revenue["intakter"] = rows
        default_revenue["total"] = sum(r["belopp"] for r in rows)
        return default_revenue
    except Exception as e:
        st.error(f"Kunde inte ladda intäkter: {e}")
        return default_revenue


def save_revenue(data: Dict) -> None:
    """Sparar intäkter till Google Sheets"""
    try:
        db.save_data("intakter", data["intakter"])
        load_revenue.clear()
    except Exception as e:
        st.error(f"Kunde inte spara intäkter: {e}")


@st.cache_data(ttl=300)
def load_budget() -> Dict:
    """Laddar budget från Google Sheets"""
    default_budget = {
        "Unithread": {"total": 0, "kategorier": {}},
        "Merchoteket": {"total": 0, "kategorier": {}}
    }
    try:
        rows = db.load_data("budget")
        if rows is None:
            rows = []
        for row in rows:
            bolag = row.get("bolag")
            if bolag in default_budget:
                default_budget[bolag]["total"] = row.get("total", 0)
                # Kategorier är sparade som JSON-sträng
                if "kategorier" in row and row["kategorier"]:
                    try:
                        default_budget[bolag]["kategorier"] = json.loads(
                            row["kategorier"])
                    except:
                        default_budget[bolag]["kategorier"] = {}
        return default_budget
    except Exception as e:
        # st.error(f"Kunde inte ladda budget: {e}")
        return default_budget


def save_budget(data: Dict) -> None:
    """Sparar budget till Google Sheets"""
    rows = []
    for bolag, content in data.items():
        row = {
            "bolag": bolag,
            "total": content.get("total", 0),
            "kategorier": json.dumps(content.get("kategorier", {}), ensure_ascii=False)
        }
        rows.append(row)

    try:
        db.save_data("budget", rows)
        load_budget.clear()
    except Exception as e:
        st.error(f"Kunde inte spara budget: {e}")


@st.cache_data(ttl=300)
def load_receipts() -> Dict:
    """Laddar kvittodata från Google Sheets"""
    default_receipts = {
        "users": [],
        "receipts": []
    }
    try:
        # Ladda kvitton
        receipts_rows = db.load_data("receipts")
        default_receipts["receipts"] = receipts_rows

        # Ladda användare (från kvitton.json-strukturen, men vi har dem i 'users'-fliken nu om vi migrerade rätt)
        # OBS: I migrate_to_cloud.py sparade vi 'users' till 'users'-fliken.
        # Men här i appen används 'kvitton.json' som innehåller BÅDE users och receipts.
        # Vi får slå ihop dem.

        users_rows = db.load_data("users")
        # Extrahera användarnamn från rader (om det är dicts)
        users_list = []
        for row in users_rows:
            if isinstance(row, dict):
                # Försök hitta 'username' eller ta första värdet
                if "username" in row:
                    users_list.append(row["username"])
                # Om det finns andra nycklar (t.ex. '0' från pandas default)
                elif row:
                    users_list.append(list(row.values())[0])
            elif isinstance(row, str):
                users_list.append(row)

        default_receipts["users"] = users_list

        # Städa upp kvitton om 'user' råkat bli en dict
        for r in default_receipts["receipts"]:
            if isinstance(r.get("user"), dict):
                # Försök rädda datat
                u_val = r["user"]
                if "username" in u_val:
                    r["user"] = u_val["username"]
                elif u_val:
                    r["user"] = list(u_val.values())[0]
                else:
                    r["user"] = "Unknown"

            # Parsa 'files' om det är en JSON-sträng
            if "files" in r and isinstance(r["files"], str):
                try:
                    r["files"] = json.loads(r["files"])
                except:
                    r["files"] = []

        return default_receipts
    except Exception as e:
        st.error(f"Kunde inte ladda kvitton: {e}")
        return default_receipts


def save_receipts(data: Dict) -> None:
    """Sparar kvittodata till Google Sheets (två olika flikar)"""
    try:
        if "receipts" in data:
            # Säkerställ att 'user' är en sträng i alla kvitton innan vi sparar
            clean_receipts = []
            for r in data["receipts"]:
                r_copy = r.copy()

                # Fixa user
                if isinstance(r_copy.get("user"), dict):
                    u_val = r_copy["user"]
                    if "username" in u_val:
                        r_copy["user"] = u_val["username"]
                    elif u_val:
                        r_copy["user"] = list(u_val.values())[0]
                    else:
                        r_copy["user"] = "Unknown"

                # Fixa files (serialize till JSON-sträng för Sheets)
                if "files" in r_copy and isinstance(r_copy["files"], list):
                    r_copy["files"] = json.dumps(r_copy["files"])

                # Append ALLTID, oavsett om files ändrades eller ej
                clean_receipts.append(r_copy)

            # Spara EFTER loopen
            db.save_data("receipts", clean_receipts)

        if "users" in data:
            # Konvertera lista av strängar till lista av dicts för snyggare sparning
            users_to_save = []
            for u in data["users"]:
                if isinstance(u, str):
                    users_to_save.append({"username": u})
                elif isinstance(u, dict) and "username" in u:
                    users_to_save.append(u)
                elif isinstance(u, dict):
                    # Försök hitta ett värde
                    val = list(u.values())[0] if u else "Unknown"
                    users_to_save.append({"username": val})
                else:
                    users_to_save.append({"username": str(u)})

            db.save_data("users", users_to_save)

        load_receipts.clear()
    except Exception as e:
        st.error(f"Kunde inte spara kvittodata: {e}")


@st.cache_data(ttl=300)
def load_calendar() -> Dict:
    """Laddar kalenderdata från Google Sheets"""
    default_calendar = {"events": []}
    # Vi har inte migrerat kalender än i migrate_to_cloud.py, men vi kan förbereda koden.
    # Om du vill använda kalender i molnet måste vi skapa en flik för det.
    # Låt oss anta att vi gör det.
    try:
        rows = db.load_data("kalender")
        default_calendar["events"] = rows
        return default_calendar
    except Exception:
        # Fallback till tom om fliken saknas
        return default_calendar


def save_calendar(data: Dict) -> None:
    """Sparar kalenderdata till Google Sheets"""
    try:
        db.save_data("kalender", data["events"])
        load_calendar.clear()
    except Exception as e:
        st.error(f"Kunde inte spara kalender: {e}")


def save_receipt_image(uploaded_file, receipt_id: str) -> str:
    """Laddar upp kvittobild till Google Drive och returnerar länk"""
    if uploaded_file is None:
        return None

    if '.' in uploaded_file.name and uploaded_file.name.rsplit('.', 1)[1]:
        file_extension = uploaded_file.name.rsplit('.', 1)[1]
    else:
        file_extension = "jpg"

    filename = f"{receipt_id}.{file_extension}"

    try:
        # Använd db_handler för att ladda upp
        # Vi behöver konvertera uploaded_file till en BytesIO eller liknande som db.upload_file gillar
        # Streamlit's uploaded_file beter sig som en fil, så det borde funka direkt.
        file_link = db.upload_file(uploaded_file, filename)

        # Vi returnerar länken istället för filnamnet, eller både och?
        # Appen förväntar sig nog ett filnamn för att visa det lokalt, men nu är vi i molnet.
        # Vi sparar länken i kvittot senare.
        # För bakåtkompatibilitet returnerar vi filnamnet, men vi måste ändra hur bilden visas.
        # Låt oss returnera hela länken.
        return file_link

    except Exception as e:
        st.error(f"Kunde inte ladda upp bild: {e}")
        return None


def find_duplicate_expenses(expenses: Dict) -> List[Dict]:
    """Hittar potentiella dubbletter i utgifter"""
    duplicates = []

    for business in BUSINESSES:
        utgifter = expenses[business]["utgifter"]
        for i, exp1 in enumerate(utgifter):
            for j, exp2 in enumerate(utgifter[i+1:], start=i+1):
                # Jämför datum (inom 2 dagar), belopp och leverantör
                date_diff = abs((datetime.strptime(exp1["datum"], "%Y-%m-%d") -
                                 datetime.strptime(exp2["datum"], "%Y-%m-%d")).days)

                if (date_diff <= 2 and
                    abs(exp1["belopp"] - exp2["belopp"]) < 0.01 and
                        exp1["leverantor"].lower() == exp2["leverantor"].lower()):
                    duplicates.append({
                        "business": business,
                        "original": exp1,
                        "duplicate": exp2,
                        "original_index": i,
                        "duplicate_index": j
                    })

    return duplicates


def find_duplicate_revenue(revenue: Dict) -> List[Dict]:
    """Hittar potentiella dubbletter i intäkter"""
    duplicates = []
    intakter = revenue["intakter"]

    for i, rev1 in enumerate(intakter):
        for j, rev2 in enumerate(intakter[i+1:], start=i+1):
            # Jämför datum (inom 2 dagar), belopp och kund
            date_diff = abs((datetime.strptime(rev1["datum"], "%Y-%m-%d") -
                             datetime.strptime(rev2["datum"], "%Y-%m-%d")).days)

            if (date_diff <= 2 and
                abs(rev1["belopp"] - rev2["belopp"]) < 0.01 and
                    rev1["kund"].lower() == rev2["kund"].lower()):
                duplicates.append({
                    "original": rev1,
                    "duplicate": rev2,
                    "original_index": i,
                    "duplicate_index": j
                })

    return duplicates


def remove_expense_by_index(expenses: Dict, business: str, index: int) -> None:
    """Tar bort utgift baserat på index"""
    if 0 <= index < len(expenses[business]["utgifter"]):
        expenses[business]["utgifter"].pop(index)
        expenses[business]["total"] = sum(
            u["belopp"] for u in expenses[business]["utgifter"])


def remove_revenue_by_index(revenue: Dict, index: int) -> None:
    """Tar bort intäkt baserat på index"""
    if 0 <= index < len(revenue["intakter"]):
        revenue["intakter"].pop(index)
        revenue["total"] = sum(i["belopp"] for i in revenue["intakter"])


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
        # Hantera PDF
        try:
            pdf_document = fitz.open(filepath)

            # Visa första sidan
            page = pdf_document[0]
            # 2x zoom för bättre kvalitet
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_data = pix.tobytes("png")

            st.image(img_data, caption="Kvitto (PDF)",
                     use_container_width=True)

            # Om fler än 1 sida
            if len(pdf_document) > 1:
                st.info(
                    f"📄 PDF:en innehåller {len(pdf_document)} sidor (visar sida 1)")

                # Option att visa alla sidor
                if st.checkbox("Visa alla sidor", key=f"show_all_{filename}"):
                    for page_num in range(1, len(pdf_document)):
                        page = pdf_document[page_num]
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        img_data = pix.tobytes("png")
                        st.image(
                            img_data, caption=f"Sida {page_num + 1}", use_container_width=True)

            pdf_document.close()

            # Nedladdningsknapp för PDF
            with open(filepath, 'rb') as f:
                st.download_button(
                    "📥 Ladda ner PDF",
                    data=f,
                    file_name=filename,
                    mime="application/pdf",
                    key=f"download_{filename}"
                )

        except Exception as e:
            st.error(f"Kunde inte läsa PDF: {e}")

    else:
        # Hantera bild (jpg, png)
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

    # Gruppera per månad
    monthly_totals = {}
    for d in data:
        month = d["datum"][:7]
        monthly_totals[month] = monthly_totals.get(month, 0) + d["belopp"]

    if len(monthly_totals) < 2:
        return 0

    # Ta senaste X månader
    sorted_months = sorted(monthly_totals.items())[-months:]
    values = [v for _, v in sorted_months]

    # Beräkna genomsnittlig förändring
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

    # Beräkna genomsnitt per månad
    monthly_avg = {}
    overall_avg = sum(sum(v) for v in monthly_stats.values()) / \
        sum(len(v) for v in monthly_stats.values())

    for month, values in monthly_stats.items():
        month_avg = sum(values) / len(values)
        # Procent över/under genomsnitt
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

    # Beräkna grundprognos (historiskt genomsnitt)
    base_forecast = calculate_historical_average(
        data, months=3, category=category)

    # Justera för trend
    trend = calculate_trend(data, months=6)
    trend_adjustment = (trend / 100) * months_ahead

    # Justa för säsong
    seasonality = detect_seasonality(data)
    target_month = (date.today().month + months_ahead - 1) % 12 + 1
    seasonal_factor = 1 + (seasonality.get(target_month, 0) / 100)

    # Slutlig prognos
    forecast = base_forecast * (1 + trend_adjustment) * seasonal_factor

    # Confidence baserat på datamängd
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

        # Lägg till säkerhetsmarginal (10-20% beroende på confidence)
        margin = 0.1 if forecast["confidence"] == "hög" else 0.15 if forecast["confidence"] == "medel" else 0.2
        recommended_budget = forecast["forecast"] * (1 + margin)

        recommendations[category] = {
            "prognos": forecast["forecast"],
            "rekommenderad_budget": recommended_budget,
            "marginal": margin * 100,
            "confidence": forecast["confidence"]
        }

    return recommendations


def calculate_month_completion(month_data: Dict) -> float:
    """Beräknar procent färdigställd för månad"""
    if not month_data:
        return 0.0

    total_subcategories = 0
    completed_subcategories = 0

    for kategori, subkategorier in month_data.get("kategorier", {}).items():
        for subkat, data in subkategorier.items():
            total_subcategories += 1
            if data.get("filer"):
                completed_subcategories += 1

    return (completed_subcategories / total_subcategories * 100) if total_subcategories > 0 else 0


@st.cache_data(ttl=300)
def load_bokforing() -> Dict:
    """Laddar bokföringsdata från Google Sheets"""
    default_bokforing = {
        "Unithread": {},
        "Merchoteket": {}
    }
    try:
        rows = db.load_data("bokforing")
        for row in rows:
            bolag = row.get("bolag")
            ar = str(row.get("ar"))
            manad = str(row.get("manad"))
            data_json = row.get("data")

            if bolag not in default_bokforing:
                default_bokforing[bolag] = {}

            if ar not in default_bokforing[bolag]:
                default_bokforing[bolag][ar] = {}

            if data_json:
                try:
                    default_bokforing[bolag][ar][manad] = json.loads(data_json)
                except:
                    default_bokforing[bolag][ar][manad] = {}

        return default_bokforing
    except Exception:
        return default_bokforing


def save_bokforing(data: Dict) -> None:
    """Sparar bokföringsdata till Google Sheets"""
    rows = []
    for bolag, years in data.items():
        for ar, months in years.items():
            for manad, content in months.items():
                row = {
                    "bolag": bolag,
                    "ar": ar,
                    "manad": manad,
                    "status": content.get("status", "ej_paborjad"),
                    "data": json.dumps(content, ensure_ascii=False)
                }
                rows.append(row)
    try:
        db.save_data("bokforing", rows)
        load_bokforing.clear()
    except Exception as e:
        st.error(f"Kunde inte spara bokföring: {e}")


def get_month_status_color(status: str) -> str:
    """Returnerar färgkod för månadsstatus"""
    colors = {
        "bokford": "#10b981",
        "saknas_underlag": "#f59e0b",
        "paborjad": "#fbbf24",
        "ej_paborjad": "#ef4444"
    }
    return colors.get(status, "#9ca3af")


def get_month_template(month: int) -> Dict:
    """Returnerar mall för specifik månad"""

    base_template = {
        "status": "ej_paborjad",
        "kategorier": {
            "Intäkter": {
                "Fakturaunderlag": {"filer": [], "kommentarer": {}},
                "Kontoutdrag": {"filer": [], "kommentarer": {}},
                "Betalningsbekräftelser": {"filer": [], "kommentarer": {}}
            },
            "Utgifter": {
                "Kvitton": {"filer": [], "kommentarer": {}},
                "Fakturor leverantörer": {"filer": [], "kommentarer": {}},
                "Löneunderlag": {"filer": [], "kommentarer": {}},
                "Skatter & avgifter": {"filer": [], "kommentarer": {}},
                "Övriga utgifter": {"filer": [], "kommentarer": {}}
            },
            "Avstämningar": {
                "Bankkontoutdrag": {"filer": [], "kommentarer": {}},
                "Kreditkortsutdrag": {"filer": [], "kommentarer": {}},
                "Saldolistor": {"filer": [], "kommentarer": {}}
            }
        }
    }

    if month == 12:
        base_template["kategorier"]["Bokslut"] = {
            "Lagerinventeringar": {"filer": [], "kommentarer": {}},
            "Pågående arbeten": {"filer": [], "kommentarer": {}},
            "Årsredovisning": {"filer": [], "kommentarer": {}},
            "Avstämningar": {"filer": [], "kommentarer": {}}
        }

    return base_template


def save_bokforing_file(uploaded_file, business: str, year: int, month: int, kategori: str, subkategori: str) -> str:
    """Sparar bokföringsfil till Google Drive och returnerar länk"""
    if uploaded_file is None:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_extension = uploaded_file.name.split(
        '.')[-1] if '.' in uploaded_file.name else "file"
    filename = f"{business}_{year}_{month}_{kategori}_{subkategori}_{timestamp}.{file_extension}"

    try:
        file_link = db.upload_file(uploaded_file, filename)
        return file_link
    except Exception as e:
        st.error(f"Kunde inte ladda upp fil: {e}")
        return None


def get_bokforing_file_path(business: str, year: int, month: int, filename: str) -> Path:
    """Returnerar fullständig sökväg till bokföringsfil (Legacy)"""
    return BOKFORING_FILES_DIR / business / str(year) / f"{month:02d}" / filename


# --- CHATT FUNCTIONS ---

@st.cache_data(ttl=300)
def load_chat_data() -> Dict:
    """Laddar chattdata från Google Sheets"""
    default_chat = {"groups": [], "messages": []}
    try:
        rows = db.load_data("chatt")
        groups = []
        messages = []
        for row in rows:
            if row.get("type") == "group":
                try:
                    groups.append(json.loads(row.get("data")))
                except:
                    pass
            elif row.get("type") == "message":
                try:
                    messages.append(json.loads(row.get("data")))
                except:
                    pass

        if not groups and not messages:
            return default_chat

        return {"groups": groups, "messages": messages}
    except Exception:
        return default_chat


def save_chat_data(data: Dict) -> None:
    """Sparar chattdata till Google Sheets"""
    rows = []
    for group in data.get("groups", []):
        rows.append({
            "id": group["id"],
            "type": "group",
            "data": json.dumps(group, ensure_ascii=False)
        })
    for message in data.get("messages", []):
        # Skapa ett unikt ID för meddelandet om det saknas
        msg_id = message.get("timestamp", "") + "_" + message.get("sender", "")
        rows.append({
            "id": msg_id,
            "type": "message",
            "data": json.dumps(message, ensure_ascii=False)
        })

    try:
        db.save_data("chatt", rows)
        load_chat_data.clear()
    except Exception as e:
        st.error(f"Kunde inte spara chatt: {e}")


def create_chat_group(name: str, creator: str, members: List[str]) -> str:
    """Skapar en ny chattgrupp"""
    chat_data = load_chat_data()
    group_id = str(uuid.uuid4())

    new_group = {
        "id": group_id,
        "name": name,
        "created_by": creator,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "members": members,
        "archived": False
    }

    chat_data["groups"].append(new_group)
    save_chat_data(chat_data)
    return group_id


def add_chat_message(group_id: str, sender: str, content: str) -> None:
    """Lägger till ett meddelande i en grupp"""
    chat_data = load_chat_data()

    new_message = {
        "id": str(uuid.uuid4()),
        "group_id": group_id,
        "sender": sender,
        "content": content,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "archived": False
    }

    chat_data["messages"].append(new_message)
    save_chat_data(chat_data)


def get_user_chats(username: str) -> List[Dict]:
    """Hämtar alla chattgrupper en användare är med i"""
    chat_data = load_chat_data()
    return [g for g in chat_data["groups"] if username in g["members"] and not g.get("archived", False)]


def get_chat_messages(group_id: str) -> List[Dict]:
    """Hämtar alla meddelanden för en grupp"""
    chat_data = load_chat_data()
    return [m for m in chat_data["messages"] if m["group_id"] == group_id and not m.get("archived", False)]


def archive_chat_group(group_id: str) -> None:
    """Arkiverar en chattgrupp"""
    chat_data = load_chat_data()
    for group in chat_data["groups"]:
        if group["id"] == group_id:
            group["archived"] = True
            break
    save_chat_data(chat_data)


# --- STREAMLIT APP (ENDAST EN GÅNG!) ---
st.set_page_config(page_title="Företagsekonomi AI",
                   page_icon="🏢", layout="wide")

# Hantera URL-parametrar för navigering
# if "selected_day" in st.query_params:
#     st.session_state.selected_day = st.query_params["selected_day"]
#     st.session_state.main_menu_radio = "📅 Kalender"

# Rensa eventuella gamla query params som kan störa
if "selected_day" in st.query_params:
    st.query_params.clear()

# Ladda data (ENDAST EN GÅNG!)
expenses = load_expenses()
revenue = load_revenue()
budget = load_budget()
receipts_data = load_receipts()
calendar_data = load_calendar()
activity_log = load_activity_log()
goals = load_goals()
bokforing_data = load_bokforing()

# Initiera användarhantering (ENDAST EN GÅNG!)
if 'user_manager' not in st.session_state:
    st.session_state.user_manager = UserManager()
if 'access_control' not in st.session_state:
    st.session_state.access_control = AccessControl()
if 'chat_manager' not in st.session_state:
    st.session_state.chat_manager = ChatManager()

user_manager = st.session_state.user_manager
access_control = st.session_state.access_control
chat_manager = st.session_state.chat_manager

# Hantera navigering via query parameters (för kalender)
# if "selected_day" in st.query_params:
#     st.session_state.selected_day = st.query_params["selected_day"]
#     st.session_state.main_menu_radio = "📅 Kalender"

# --- SIDEBAR (ENDAST EN GÅNG!) ---
st.sidebar.title("🏢 Företagsekonomi")
st.sidebar.markdown("---")

# --- SIDEBAR HEADER ---
with st.sidebar:
    st.markdown("""
        <div style="text-align: center; padding: 1rem 0; margin-bottom: 2rem;">
            <div style="
                width: 60px;
                height: 60px;
                background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
                border-radius: 16px;
                margin: 0 auto 1rem auto;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 2rem;
                box-shadow: 0 10px 15px -3px rgba(79, 70, 229, 0.3);
            ">
                💼
            </div>
            <h2 style="font-size: 1.2rem; margin: 0; color: #0f172a;">Företagsekonomi</h2>
            <p style="font-size: 0.8rem; color: #64748b; margin: 0;">Allt-i-ett lösning</p>
            <p style="font-size: 0.7rem; color: #10b981; margin-top: 5px;">✅ v1.2.2 (Lokal)</p>
        </div>
    """, unsafe_allow_html=True)

# Bygg meny baserat på behörigheter
menu_options = [
    "📊 Dashboard",
    "💰 Utgifter",
    "💵 Intäkter",
    "📈 Budget & Prognos",
    "📄 Kvittoredovisning",
    "📅 Kalender",
    "📚 Bokföringsstöd",
    "🔍 Dubbletthantering"
]

if auth.has_permission("access_reports"):
    menu_options.append("📋 Rapporter")

if auth.has_permission("access_settings"):
    menu_options.append("⚙️ Inställningar")


def on_menu_change():
    """Callback när menyn ändras"""
    # Rensa vald dag om vi lämnar kalendern
    if st.session_state.main_menu_radio != "📅 Kalender":
        st.session_state.pop("selected_day", None)


main_menu = st.sidebar.radio(
    "Huvudmeny",
    menu_options,
    key="main_menu_radio",  # unik nyckel för att undvika ID-krockar
    on_change=on_menu_change
)

# --- FLYTANDE CHATT (EGEN IMPLEMENTATION) ---
# Flyttad till slutet av filen för att inte störa layouten


st.sidebar.markdown("### 📢 Senaste aktiviteter")

recent_activities = activity_log[-5:] if activity_log else []
for activity in reversed(recent_activities):
    time_diff = datetime.now() - \
        datetime.strptime(activity["timestamp"], "%Y-%m-%d %H:%M:%S")

    if time_diff.total_seconds() < 3600:
        time_ago = f"{int(time_diff.total_seconds() / 60)} min sedan"
    elif time_diff.total_seconds() < 86400:
        time_ago = f"{int(time_diff.total_seconds() / 3600)} tim sedan"
    else:
        time_ago = f"{int(time_diff.days)} dag(ar) sedan"

    st.sidebar.markdown(f"""
        <div style='background: rgba(255,255,255,0.1); padding: 8px; border-radius: 6px; margin-bottom: 6px; border-left: 3px solid #10b981;'>
            <div style='font-size: 0.7rem; opacity: 0.8;'>{time_ago}</div>
            <div style='font-size: 0.85rem;'><strong>{activity['user']}</strong></div>
            <div style='font-size: 0.8rem;'>{activity['action']}</div>
        </div>
    """, unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.caption("v1.2.3 - Debug Mode")
if st.sidebar.button("🚪 Logga ut", type="secondary", use_container_width=True):
    auth.logout()

if not recent_activities:
    st.sidebar.info("Ingen aktivitet än")

# --- DASHBOARD (FÖRBÄTTRAD) ---
if main_menu == "📊 Dashboard":
    st.title("📊 Dashboard")
    st.markdown("### Översikt & Nyckeltal")

    # Beräkna data (YTD - Innevarande år)
    current_year = str(date.today().year)

    # Intäkter YTD
    total_revenue = sum(r["belopp"] for r in revenue["intakter"]
                        if r["datum"].startswith(current_year))

    # Utgifter YTD
    total_expenses = sum(sum(e["belopp"] for e in expenses[b]["utgifter"]
                             if e["datum"].startswith(current_year)) for b in BUSINESSES)

    total_profit = total_revenue - total_expenses
    profit_margin = (total_profit/total_revenue *
                     100 if total_revenue > 0 else 0)

    # Beräkna YoY-förändring
    current_month = date.today().strftime("%Y-%m")
    last_year_month = (date.today().replace(
        year=date.today().year - 1)).strftime("%Y-%m")

    current_month_revenue = [
        r for r in revenue["intakter"] if r["datum"].startswith(current_month)]
    last_year_month_revenue = [
        r for r in revenue["intakter"] if r["datum"].startswith(last_year_month)]
    yoy_change = calculate_yoy_change(
        current_month_revenue, last_year_month_revenue)

    # Custom CSS Cards
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Intäkt ({current_year})</div>
            <div class="metric-value">{total_revenue:,.0f} kr</div>
            <div class="metric-delta {'delta-positive' if yoy_change >= 0 else 'delta-negative'}">
                {yoy_change:+.1f}% YoY
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Utgift ({current_year})</div>
            <div class="metric-value">{total_expenses:,.0f} kr</div>
            <div class="metric-label" style="font-size: 0.8rem; margin-top: 4px;">Löpande kostnader</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Nettovinst ({current_year})</div>
            <div class="metric-value" style="color: {'#166534' if total_profit >= 0 else '#991b1b'}">{total_profit:,.0f} kr</div>
            <div class="metric-delta {'delta-positive' if profit_margin >= 20 else 'delta-negative'}">
                {profit_margin:.1f}% marginal
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        annual_goal = sum(goals[b].get("annual_revenue", 0)
                          for b in BUSINESSES)
        ytd_revenue = sum(r["belopp"] for r in revenue["intakter"]
                          if r["datum"].startswith(str(date.today().year)))
        goal_progress = (ytd_revenue / annual_goal *
                         100) if annual_goal > 0 else 0

        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Årsmål</div>
            <div class="metric-value">{goal_progress:.0f}%</div>
            <div class="metric-label" style="font-size: 0.8rem; margin-top: 4px;">{ytd_revenue:,.0f} / {annual_goal:,.0f} kr</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Grafer
    col_main, col_side = st.columns([2, 1])

    with col_main:
        st.markdown("### 📈 Trendanalys (6 mån)")

        months = []
        revenue_by_month = []
        expenses_by_month = []
        profit_by_month = []

        for month_idx in range(5, -1, -1):
            month_date = date.today() - timedelta(days=month_idx*30)
            month_str = month_date.strftime("%Y-%m")
            month_name = month_date.strftime("%b")
            months.append(month_name)

            m_rev = sum(rev["belopp"] for rev in revenue["intakter"]
                        if rev["datum"].startswith(month_str))
            m_exp = sum(sum(exp["belopp"] for exp in expenses[b]["utgifter"]
                        if exp["datum"].startswith(month_str)) for b in BUSINESSES)

            revenue_by_month.append(m_rev)
            expenses_by_month.append(m_exp)
            profit_by_month.append(m_rev - m_exp)

        fig = go.Figure()

        # Intäkter Area
        fig.add_trace(go.Scatter(
            x=months, y=revenue_by_month, mode='lines', name='Intäkter',
            line=dict(color='#10b981', width=3),
            fill='tozeroy', fillcolor='rgba(16, 185, 129, 0.1)'
        ))

        # Utgifter Line
        fig.add_trace(go.Scatter(
            x=months, y=expenses_by_month, mode='lines+markers', name='Utgifter',
            line=dict(color='#ef4444', width=3),
            marker=dict(size=8)
        ))

        fig.update_layout(
            template="plotly_white",
            height=400,
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", yanchor="bottom",
                        y=1.02, xanchor="right", x=1),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_side:
        st.markdown("### 📊 Fördelning")

        # Intäkter per verksamhet
        rev_per_business = {}
        for r in revenue["intakter"]:
            b = r.get("verksamhet", "Okänd")
            rev_per_business[b] = rev_per_business.get(b, 0) + r["belopp"]

        if rev_per_business:
            fig_pie = px.pie(
                values=list(rev_per_business.values()),
                names=list(rev_per_business.keys()),
                hole=0.6,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_layout(
                showlegend=True,
                height=300,
                margin=dict(l=20, r=20, t=0, b=0),
                annotations=[dict(text='Intäkter', x=0.5, y=0.5,
                                  font_size=14, showarrow=False)]
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Ingen data att visa")

        # Momsöversikt (Enkel)
        st.markdown("### 🏛️ Momsstatus (Est.)")
        # Här skulle vi kunna räkna ut moms om vi hade datan
        st.info("Momsdata kommer snart...")

    with col_side:
        st.markdown("### 📢 Aktivitetsflöde")

        if activity_log:
            # Visa endast 5 senaste
            for activity in reversed(activity_log[-5:]):
                time_diff = datetime.now() - \
                    datetime.strptime(
                    activity["timestamp"], "%Y-%m-%d %H:%M:%S")

                if time_diff.total_seconds() < 3600:
                    time_ago = f"{int(time_diff.total_seconds() / 60)} min"
                elif time_diff.total_seconds() < 86400:
                    time_ago = f"{int(time_diff.total_seconds() / 3600)} tim"
                else:
                    time_ago = f"{int(time_diff.days)} dag"

                st.markdown(f"""
                    <div style='background: white; padding: 10px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #4f46e5;'>
                        <div style='display: flex; justify-content: space-between;'>
                            <strong>{activity['action']}</strong>
                            <span style='color: #64748b; font-size: 0.9em;'>{activity['timestamp']}</span>
                        </div>
                        <div style='margin-top: 5px;'>
                            <span style='background-color: #e0e7ff; color: #4338ca; padding: 2px 8px; border-radius: 12px; font-size: 0.8em;'>👤 {activity['user']}</span>
                            <span style='margin-left: 10px; color: #475569;'>{activity['details']}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

            # Länk till full logg
            st.markdown("---")
            st.info(
                "💡 Se hela aktivitetsloggen under **Inställningar** → **Aktivitetslogg**")
        else:
            st.info("Ingen aktivitet än")

    st.markdown("---")

    # NY: Mål & KPI-sektion
    st.markdown("### 🎯 Mål & Prestanda")

    col1, col2 = st.columns(2)

    for idx, business in enumerate(BUSINESSES):
        with [col1, col2][idx]:
            st.markdown(f"#### {business}")

            annual_revenue_goal = goals[business].get("annual_revenue", 0)
            annual_profit_goal = goals[business].get("annual_profit", 0)

            ytd_revenue = sum(r["belopp"] for r in revenue["intakter"]
                              if r["datum"].startswith(str(date.today().year)) and r.get("verksamhet") == business)
            ytd_expenses = sum(e["belopp"] for e in expenses[business]["utgifter"]
                               if e["datum"].startswith(str(date.today().year)))
            ytd_profit = ytd_revenue - ytd_expenses

            revenue_progress = (
                ytd_revenue / annual_revenue_goal * 100) if annual_revenue_goal > 0 else 0
            profit_progress = (ytd_profit / annual_profit_goal *
                               100) if annual_profit_goal > 0 else 0

            # Revenue progress
            st.markdown("**💰 Intäktsmål**")
            progress_color = "#10b981" if revenue_progress >= 75 else "#f59e0b" if revenue_progress >= 50 else "#ef4444"
            st.markdown(f"""
                <div style="background-color: #f0f0f0; border-radius: 10px; padding: 3px; margin: 10px 0;">
                    <div style="background: {progress_color}; width: {min(revenue_progress, 100)}%; border-radius: 8px; padding: 12px; color: white; font-weight: bold; text-align: center; transition: width 0.5s ease;">
                        {revenue_progress:.0f}%
                    </div>
                </div>
                <div style="text-align: center; font-size: 0.875rem; font-weight: 600;">
                    {ytd_revenue:,.0f} kr / {annual_revenue_goal:,.0f} kr
                </div>
            """, unsafe_allow_html=True)

            # Profit progress
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**📈 Vinstmål**")
            profit_color = "#10b981" if profit_progress >= 75 else "#f59e0b" if profit_progress >= 50 else "#ef4444"
            st.markdown(f"""
                <div style="background-color: #f0f0f0; border-radius: 10px; padding: 3px; margin: 10px 0;">
                    <div style="background: {profit_color}; width: {min(profit_progress, 100)}%; border-radius: 8px; padding: 12px; color: white; font-weight: bold; text-align: center;">
                        {profit_progress:.0f}%
                    </div>
                </div>
                <div style="text-align: center; font-size: 0.875rem; font-weight: 600;">
                    {ytd_profit:,.0f} kr / {annual_profit_goal:,.0f} kr
                </div>
            """, unsafe_allow_html=True)

            if revenue_progress >= 100:
                st.success("🎉 Intäktsmålet uppnått!")
            elif revenue_progress >= 75:
                st.info("🟢 På väg mot målet!")
            elif revenue_progress >= 50:
                st.warning("🟡 Måttlig framgång")
            else:
                st.error("🔴 Behöver öka tempo")

    st.markdown("---")

    # NY: Jämför mot förra året
    st.markdown("### 📊 Jämförelse mot förra året")

    comparison_data = []

    for month_offset in range(5, -1, -1):
        month_date = date.today() - timedelta(days=month_offset*30)
        current_month = month_date.strftime("%Y-%m")
        last_year_month = month_date.replace(
            year=month_date.year - 1).strftime("%Y-%m")
        month_name = month_date.strftime("%b")

        current_rev = sum(r["belopp"] for r in revenue["intakter"]
                          if r["datum"].startswith(current_month))
        last_year_rev = sum(r["belopp"] for r in revenue["intakter"]
                            if r["datum"].startswith(last_year_month))

        comparison_data.append({
            "Månad": month_name,
            f"Intäkt {date.today().year}": current_rev,
            f"Intäkt {date.today().year - 1}": last_year_rev
        })

    df_comparison = pd.DataFrame(comparison_data)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name=f'Intäkt {date.today().year}',
        x=df_comparison["Månad"],
        y=df_comparison[f"Intäkt {date.today().year}"],
        marker_color='#10b981'
    ))

    fig.add_trace(go.Bar(
        name=f'Intäkt {date.today().year - 1}',
        x=df_comparison["Månad"],
        y=df_comparison[f"Intäkt {date.today().year - 1}"],
        marker_color='#6ee7b7',
        opacity=0.6
    ))

    fig.update_layout(barmode='group', height=400, template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

    total_current = df_comparison[f"Intäkt {date.today().year}"].sum()
    total_last_year = df_comparison[f"Intäkt {date.today().year - 1}"].sum()
    total_yoy = ((total_current - total_last_year) /
                 total_last_year * 100) if total_last_year > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("📈 Tillväxt YoY", f"{total_yoy:+.1f}%")
    col2.metric(f"💰 Intäkt {date.today().year}",
                f"{total_current:,.0f} kr")
    col3.metric(f"💰 Intäkt {date.today().year - 1}",
                f"{total_last_year:,.0f} kr")

# --- UTGIFTER (LÄGG TILL AKTIVITETSLOGGNING) ---
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
                datum = st.date_input("📅 Datum", value=date.today())  # NY RAD

            with col2:
                leverantor = st.text_input("🏪 Leverantör")
                belopp = st.number_input(
                    "💰 Belopp (inkl. moms)", min_value=0.0, step=0.01, format="%.2f")
                moms_sats = st.selectbox("Moms (%)", [0, 6, 12, 25], index=3)

            submitted = st.form_submit_button("💾 Registrera", type="primary")

        if submitted and beskrivning and leverantor and belopp > 0:
            moms_belopp = belopp * (moms_sats / (100 + moms_sats))
            utgift = {
                "datum": datum.strftime("%Y-%m-%d"),
                "kategori": kategori,
                "beskrivning": beskrivning,
                "leverantor": leverantor,
                "belopp": belopp,
                "moms_sats": moms_sats,
                "moms_belopp": round(moms_belopp, 2)
            }
            expenses[verksamhet]["utgifter"].append(utgift)
            expenses[verksamhet]["total"] = sum(
                u["belopp"] for u in expenses[verksamhet]["utgifter"])
            save_expenses(expenses)

            # NY: Logga aktivitet
            add_activity(
                ADMIN_USERNAME, f"Lade till utgift: {beskrivning}", f"{belopp:,.0f} kr ({verksamhet})")

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

# --- INTÄKTER (LÄGG TILL AKTIVITETSLOGGNING) ---
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
                datum = st.date_input("📅 Datum", value=date.today())  # NY RAD

            with col2:
                kund = st.text_input("👤 Kund")
                belopp = st.number_input(
                    "💰 Belopp (kr)", min_value=0.0, step=0.01, format="%.2f")

            submitted = st.form_submit_button("💾 Registrera", type="primary")

            if submitted and beskrivning and kund and belopp > 0:
                intakt = {
                    # ÄNDRAD RAD (var: datetime.now().strftime("%Y-%m-%d"))
                    "datum": datum.strftime("%Y-%m-%d"),
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

                # NY: Logga aktivitet
                add_activity(
                    ADMIN_USERNAME, f"Lade till intäkt: {beskrivning}", f"{belopp:,.0f} kr ({verksamhet})")

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

# --- BOKFÖRINGSSTÖD ---
elif main_menu == "📚 Bokföringsstöd":
    st.title("📚 Bokföringsstöd")

    months_sv = ["Januari", "Februari", "Mars", "April", "Maj", "Juni",
                 "Juli", "Augusti", "September", "Oktober", "November", "December"]

    # Välj verksamhet
    business = st.selectbox("🏢 Verksamhet", BUSINESSES, key="bk_business")

    # Välj år och månad
    col_y, col_m = st.columns(2)
    with col_y:
        year = st.number_input("📆 År", min_value=2020, max_value=2035,
                               value=date.today().year, key=f"bk_year_{business}")
    with col_m:
        month = st.selectbox("📅 Månad", list(range(1, 13)), index=date.today(
        ).month-1, format_func=lambda x: months_sv[x-1], key=f"bk_month_{business}_{year}")

    # Initiera datastruktur
    year_key = str(year)
    month_key = f"{month:02d}"
    if business not in bokforing_data:
        bokforing_data[business] = {}
    if year_key not in bokforing_data[business]:
        bokforing_data[business][year_key] = {}
    if month_key not in bokforing_data[business][year_key]:
        bokforing_data[business][year_key][month_key] = get_month_template(
            month)
        save_bokforing(bokforing_data)

    month_data = bokforing_data[business][year_key][month_key]

    # Status
    status_labels = {
        "ej_paborjad": "⭕ Ej påbörjad",
        "paborjad": "🟡 Påbörjad",
        "saknas_underlag": "⚠️ Saknar underlag",
        "bokford": "✅ Bokförd",
    }
    current_status = month_data.get("status", "ej_paborjad")
    new_status = st.selectbox(
        "📊 Status",
        list(status_labels.keys()),
        index=list(status_labels.keys()).index(current_status),
        format_func=lambda s: status_labels[s],
        key=f"bk_status_{business}_{year}_{month}"
    )
    if new_status != current_status:
        month_data["status"] = new_status
        save_bokforing(bokforing_data)
        st.success("✅ Status uppdaterad")

    # Progress
    completion = calculate_month_completion(month_data)
    st.metric("📈 Färdigställande", f"{completion:.0f}%")
    st.markdown("---")
    st.subheader(f"📁 Underlag: {months_sv[month-1]} {year}")

    # Kategorier och subkategorier
    for kategori, subkategorier in month_data.get("kategorier", {}).items():
        with st.expander(f"📂 {kategori}", expanded=True):
            for subkategori, data in subkategorier.items():
                st.markdown(f"**{subkategori}**")

                # Uppladdning
                files = st.file_uploader(
                    f"Ladda upp till {subkategori}",
                    type=["pdf", "jpg", "jpeg", "png", "xlsx", "docx"],
                    accept_multiple_files=True,
                    key=f"bk_upload_{business}_{year}_{month}_{kategori}_{subkategori}"
                )
                if files:
                    for f in files:
                        saved_name = save_bokforing_file(
                            f, business, year, month, kategori, subkategori)
                        if saved_name:
                            data.setdefault("filer", []).append({
                                "filename": saved_name,
                                "original_name": f.name,
                                "uploaded": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "size": f.size
                            })
                            save_bokforing(bokforing_data)
                            st.success(f"✅ {len(files)} fil(er) uppladdade")
                            st.rerun()  # FIX: Använd st.rerun() istället för st.experimental_rerun()

                # Lista filer + kommentarer + ta bort
                for idx, fil in enumerate(data.get("filer", [])):
                    filename_or_link = fil["filename"]

                    cols = st.columns([3, 2, 1])
                    with cols[0]:
                        st.write(f"📄 {fil['original_name']}")
                        st.caption(
                            f"Uppladdad: {fil['uploaded']} • {fil['size']/1024:.1f} KB")

                        if filename_or_link.startswith("http"):
                            st.link_button("📥 Öppna fil", filename_or_link)
                        else:
                            # Legacy local file support
                            file_path = get_bokforing_file_path(
                                business, year, month, filename_or_link)
                            if file_path.exists():
                                with open(file_path, 'rb') as f:
                                    st.download_button(
                                        "📥 Ladda ner",
                                        data=f,
                                        file_name=fil["original_name"],
                                        key=f"bk_dl_{business}_{year}_{month}_{kategori}_{subkategori}_{idx}"
                                    )

                    with cols[1]:
                        existing_comment = data.setdefault(
                            "kommentarer", {}).get(fil["filename"], "")
                        new_comment = st.text_input(
                            "💬 Kommentar",
                            value=existing_comment,
                            key=f"bk_comment_{business}_{year}_{month}_{kategori}_{subkategori}_{idx}"
                        )
                        if new_comment != existing_comment:
                            data["kommentarer"][fil["filename"]] = new_comment
                            save_bokforing(bokforing_data)
                            st.toast("Kommentar sparad", icon="💾")
                    with cols[2]:
                        if st.button("🗑️", key=f"bk_del_{business}_{year}_{month}_{kategori}_{subkategori}_{idx}", help="Ta bort fil"):
                            try:
                                if file_path.exists():
                                    file_path.unlink()
                            except Exception:
                                pass
                            data["filer"].pop(idx)
                            data.get("kommentarer", {}).pop(
                                fil["filename"], None)
                            save_bokforing(bokforing_data)
                            st.success("✅ Fil borttagen")
                            st.rerun()  # FIX: Använd st.rerun() istället för st.experimental_rerun()

# --- KVITTOREDOVISNING (KOMPLETT FÖRBÄTTRAD!) ---
elif main_menu == "📄 Kvittoredovisning":
    st.title("📄 Kvittoredovisning - Komplett System")

    # Custom CSS för kvitton
    st.markdown("""
        <style>
        .receipt-card {
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        .receipt-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .status-inlamnat { background: #fef3c7; color: #92400e; }
        .status-godkannt { background: #d1fae5; color: #065f46; }
        .status-avvisat { background: #fee2e2; color: #991b1b; }
        .upload-zone {
            border: 2px dashed #cbd5e1;
            border-radius: 10px;
            padding: 30px;
            text-align: center;
            background: #f8fafc;
            transition: all 0.3s ease;
        }
        .upload-zone:hover {
            border-color: #667eea;
            background: #eef2ff;
        }
        </style>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Dashboard",
        "👥 Användare",
        "📤 Ladda upp",
        "✅ Granska",
        "📅 Månadsrapport",
        "📈 Statistik"
    ])

    # TAB 1: DASHBOARD
    with tab1:
        st.subheader("📊 Översikt Kvittoredovisning")

        # Beräkna statistik
        total_receipts = len(receipts_data["receipts"])
        total_amount = sum(r.get("belopp", 0)
                           for r in receipts_data["receipts"])

        # Status-räkning
        pending = len([r for r in receipts_data["receipts"]
                       if r.get("status") == "inlamnat"])
        approved = len([r for r in receipts_data["receipts"]
                        if r.get("status") == "godkannt"])
        rejected = len([r for r in receipts_data["receipts"]
                        if r.get("status") == "avvisat"])

        # Denna månad
        current_month = date.today().strftime("%Y-%m")
        month_receipts = [r for r in receipts_data["receipts"]
                          if r.get("datum", "").startswith(current_month)]
        month_amount = sum(r.get("belopp", 0) for r in month_receipts)

        # KPI-kort
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📋 Totalt kvitton", total_receipts)
        col2.metric("💰 Totalt belopp", f"{total_amount:,.0f} kr")
        col3.metric("⏳ Väntar granskning", pending)
        col4.metric("📅 Denna månad", f"{month_amount:,.0f} kr")

        st.markdown("---")

        # Status-översikt
        st.markdown("### 📊 Status-översikt")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f"""
                <div class="receipt-card" style="border-left: 4px solid #f59e0b;">
                    <h3 style="color: #f59e0b; margin: 0;">⏳ Väntar</h3>
                    <p style="font-size: 2rem; font-weight: bold; margin: 10px 0;">{pending}</p>
                    <p style="color: #64748b; margin: 0;">{(pending/total_receipts*100 if total_receipts > 0 else 0):.0f}% av totalt</p>
                </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
                <div class="receipt-card" style="border-left: 4px solid #10b981;">
                    <h3 style="color: #10b981; margin: 0;">✅ Godkända</h3>
                    <p style="font-size: 2rem; font-weight: bold; margin: 10px 0;">{approved}</p>
                    <p style="color: #64748b; margin: 0;">{(approved/total_receipts*100 if total_receipts > 0 else 0):.0f}% av totalt</p>
                </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
                <div class="receipt-card" style="border-left: 4px solid #ef4444;">
                    <h3 style="color: #ef4444; margin: 0;">❌ Avvisade</h3>
                    <p style="font-size: 2rem; font-weight: bold; margin: 10px 0;">{rejected}</p>
                    <p style="color: #64748b; margin: 0;">{(rejected/total_receipts*100 if total_receipts > 0 else 0):.0f}% av totalt</p>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # Per användare
        st.markdown("### 👥 Per användare")

        user_stats = {}
        for receipt in receipts_data["receipts"]:
            user = receipt.get("user", "Okänd")
            if user not in user_stats:
                user_stats[user] = {"count": 0, "amount": 0, "pending": 0}
            user_stats[user]["count"] += 1
            user_stats[user]["amount"] += receipt.get("belopp", 0)
            if receipt.get("status") == "inlamnat":
                user_stats[user]["pending"] += 1

        for user, stats in user_stats.items():
            with st.expander(f"👤 {user} - {stats['count']} kvitton ({stats['amount']:,.0f} kr)"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Antal", stats['count'])
                col2.metric("Belopp", f"{stats['amount']:,.0f} kr")
                col3.metric("Väntar", stats['pending'])

        st.markdown("---")

        # Senaste aktivitet
        st.markdown("### 🕐 Senaste kvitton")
        recent = receipts_data["receipts"][-5:]
        for r in reversed(recent):
            status_class = f"status-{r.get('status', 'inlamnat')}"
            status_text = {"inlamnat": "⏳ Väntar", "godkannt": "✅ Godkänt",
                           "avvisat": "❌ Avvisad"}.get(r.get('status'), "⏳")

            st.markdown(f"""
                <div class="receipt-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong>{r.get('beskrivning', 'Okänd')}</strong>
                            <div style="color: #64748b; font-size: 0.85rem;">
                                👤 {r.get('user', 'Okänd')} • 📅 {r.get('datum', '')} • 💰 {r.get('belopp', 0):,.0f} kr
                            </div>
                        </div>
                        <span class="status-badge {status_class}">{status_text}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    # TAB 2: ANVÄNDARE
    with tab2:
        st.subheader("👥 Hantera användare")

        col1, col2 = st.columns([2, 1])

        with col1:
            with st.form("add_receipt_user"):
                new_user = st.text_input("👤 Nytt användarnamn")
                user_email = st.text_input("📧 E-post (valfritt)")

                if st.form_submit_button("➕ Lägg till användare", type="primary"):
                    if new_user and new_user not in receipts_data["users"]:
                        receipts_data["users"].append(new_user)
                        save_receipts(receipts_data)
                        add_activity(ADMIN_USERNAME,
                                     f"Lade till kvittoanvändare", new_user)
                        st.success(f"✅ Användare {new_user} tillagd!")
                        st.rerun()
                    else:
                        st.error("❌ Användarnamn finns redan eller är tomt")

        with col2:
            st.info(f"📊 **{len(receipts_data['users'])}** aktiva användare")

        if receipts_data["users"]:
            st.markdown("---")
            st.markdown("### 📋 Befintliga användare")

            for user in receipts_data["users"]:
                user_receipts = [
                    r for r in receipts_data["receipts"] if r.get("user") == user]
                user_total = sum(r.get("belopp", 0) for r in user_receipts)

                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

                with col1:
                    st.write(f"👤 **{user}**")
                with col2:
                    st.write(f"📋 {len(user_receipts)} kvitton")
                with col3:
                    st.write(f"💰 {user_total:,.0f} kr")
                with col4:
                    if st.button("🗑️", key=f"del_user_{user}"):
                        receipts_data["users"].remove(user)
                        save_receipts(receipts_data)
                        st.success("✅ Användare borttagen!")
                        st.rerun()

    with tab3:
        st.subheader("📤 Ladda upp kvitton")

        if not receipts_data["users"]:
            st.warning("⚠️ Lägg till användare först!")
        else:
            # Drag & drop zone
            st.markdown("""
                <div class="upload-zone">
                    <h3>🖼️ Dra och släpp filer här</h3>
                    <p>eller använd formuläret nedan</p>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            with st.form("upload_receipt"):
                col1, col2 = st.columns(2)

                with col1:
                    user = st.selectbox(
                        "👤 Användare", receipts_data["users"], key="upload_user")
                    beskrivning = st.text_input(
                        "📝 Beskrivning *", key="upload_desc")
                    belopp = st.number_input(
                        "💰 Belopp (kr) *", min_value=0.0, step=0.01, key="upload_amount")

                with col2:
                    kategori = st.selectbox(
                        "📁 Kategori", EXPENSE_CATEGORIES, key="upload_cat")
                    datum = st.date_input(
                        "📅 Datum", value=date.today(), key="upload_date")

                # OCR-förslag (simulerat)
                st.info(
                    "💡 Tips: Systemet kan automatiskt läsa belopp från kvittot")

                uploaded_files = st.file_uploader(
                    "📎 Ladda upp kvitto/underlag",
                    type=["pdf", "jpg", "jpeg", "png"],
                    accept_multiple_files=True,
                    key="upload_receipt_files"
                )

                submitted = st.form_submit_button(
                    "📤 Skicka in kvitto", type="primary")

                if submitted and user and beskrivning and belopp > 0:
                    receipt_id = str(uuid.uuid4())

                    # Spara filer
                    file_links = []
                    if uploaded_files:
                        for i, uploaded_file in enumerate(uploaded_files):
                            # Använd unikt ID för varje fil om flera laddas upp för att undvika överskrivning
                            file_id = f"{receipt_id}_{i}" if len(
                                uploaded_files) > 1 else receipt_id
                            file_link = save_receipt_image(
                                uploaded_file, file_id)
                            if file_link:
                                file_links.append(file_link)

                    receipt = {
                        "id": receipt_id,
                        "user": user,
                        "datum": datum.strftime("%Y-%m-%d"),
                        "beskrivning": beskrivning,
                        "belopp": belopp,
                        "kategori": kategori,
                        "status": "inlamnat",
                        "files": file_links,
                        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    receipts_data["receipts"].append(receipt)
                    save_receipts(receipts_data)
                    add_activity(user, "Lade till kvitto",
                                 f"{belopp:,.0f} kr - {beskrivning}")
                    st.success(f"✅ Kvitto inlämnat! (ID: {receipt_id[:8]}...)")
                    st.rerun()

    # TAB 4: GRANSKA (Admin)
    with tab4:
        st.subheader("✅ Granska kvitton")

        # Filtrera kvitton som inte är granskade
        pending_receipts = [r for r in receipts_data["receipts"]
                            if r.get("status") == "inlamnat"]

        if not pending_receipts:
            st.info("🎉 Inga kvitton väntar på granskning!")
        else:
            for receipt in pending_receipts:
                with st.expander(f"{receipt.get('datum')} - {receipt.get('user')} - {receipt.get('belopp'):,.0f} kr"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write(
                            f"**Beskrivning:** {receipt.get('beskrivning')}")
                        st.write(
                            f"**Kategori:** {receipt.get('kategori', 'Okänd')}")
                        if receipt.get("files"):
                            st.write(f"📎 {len(receipt.get('files'))} bilagor")
                            file_list = receipt.get("files")
                            if isinstance(file_list, list):
                                for i, link in enumerate(file_list):
                                    st.markdown(
                                        f"📄 [Öppna bilaga {i+1}]({link})")
                            elif isinstance(file_list, str):
                                st.markdown(f"📄 [Öppna bilaga]({file_list})")

                    with col2:
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ Godkänn", key=f"approve_{receipt['id']}"):
                                receipt["status"] = "godkannt"
                                save_receipts(receipts_data)
                                add_activity(
                                    ADMIN_USERNAME, "Godkände kvitto", f"{receipt.get('user')} - {receipt.get('belopp')} kr")
                                st.success("Godkänt!")
                                st.rerun()
                        with c2:
                            if st.button("❌ Avvisa", key=f"reject_{receipt['id']}"):
                                receipt["status"] = "avvisat"
                                save_receipts(receipts_data)
                                add_activity(
                                    ADMIN_USERNAME, "Avvisade kvitto", f"{receipt.get('user')} - {receipt.get('belopp')} kr")
                                st.warning("Avvisat!")
                                st.rerun()

                    # Retroaktiv uppladdning
                    st.markdown("---")
                    with st.expander("📎 Komplettera med fil"):
                        with st.form(key=f"add_file_form_{receipt['id']}"):
                            st.write(
                                "Ladda upp PDF eller bild för att lägga till i detta kvitto.")
                            new_file = st.file_uploader(
                                "Välj fil", key=f"upload_{receipt['id']}")
                            if st.form_submit_button("💾 Spara bilaga"):
                                if new_file:
                                    try:
                                        # Skapa ett unikt ID för filen
                                        file_suffix = datetime.now().strftime("%H%M%S")
                                        file_link = save_receipt_image(
                                            new_file, f"{receipt['id']}_{file_suffix}")

                                        if file_link:
                                            if "files" not in receipt or not isinstance(receipt["files"], list):
                                                receipt["files"] = []
                                            receipt["files"].append(file_link)
                                            save_receipts(receipts_data)
                                            add_activity(
                                                ADMIN_USERNAME, "Kompletterade kvitto", receipt['id'])
                                            st.success("✅ Fil tillagd!")
                                            st.rerun()
                                    except Exception as e:
                                        st.error(f"Fel vid uppladdning: {e}")
                                else:
                                    st.warning("Ingen fil vald.")

    # TAB 5: MÅNADSRAPPORT
    with tab5:
        st.subheader("📅 Månadsrapport")

        col1, col2 = st.columns(2)
        curr_year = datetime.now().year
        curr_month = datetime.now().month

        with col1:
            sel_year = st.number_input(
                "År", value=curr_year, min_value=2023, max_value=2030, key="rep_y")
        with col2:
            sel_month = st.selectbox("Månad", range(
                1, 13), index=curr_month-1, key="rep_m")

        month_str = f"{sel_year}-{sel_month:02d}"

        # Filtrera kvitton
        month_receipts = [r for r in receipts_data["receipts"]
                          if r.get("datum", "").startswith(month_str) and r.get("status") == "godkannt"]

        if not month_receipts:
            st.info(f"Inga godkända kvitton för {month_str}")
        else:
            # Stats for month
            total_month = sum(r.get("belopp", 0) for r in month_receipts)
            st.metric(f"Total utlägg {month_str}", f"{total_month:,.0f} kr")

            # DataFrame
            df = pd.DataFrame(month_receipts)
            if not df.empty:
                display_df = df[["datum", "user",
                                 "beskrivning", "belopp", "kategori"]].copy()
                st.dataframe(display_df, use_container_width=True)

                # CSV Export
                csv = display_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Ladda ner rapport (CSV)",
                    csv,
                    f"rapport_{month_str}.csv",
                    "text/csv"
                )

            # Detaljerad lista med filer
            st.markdown("---")
            st.markdown("### 📝 Detaljerad lista & Underlag")

            for receipt in month_receipts:
                with st.expander(f"{receipt.get('datum')} - {receipt.get('beskrivning')} ({receipt.get('belopp'):,.0f} kr)"):
                    cols = st.columns([2, 1])
                    with cols[0]:
                        st.write(f"**Användare:** {receipt.get('user')}")
                        st.write(f"**Kategori:** {receipt.get('kategori')}")
                        st.write(f"**ID:** `{receipt.get('id')}`")

                    with cols[1]:
                        if receipt.get("files"):
                            file_list = receipt.get("files")
                            if isinstance(file_list, list):
                                for i, link in enumerate(file_list):
                                    st.markdown(
                                        f"📄 [Öppna bilaga {i+1}]({link})")
                            elif isinstance(file_list, str):
                                st.markdown(f"📄 [Öppna bilaga]({file_list})")
                        else:
                            st.caption("Inga bilagor")

                    # Admin-funktion för att lägga till bilaga i efterhand (Månadsrapport)
                    with st.expander("📎 Lägg till fil (Admin)", expanded=False):
                        if not auth.has_permission("access_settings"):
                            st.error(
                                "Endast admin kan ändra godkända kvitton.")
                        else:
                            with st.form(key=f"retro_add_file_{receipt['id']}"):
                                st.write(
                                    "Ladda upp fil för att komplettera detta godkända kvitto.")
                                retro_file = st.file_uploader(
                                    "Välj fil", key=f"retro_up_{receipt['id']}")
                                if st.form_submit_button("💾 Spara ny bilaga"):
                                    if retro_file:
                                        try:
                                            file_suffix = datetime.now().strftime("%H%M%S")
                                            file_link = save_receipt_image(
                                                retro_file, f"{receipt['id']}_{file_suffix}")

                                            if file_link:
                                                if "files" not in receipt or not isinstance(receipt["files"], list):
                                                    receipt["files"] = []
                                                receipt["files"].append(
                                                    file_link)
                                                save_receipts(receipts_data)
                                                add_activity(
                                                    ADMIN_USERNAME, "Kompletterade godkänt kvitto", receipt['id'])
                                                st.success("✅ Fil tillagd!")
                                                st.rerun()
                                        except Exception as e:
                                            st.error(f"Fel: {e}")
                                    else:
                                        st.warning("Ingen fil vald.")

    # TAB 6: STATISTIK
    with tab6:
        st.subheader("📈 Statistik & Analys")

        approved_receipts = [
            r for r in receipts_data["receipts"] if r.get("status") == "godkannt"]

        if not approved_receipts:
            st.info("Ingen data att analysera än.")
        else:
            df_stats = pd.DataFrame(approved_receipts)

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### Per Kategori")
                if not df_stats.empty:
                    cat_fig = px.pie(
                        df_stats, values='belopp', names='kategori', title='Kostnader per kategori')
                    st.plotly_chart(cat_fig, use_container_width=True)

            with col2:
                st.markdown("#### Per Användare")
                if not df_stats.empty:
                    user_fig = px.bar(df_stats, x='user', y='belopp',
                                      color='kategori', title='Kostnader per användare')
                    st.plotly_chart(user_fig, use_container_width=True)

            st.markdown("#### Tidsutveckling")
            try:
                df_stats["datum"] = pd.to_datetime(df_stats["datum"])
                df_stats = df_stats.sort_values("datum")
                line_fig = px.line(df_stats, x="datum", y="belopp",
                                   color="kategori", title="Utlägg över tid")
                st.plotly_chart(line_fig, use_container_width=True)
            except Exception as e:
                st.warning(f"Kunde inte skapa tidslinje: {e}")

# --- KALENDER ---
elif main_menu == "📅 Kalender":
    st.title("📅 Kalender")

    # Kalender-logik
    if "selected_day" not in st.session_state:
        st.session_state.selected_day = None

    # Hämta händelser
    calendar_data = load_calendar()
    events = calendar_data.get("events", [])

    # Konvertera till datum-objekt för enklare hantering
    events_by_date = {}
    for event in events:
        d = event.get("datum")  # Använd 'datum' som i foretags_ekonomi.py
        if d:
            if d not in events_by_date:
                events_by_date[d] = []
            events_by_date[d].append(event)

    # Månadsväljare
    col1, col2 = st.columns([1, 3])
    with col1:
        # Enkel månadsväljare
        current_date = datetime.now()
        year = st.number_input("År", min_value=2020,
                               max_value=2030, value=current_date.year)

        swedish_months = ["", "Januari", "Februari", "Mars", "April", "Maj", "Juni",
                          "Juli", "Augusti", "September", "Oktober", "November", "December"]

        month = st.selectbox("Månad", range(
            1, 13), index=current_date.month - 1, format_func=lambda x: swedish_months[x])

    # Filter events for the current month
    month_prefix = f"{year}-{month:02d}"
    month_events = [e for e in events if e.get(
        "datum", "").startswith(month_prefix)]

    # Kalender-grid
    cal = cal_module.Calendar(firstweekday=0)  # Måndag som första dag
    month_days = cal.monthdayscalendar(year, month)

    # Callback för att välja dag
    def select_day(day_str):
        st.session_state.selected_day = day_str

    # Veckodagar header
    cols = st.columns(7)
    weekdays = ["Mån", "Tis", "Ons", "Tor", "Fre", "Lör", "Sön"]
    for i, day in enumerate(weekdays):
        cols[i].markdown(f"**{day}**", unsafe_allow_html=True)

    # Kalender-loop
    for week in month_days:
        cols = st.columns(7)
        for i, day in enumerate(week):
            with cols[i]:
                if day == 0:
                    st.write("")
                    continue

                day_str = f"{year}-{month:02d}-{day:02d}"
                is_today = (day_str == datetime.now().strftime("%Y-%m-%d"))
                day_events = events_by_date.get(day_str, [])

                # Determine classes
                day_classes = "cal-day"
                if is_today:
                    day_classes += " today"
                if 'selected_day' in st.session_state and st.session_state.selected_day == day_str:
                    day_classes += " selected"

                # Generate event HTML
                events_html = ""
                if day_events:
                    for event in day_events[:3]:
                        e_type = event.get("type", "Övrigt")
                        pill_class = {
                            "Deadline": "pill-deadline",
                            "Möte": "pill-mote",
                            "Påminnelse": "pill-paminnelse"
                        }.get(e_type, "pill-ovrigt")

                        title = event.get("title", "")[
                            :15].replace('"', '&quot;')
                        events_html += f'<div class="cal-event-pill {pill_class}" title="{title}">{title}</div>'

                    if len(day_events) > 3:
                        events_html += f'<div class="cal-more-events">+{len(day_events)-3} till</div>'

                # Hämta nuvarande token för att behålla inloggning
                # current_token = st.query_params.get("token")
                # token_param = f"&token={current_token}" if current_token else ""

                # Render card with link (no indentation to avoid markdown code block issues)
                # Vi använder en knapp istället för en länk för att undvika omladdning av sidan som rensar state

                # Container för dagen för att få lite styling
                with st.container(border=True):
                    # Datumet som knapp
                    st.button(f"{day}", key=f"cal_day_{day_str}", help=f"Visa händelser för {day_str}",
                              use_container_width=True, on_click=select_day, args=(day_str,))

                    # Visa händelser under knappen
                    if day_events:
                        st.markdown(events_html, unsafe_allow_html=True)

                # Gammal kod (HTML-länk) som orsakade problem med state
                # st.markdown(f"""
                # <a href="?selected_day={day_str}{token_param}" target="_self" style="text-decoration: none; color: inherit; display: block;">
                # <div class="{day_classes}">
                # <div class="cal-day-header">
                # <span class="cal-day-num">{day}</span>
                # </div>
                # <div style="flex-grow: 1;">
                # {events_html}
                # </div>
                # </div>
                # </a>
                # """, unsafe_allow_html=True)

    # Visa vald dag (om klickad)
    if 'selected_day' in st.session_state and st.session_state.selected_day:
        selected_day = st.session_state.selected_day
        selected_events = events_by_date.get(selected_day, [])

        st.markdown("---")
        st.markdown(f"### 📅 Händelser {selected_day}")

        if selected_events:
            for event in selected_events:
                type_emoji = {
                    "Deadline": "🔴",
                    "Möte": "👥",
                    "Påminnelse": "📌",
                    "Övrigt": "📋"
                }.get(event.get("type", "Övrigt"), "📋")

                with st.expander(f"{type_emoji} {event.get('title', 'Ingen titel')}"):
                    st.write(
                        f"**🏢 Verksamhet:** {event.get('business', 'Alla')}")
                    st.write(
                        f"**🕐 Tid:** {event.get('time', 'Ingen tid angiven')}")
                    if event.get("beskrivning"):
                        st.write(
                            f"**📝 Beskrivning:** {event.get('beskrivning')}")

                    if st.button("🗑️ Ta bort", key=f"del_{event.get('id')}"):
                        calendar_data["events"] = [
                            e for e in calendar_data["events"] if e.get("id") != event.get("id")]
                        save_calendar(calendar_data)
                        add_activity(
                            ADMIN_USERNAME, f"Raderade händelse: {event.get('title')}", selected_day)
                        st.success("✅ Händelse raderad!")
                        st.rerun()
        else:
            st.info("Inga händelser denna dag")

        # Lägg till ny händelse
        st.markdown("---")
        with st.form(f"add_event_{selected_day}"):
            st.markdown("### ➕ Lägg till händelse")

            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("📌 Titel *")
                event_type = st.selectbox(
                    "🏷️ Typ", ["Deadline", "Möte", "Påminnelse", "Övrigt"])
            with col2:
                business = st.selectbox("🏢 Verksamhet", ["Alla"] + BUSINESSES)
                event_time = st.time_input("🕐 Tid (valfritt)", value=None)

            beskrivning = st.text_area("📝 Beskrivning (valfritt)")

            col_submit, col_close = st.columns(2)
            with col_submit:
                submitted = st.form_submit_button(
                    "💾 Spara", type="primary", use_container_width=True)
            with col_close:
                close = st.form_submit_button(
                    "❌ Stäng", use_container_width=True)

            if submitted and title:
                event = {
                    "id": f"evt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "title": title,
                    "datum": selected_day,
                    "time": event_time.strftime("%H:%M") if event_time else None,
                    "type": event_type,
                    "business": business,
                    "beskrivning": beskrivning,
                    "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                calendar_data["events"].append(event)
                save_calendar(calendar_data)
                add_activity(
                    ADMIN_USERNAME, f"Lade till händelse: {title}", f"{event_type} - {selected_day}")
                st.success("✅ Händelse sparad!")
                if "selected_day" in st.query_params:
                    del st.query_params["selected_day"]
                st.session_state.selected_day = None
                st.rerun()

            if close:
                if "selected_day" in st.query_params:
                    del st.query_params["selected_day"]
                st.session_state.selected_day = None
                st.rerun()

    # Tabs för hantering
    st.markdown("---")
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📋 Alla händelser", "➕ Snabblägg till", "✅ To-Do", "📊 Statistik"])

    with tab1:
        st.subheader("📋 Alla händelser denna månad")

        if not month_events:
            st.info("Inga händelser denna månad")
        else:
            sorted_events = sorted(
                month_events, key=lambda x: x.get("date", ""))

            for event in sorted_events:
                type_emoji = {
                    "Deadline": "🔴",
                    "Möte": "👥",
                    "Påminnelse": "📌",
                    "Övrigt": "📋"
                }.get(event.get("type", "Övrigt"), "📋")

                st.markdown(f"""
<div style="background: white; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #667eea;">
    <strong>{type_emoji} {event.get('title', '')}</strong><br>
    <span style="color: #64748b; font-size: 0.9rem;">
        📅 {event.get('datum', '')} {f"• 🕐 {event.get('time')}" if event.get('time') else ""} • 🏢 {event.get('business', 'Alla')}
    </span>
</div>
""", unsafe_allow_html=True)

    with tab2:
        st.subheader("➕ Snabblägg till händelse")

        with st.form("quick_add"):
            col1, col2, col3 = st.columns(3)
            with col1:
                quick_date = st.date_input("📅 Datum", value=date.today())
            with col2:
                quick_title = st.text_input("📌 Titel *")
                quick_type = st.selectbox(
                    "🏷️ Typ", ["Deadline", "Möte", "Påminnelse", "Övrigt"])

            if st.form_submit_button("💾 Lägg till", type="primary"):
                if quick_title:
                    event = {
                        "id": f"evt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        "title": quick_title,
                        "date": quick_date.strftime("%Y-%m-%d"),
                        "time": None,
                        "type": quick_type,
                        "business": "Alla",
                        "beskrivning": "",
                        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    calendar_data["events"].append(event)
                    save_calendar(calendar_data)
                    add_activity(
                        ADMIN_USERNAME, f"Snabblade till händelse: {quick_title}", quick_date.strftime("%Y-%m-%d"))
                    st.success("✅ Händelse tillagd!")
                    st.rerun()

    with tab3:
        st.subheader("✅ Att-göra-lista")

        # Initiera todos om det inte finns
        if "todos" not in calendar_data:
            calendar_data["todos"] = []

        # Statistik / Progress
        total_todos = len(calendar_data["todos"])
        if total_todos > 0:
            done_todos = len(
                [t for t in calendar_data["todos"] if t.get("done", False)])
            progress = done_todos / total_todos
            st.progress(
                progress, text=f"{done_todos} av {total_todos} klara ({int(progress*100)}%)")

        # Lägg till ny uppgift
        with st.expander("➕ Lägg till ny uppgift", expanded=False):
            with st.form("add_todo"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    todo_task = st.text_input(
                        "Uppgift", placeholder="Vad behöver göras?")
                with col2:
                    todo_prio = st.selectbox(
                        "Prioritet", ["Hög", "Medel", "Låg"], index=1)

                todo_deadline = st.date_input(
                    "Deadline (valfritt)", value=None)

                if st.form_submit_button("Lägg till", type="primary"):
                    if todo_task:
                        new_todo = {
                            "id": f"todo_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                            "task": todo_task,
                            "priority": todo_prio,
                            "deadline": todo_deadline.strftime("%Y-%m-%d") if todo_deadline else None,
                            "done": False,
                            "created": datetime.now().strftime("%Y-%m-%d")
                        }
                        calendar_data["todos"].append(new_todo)
                        save_calendar(calendar_data)
                        st.success("✅ Uppgift tillagd!")
                        st.rerun()

        # Visa uppgifter
        if not calendar_data["todos"]:
            st.info("Inga uppgifter i listan. Skönt! 🎉")
        else:
            # Sortera: Ej klara först, sedan prioritet (Hög > Medel > Låg)
            prio_map = {"Hög": 0, "Medel": 1, "Låg": 2}
            sorted_todos = sorted(calendar_data["todos"], key=lambda x: (
                x.get("done", False), prio_map.get(x.get("priority", "Medel"), 1)))

            st.markdown("---")
            for todo in sorted_todos:
                col_check, col_text, col_meta, col_actions = st.columns(
                    [0.5, 3, 1.5, 1])

                with col_check:
                    is_done = st.checkbox(
                        " ", value=todo.get("done", False), key=f"check_{todo['id']}")
                    if is_done != todo.get("done", False):
                        todo["done"] = is_done
                        save_calendar(calendar_data)
                        st.rerun()

                with col_text:
                    task_style = "text-decoration: line-through; color: #9ca3af;" if todo.get(
                        "done", False) else ""
                    st.markdown(
                        f"<span style='{task_style}'>{todo['task']}</span>", unsafe_allow_html=True)

                with col_meta:
                    prio_colors = {"Hög": "🔴", "Medel": "🟡", "Låg": "🟢"}
                    meta_text = f"{prio_colors.get(todo.get('priority'), '⚪')} {todo.get('priority')}"

                    if todo.get("deadline"):
                        try:
                            deadline_date = datetime.strptime(
                                todo["deadline"], "%Y-%m-%d").date()
                            days_left = (deadline_date - date.today()).days

                            if todo.get("done", False):
                                pass
                            elif days_left < 0:
                                meta_text += f" | ⚠️ {todo['deadline']}"
                            elif days_left == 0:
                                meta_text += f" | 📅 Idag"
                            else:
                                meta_text += f" | 📅 {todo['deadline']}"
                        except ValueError:
                            pass

                    st.caption(meta_text)

                with col_actions:
                    # Knapp för att konvertera till kalenderhändelse (om ej klar och har deadline)
                    if not todo.get("done", False) and todo.get("deadline"):
                        if st.button("📅", key=f"cal_{todo['id']}", help="Lägg till i kalender"):
                            new_event = {
                                "id": f"evt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                                "title": todo['task'],
                                "date": todo['deadline'],
                                "time": None,
                                "type": "Deadline" if todo['priority'] == "Hög" else "Övrigt",
                                "business": "Alla",
                                "beskrivning": f"Från To-Do listan. Prioritet: {todo['priority']}",
                                "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            calendar_data["events"].append(new_event)
                            save_calendar(calendar_data)
                            st.toast("✅ Tillagd i kalendern!")

                    if st.button("🗑️", key=f"del_todo_{todo['id']}"):
                        calendar_data["todos"] = [
                            t for t in calendar_data["todos"] if t["id"] != todo["id"]]
                        save_calendar(calendar_data)
                        st.rerun()

    with tab4:
        st.subheader("📊 Statistik denna månad")

        if month_events:
            type_counts = {}
            for e in month_events:
                t = e.get("type", "Övrigt")
                type_counts[t] = type_counts.get(t, 0) + 1

            fig = px.pie(
                names=list(type_counts.keys()),
                values=list(type_counts.values()),
                title="Händelser per typ",
                color_discrete_sequence=["#ef4444",
                                         "#3b82f6", "#f59e0b", "#8b5cf6"]
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Ingen statistik tillgänglig")

# --- RAPPORTER (NY SEKTION) ---
elif main_menu == "📋 Rapporter":
    if not auth.has_permission("access_reports"):
        st.error("⛔ Du saknar behörighet för denna sida.")
        st.stop()

    st.title("📋 Rapporter & Analys")

    # Ta bort gammal admin-check om den inte behövs längre, eller behåll om du vill ha dubbel säkerhet
    # Men nu styrs det av permissions.

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 Resultatrapport", "💰 Kassaflöde", "📈 Trendanalys", "🏢 Per verksamhet"])

    with tab1:
        st.subheader("📊 Resultatrapport")

        col1, col2 = st.columns(2)
        with col1:
            report_year = st.number_input(
                "År", min_value=2020, max_value=2035, value=date.today().year)
        with col2:
            report_period = st.selectbox("Period", ["Helår", "Q1", "Q2", "Q3", "Q4", "Januari", "Februari",
                                                    "Mars", "April", "Maj", "Juni", "Juli", "Augusti", "September", "Oktober", "November", "December"])

        if report_period == "Helår":
            period_filter = f"{report_year}"
        elif report_period.startswith("Q"):
            period_filter = f"{report_year}"
        else:
            month_num = ["Januari", "Februari", "Mars", "April", "Maj", "Juni", "Juli",
                         "Augusti", "September", "Oktober", "November", "December"].index(report_period) + 1
            period_filter = f"{report_year}-{month_num:02d}"

        if st.button("📊 Generera rapport", type="primary"):
            period_revenue = [r for r in revenue["intakter"]
                              if r.get("datum", "").startswith(period_filter)]
            total_revenue = sum(r.get("belopp", 0) for r in period_revenue)

            period_expenses = {}
            total_expenses = 0
            for business in BUSINESSES:
                business_expenses = [e for e in expenses[business]["utgifter"] if e.get(
                    "datum", "").startswith(period_filter)]
                period_expenses[business] = sum(
                    e.get("belopp", 0) for e in business_expenses)
                total_expenses += period_expenses[business]

            net_profit = total_revenue - total_expenses
            profit_margin = (net_profit / total_revenue *
                             100) if total_revenue > 0 else 0

            st.markdown("---")
            st.markdown(
                f"### 📋 Resultatrapport - {report_period} {report_year}")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💰 Intäkter", f"{total_revenue:,.0f} kr")
            col2.metric("💸 Utgifter", f"{total_expenses:,.0f} kr")
            col3.metric("📈 Nettovinst",
                        f"{net_profit:,.0f} kr", delta=f"{profit_margin:.1f}%")
            col4.metric("📊 Rörelsemarginal", f"{profit_margin:.1f}%")

            st.markdown("---")
            st.markdown("### 🏢 Per verksamhet")
            for business in BUSINESSES:
                business_revenue = sum(
                    r.get("belopp", 0) for r in period_revenue if r.get("verksamhet") == business)
                business_expenses_val = period_expenses[business]
                business_profit = business_revenue - business_expenses_val

                with st.expander(f"🏢 {business}", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Intäkter", f"{business_revenue:,.0f} kr")
                    col2.metric("Utgifter", f"{business_expenses_val:,.0f} kr")
                    col3.metric("Vinst", f"{business_profit:,.0f} kr")

            st.markdown("---")
            if st.button("📥 Exportera till PDF", type="secondary"):
                st.info("PDF-export kommer snart")

    with tab2:
        st.subheader("💰 Kassaflödesanalys")

        months_back = st.slider("Antal månader tillbaka", 3, 12, 6)

        if st.button("📊 Generera kassaflöde", type="primary"):
            cashflow_data = []

            for i in range(months_back - 1, -1, -1):
                month_date = date.today() - timedelta(days=i*30)
                month = month_date.strftime("%Y-%m")
                month_name = month_date.strftime("%b %Y")

                month_revenue = sum(r.get("belopp", 0) for r in revenue["intakter"] if r.get(
                    "datum", "").startswith(month))
                month_expenses = sum(sum(e.get("belopp", 0) for e in expenses[b]["utgifter"] if e.get(
                    "datum", "").startswith(month)) for b in BUSINESSES)
                month_net = month_revenue - month_expenses

                cashflow_data.append({
                    "Månad": month_name,
                    "Intäkter": month_revenue,
                    "Utgifter": month_expenses,
                    "Netto": month_net
                })

            df_cashflow = pd.DataFrame(cashflow_data)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='Intäkter', x=df_cashflow['Månad'], y=df_cashflow['Intäkter'], marker_color='#10b981'))
            fig.add_trace(go.Bar(
                name='Utgifter', x=df_cashflow['Månad'], y=df_cashflow['Utgifter'], marker_color='#ef4444'))
            fig.add_trace(go.Scatter(name='Netto', x=df_cashflow['Månad'], y=df_cashflow['Netto'],
                                     mode='lines+markers', line=dict(color='#667eea', width=4), marker=dict(size=10)))

            fig.update_layout(barmode='group', height=500,
                              template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(df_cashflow, use_container_width=True,
                         hide_index=True)

    with tab3:
        st.subheader("📈 Trendanalys")

        trend_category = st.selectbox(
            "Välj kategori", ["Alla"] + EXPENSE_CATEGORIES)
        trend_months = st.slider("Antal månader", 3, 12, 6, key="trend_months")

        if st.button("📊 Generera trend", type="primary"):
            trend_data = []

            for i in range(trend_months - 1, -1, -1):
                month_date = date.today() - timedelta(days=i*30)
                month = month_date.strftime("%Y-%m")
                month_name = month_date.strftime("%b %Y")

                if trend_category == "Alla":
                    month_total = sum(sum(e.get("belopp", 0) for e in expenses[b]["utgifter"] if e.get(
                        "datum", "").startswith(month)) for b in BUSINESSES)
                else:
                    month_total = sum(sum(e.get("belopp", 0) for e in expenses[b]["utgifter"] if e.get(
                        "datum", "").startswith(month) and e.get("kategori") == trend_category) for b in BUSINESSES)

                trend_data.append({"Månad": month_name, "Belopp": month_total})

            df_trend = pd.DataFrame(trend_data)

            fig = px.line(df_trend, x="Månad", y="Belopp",
                          markers=True, title=f"Trend: {trend_category}")
            fig.update_traces(line_color='#667eea',
                              line_width=4, marker=dict(size=12))
            st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.subheader("🏢 Jämförelse per verksamhet")

        compare_year = st.number_input(
            "År", min_value=2020, max_value=2035, value=date.today().year, key="compare_year")

        if st.button("📊 Generera jämförelse", type="primary"):
            comparison = []

            for business in BUSINESSES:
                year_revenue = sum(r.get("belopp", 0) for r in revenue["intakter"] if r.get(
                    "datum", "").startswith(str(compare_year)) and r.get("verksamhet") == business)
                year_expenses = sum(e.get("belopp", 0) for e in expenses[business]["utgifter"] if e.get(
                    "datum", "").startswith(str(compare_year)))
                year_profit = year_revenue - year_expenses

                comparison.append({
                    "Verksamhet": business,
                    "Intäkter": year_revenue,
                    "Utgifter": year_expenses,
                    "Vinst": year_profit,
                    "Marginal": f"{(year_profit/year_revenue*100 if year_revenue > 0 else 0):.1f}%"
                })

            df_comparison = pd.DataFrame(comparison)

            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(df_comparison, x="Verksamhet", y="Intäkter",
                             title="Intäkter per verksamhet", color="Verksamhet")
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = px.bar(df_comparison, x="Verksamhet", y="Vinst",
                             title="Vinst per verksamhet", color="Verksamhet")
                st.plotly_chart(fig, use_container_width=True)

            st.dataframe(df_comparison, use_container_width=True,
                         hide_index=True)

# --- DUBBLETTHANTERING ---
elif main_menu == "🔍 Dubbletthantering":
    st.title("🔍 Dubbletthantering")
    tab1, tab2 = st.tabs(["💰 Utgiftsdubbletter", "💵 Intäktsdubbletter"])

    with tab1:
        st.subheader("💰 Hitta dubbletter i utgifter")
        if st.button("🔍 Sök dubbletter", type="primary"):
            duplicates = find_duplicate_expenses(expenses)
            if duplicates:
                st.warning(
                    f"⚠️ Hittade {len(duplicates)} potentiella dubbletter!")
                for dup in duplicates:
                    with st.expander(f"🔴 {dup['original']['beskrivning']} - {dup['original']['belopp']:,.2f} kr"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Original:**")
                            st.write(f"Datum: {dup['original']['datum']}")
                            st.write(
                                f"Belopp: {dup['original']['belopp']:,.2f} kr")
                            st.write(
                                f"Leverantör: {dup['original']['leverantor']}")
                        with col2:
                            st.markdown("**Dublett:**")
                            st.write(f"Datum: {dup['duplicate']['datum']}")
                            st.write(
                                f"Belopp: {dup['duplicate']['belopp']:,.2f} kr")
                            st.write(
                                f"Leverantör: {dup['duplicate']['leverantor']}")
                        if st.button("🗑️ Ta bort dublett", key=f"del_exp_{dup['duplicate_index']}"):
                            remove_expense_by_index(
                                expenses, dup['business'], dup['duplicate_index'])
                            save_expenses(expenses)
                            st.success("✅ Dublett borttagen!")
                            st.rerun()
            else:
                st.success("✅ Inga dubbletter hittade!")

    with tab2:
        st.subheader("💵 Hitta dubbletter i intäkter")
        if st.button("🔍 Sök dubbletter", type="primary", key="search_rev_dup"):
            duplicates = find_duplicate_revenue(revenue)
            if duplicates:
                st.warning(
                    f"⚠️ Hittade {len(duplicates)} potentiella dubbletter!")
                for dup in duplicates:
                    with st.expander(f"🔴 {dup['original']['beskrivning']} - {dup['original']['belopp']:,.2f} kr"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Original:**")
                            st.write(f"Datum: {dup['original']['datum']}")
                            st.write(
                                f"Belopp: {dup['original']['belopp']:,.2f} kr")
                            st.write(f"Kund: {dup['original']['kund']}")
                        with col2:
                            st.markdown("**Dublett:**")
                            st.write(f"Datum: {dup['duplicate']['datum']}")
                            st.write(
                                f"Belopp: {dup['duplicate']['belopp']:,.2f} kr")
                            st.write(f"Kund: {dup['duplicate']['kund']}")
                        if st.button("🗑️ Ta bort dublett", key=f"del_rev_{dup['duplicate_index']}"):
                            remove_revenue_by_index(
                                revenue, dup['duplicate_index'])
                            save_revenue(revenue)
                            st.success("✅ Dublett borttagen!")
                            st.rerun()
            else:
                st.success("✅ Inga dubbletter hittade!")

# --- INSTÄLLNINGAR ---
elif main_menu == "⚙️ Inställningar":
    if not auth.has_permission("access_settings"):
        st.error("⛔ Du saknar behörighet för denna sida.")
        st.stop()

    st.title("⚙️ Inställningar")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📤 Export", "🎯 Årsmål", "👥 Användarhantering", "📝 Hantera transaktioner", "📋 Aktivitetslogg"])

    with tab1:
        st.subheader("📤 Exportera data")
        if st.button("📥 Exportera till Excel", type="primary"):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for business in BUSINESSES:
                    df = pd.DataFrame(expenses[business]["utgifter"])
                    if not df.empty:
                        df.to_excel(writer, sheet_name=business, index=False)
            output.seek(0)
            st.download_button("📥 Ladda ner Excel", data=output, file_name=f"utgifter_{datetime.now().strftime('%Y%m%d')}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with tab2:
        st.subheader("🎯 Årsmål")
        for business in BUSINESSES:
            with st.expander(f"🏢 {business}", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    annual_revenue_goal = st.number_input(f"Intäktsmål {business} (kr)", min_value=0.0,
                                                          value=float(goals[business].get("annual_revenue", 0)), step=10000.0, key=f"goal_rev_{business}")
                with col2:
                    annual_profit_goal = st.number_input(f"Vinstmål {business} (kr)", min_value=0.0,
                                                         value=float(goals[business].get("annual_profit", 0)), step=5000.0, key=f"goal_profit_{business}")
                goals[business]["annual_revenue"] = annual_revenue_goal
                goals[business]["annual_profit"] = annual_profit_goal

        if st.button("💾 Spara mål", type="primary"):
            save_goals(goals)
            add_activity(ADMIN_USERNAME, "Uppdaterade årsmål",
                         "För båda verksamheter")
            st.success("✅ Mål sparade!")
            st.rerun()

    with tab3:
        st.subheader("👥 Användarhantering")
        tab_add, tab_list = st.tabs(["➕ Lägg till", "📋 Lista"])
        with tab_add:
            with st.form("add_user"):
                new_username = st.text_input("Användarnamn")
                new_role = st.selectbox("Roll", ["admin", "user"])
                if st.form_submit_button("➕ Lägg till", type="primary"):
                    if new_username:
                        result = user_manager.add_user(new_username, new_role)
                        st.success(f"✅ {result}")
                        add_activity(
                            ADMIN_USERNAME, "Lade till användare", f"{new_username} ({new_role})")
                        st.rerun()

        with tab_list:
            if not user_manager.users:
                st.info("Inga användare")
            else:
                for username, user in user_manager.users.items():
                    with st.expander(f"👤 {username} ({user.role})"):
                        # Visa rättigheter
                        st.markdown("#### Rättigheter")

                        current_perms = user.permissions

                        col_p1, col_p2 = st.columns(2)
                        with col_p1:
                            perm_settings = st.checkbox(
                                "⚙️ Inställningar", value="access_settings" in current_perms, key=f"perm_set_{username}")
                            perm_reports = st.checkbox(
                                "📋 Rapporter", value="access_reports" in current_perms, key=f"perm_rep_{username}")
                        with col_p2:
                            perm_chat = st.checkbox(
                                "💬 Skapa chatt", value="create_chat" in current_perms, key=f"perm_chat_{username}")
                            perm_archive = st.checkbox(
                                "📦 Arkivera chatt", value="archive_chat" in current_perms, key=f"perm_arch_{username}")

                        if st.button("💾 Spara rättigheter", key=f"save_perm_{username}"):
                            new_perms = []
                            if perm_settings:
                                new_perms.append("access_settings")
                            if perm_reports:
                                new_perms.append("access_reports")
                            if perm_chat:
                                new_perms.append("create_chat")
                            if perm_archive:
                                new_perms.append("archive_chat")

                            # Behåll andra permissions
                            for p in current_perms:
                                if p not in ["access_settings", "access_reports", "create_chat", "archive_chat"]:
                                    new_perms.append(p)

                            user_manager.update_permissions(
                                username, new_perms)
                            st.success("✅ Rättigheter sparade!")
                            st.rerun()

                        if username != ADMIN_USERNAME:
                            if st.button("🗑️ Ta bort användare", key=f"del_user_{username}"):
                                user_manager.remove_user(username)
                                st.success("✅ Användare borttagen!")
                                st.rerun()

    with tab4:
        st.subheader("📝 Hantera transaktioner")
        subtab1, subtab2 = st.tabs(["💰 Utgifter", "💵 Intäkter"])

        # --- UTGIFTER ---
        with subtab1:
            st.markdown("### 💰 Hantera utgifter")

            col1, col2, col3 = st.columns(3)
            with col1:
                filter_business = st.selectbox(
                    "🏢 Verksamhet", ["Alla"] + BUSINESSES, key="edit_exp_business")
            with col2:
                filter_category = st.selectbox(
                    "📁 Kategori", ["Alla"] + EXPENSE_CATEGORIES, key="edit_exp_cat")
            with col3:
                use_month_filter = st.checkbox(
                    "Filtrera på månad", value=True, key="use_month_filter_exp")
                if use_month_filter:
                    filter_month_date = st.date_input(
                        "📅 Månad", value=date.today(), key="edit_exp_month")
                    filter_month = filter_month_date.strftime("%Y-%m")
                else:
                    filter_month = None

            # Samla alla utgifter med referens till ursprung
            all_expenses_list = []
            for business, data in expenses.items():
                for idx, exp in enumerate(data["utgifter"]):
                    exp_item = exp.copy()
                    exp_item["_business"] = business
                    exp_item["_index"] = idx
                    all_expenses_list.append(exp_item)

            # Filtrera
            filtered_expenses = all_expenses_list
            if filter_business != "Alla":
                filtered_expenses = [
                    e for e in filtered_expenses if e["_business"] == filter_business]
            if filter_category != "Alla":
                filtered_expenses = [
                    e for e in filtered_expenses if e["kategori"] == filter_category]
            if filter_month:
                filtered_expenses = [
                    e for e in filtered_expenses if e["datum"].startswith(filter_month)]

            # Sortera på datum (nyast först)
            filtered_expenses.sort(key=lambda x: x["datum"], reverse=True)

            st.write(f"Hittade {len(filtered_expenses)} transaktioner.")

            for i, exp in enumerate(filtered_expenses):
                unique_key = f"exp_{exp['_business']}_{exp['_index']}"
                label = f"{exp['datum']} | {exp['_business']} | {exp['beskrivning']} | {exp['belopp']} kr"

                with st.expander(label):
                    with st.form(key=f"form_{unique_key}"):
                        col_a, col_b = st.columns(2)
                        with col_a:
                            try:
                                exp_date = datetime.strptime(
                                    exp["datum"], "%Y-%m-%d").date()
                            except ValueError:
                                exp_date = date.today()

                            new_date = st.date_input(
                                "Datum", value=exp_date, key=f"date_{unique_key}")
                            new_business = st.selectbox("Verksamhet", BUSINESSES, index=BUSINESSES.index(
                                exp["_business"]) if exp["_business"] in BUSINESSES else 0, key=f"bus_{unique_key}")
                            new_category = st.selectbox("Kategori", EXPENSE_CATEGORIES, index=EXPENSE_CATEGORIES.index(
                                exp["kategori"]) if exp["kategori"] in EXPENSE_CATEGORIES else 0, key=f"cat_{unique_key}")
                        with col_b:
                            new_desc = st.text_input(
                                "Beskrivning", value=exp["beskrivning"], key=f"desc_{unique_key}")
                            new_supplier = st.text_input("Leverantör", value=exp.get(
                                "leverantor", ""), key=f"supp_{unique_key}")
                            new_amount = st.number_input("Belopp", value=float(
                                exp["belopp"]), step=1.0, key=f"amt_{unique_key}")

                        col_c, col_d = st.columns([1, 1])
                        with col_c:
                            update_submitted = st.form_submit_button(
                                "💾 Spara ändringar", type="primary")
                        with col_d:
                            delete_submitted = st.form_submit_button(
                                "🗑️ Ta bort transaktion", type="secondary")

                    if update_submitted:
                        old_business = exp["_business"]
                        old_index = exp["_index"]

                        updated_exp = {
                            "datum": new_date.strftime("%Y-%m-%d"),
                            "kategori": new_category,
                            "beskrivning": new_desc,
                            "leverantor": new_supplier,
                            "belopp": new_amount
                        }

                        if new_business == old_business:
                            expenses[old_business]["utgifter"][old_index] = updated_exp
                        else:
                            expenses[old_business]["utgifter"].pop(old_index)
                            expenses[new_business]["utgifter"].append(
                                updated_exp)

                        for b in expenses:
                            expenses[b]["total"] = sum(
                                u["belopp"] for u in expenses[b]["utgifter"])

                        save_expenses(expenses)
                        st.toast("✅ Utgift uppdaterad!")
                        st.rerun()

                    if delete_submitted:
                        remove_expense_by_index(
                            expenses, exp["_business"], exp["_index"])
                        save_expenses(expenses)
                        st.success("✅ Utgift borttagen!")
                        st.rerun()

        # --- INTÄKTER ---
        with subtab2:
            st.markdown("### 💵 Hantera intäkter")
            # (Förenklad version för intäkter - liknande logik kan läggas till här)
            st.info("Funktionalitet för att redigera intäkter kommer snart.")

    with tab5:
        st.subheader("📋 Aktivitetslogg")
        if not activity_log:
            st.info("Ingen aktivitet registrerad än.")
        else:
            for activity in reversed(activity_log):
                st.markdown(f"""
                **{activity['timestamp']}** - {activity['user']}
                * {activity['action']}
                * {activity['details']}
                ---
                """)

# --- FLYTANDE CHATT (EGEN IMPLEMENTATION) ---
# Initiera session state
if "chat_open" not in st.session_state:
    st.session_state.chat_open = False
if "chat_expanded" not in st.session_state:
    st.session_state.chat_expanded = False

# Dynamiska mått
chat_width = "600px" if st.session_state.chat_expanded else "380px"
chat_height = "800px" if st.session_state.chat_expanded else "500px"

# CSS för flytande element
st.markdown(f"""
<style>
    /* Flytande knapp-container - Target HorizontalBlock to avoid Sidebar Root */
    div[data-testid="stHorizontalBlock"]:has(span#chat-btn-marker) {{
        position: fixed;
        bottom: 30px;
        right: 30px;
        width: 60px;
        height: 60px;
        z-index: 10000;
        background: transparent;
        pointer-events: auto;
    }}
    
    /* Styla själva knappen i containern */
    div[data-testid="stHorizontalBlock"]:has(span#chat-btn-marker) button {{
        width: 60px;
        height: 60px;
        border-radius: 30px;
        background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
        color: white;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
        border: none;
        font-size: 24px;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: transform 0.2s;
    }}
    
    div[data-testid="stHorizontalBlock"]:has(span#chat-btn-marker) button:hover {{
        transform: scale(1.1);
        box-shadow: 0 6px 16px rgba(79, 70, 229, 0.4);
    }}

    /* Flytande chatt-fönster - Target HorizontalBlock */
    div[data-testid="stHorizontalBlock"]:has(span#chat-window-marker) {{
        position: fixed;
        bottom: 100px;
        right: 30px;
        width: {chat_width};
        height: {chat_height};
        max-height: 85vh;
        background: white;
        border-radius: 16px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        z-index: 9999;
        padding: 1rem;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        color: black; /* Tvinga svart text */
        pointer-events: auto;
    }}
    
    /* Tvinga svart text på rubriker och paragrafer i chattfönstret */
    div[data-testid="stHorizontalBlock"]:has(span#chat-window-marker) h1,
    div[data-testid="stHorizontalBlock"]:has(span#chat-window-marker) h2,
    div[data-testid="stHorizontalBlock"]:has(span#chat-window-marker) h3,
    div[data-testid="stHorizontalBlock"]:has(span#chat-window-marker) p,
    div[data-testid="stHorizontalBlock"]:has(span#chat-window-marker) span,
    div[data-testid="stHorizontalBlock"]:has(span#chat-window-marker) div {{
        color: #1e293b !important;
    }}
    
    /* Dölj scrollbar i fönstret men behåll funktion */
    div[data-testid="stHorizontalBlock"]:has(span#chat-window-marker)::-webkit-scrollbar {{
        width: 6px;
    }}
    div[data-testid="stHorizontalBlock"]:has(span#chat-window-marker)::-webkit-scrollbar-thumb {{
        background-color: rgba(0,0,0,0.1);
        border-radius: 3px;
    }}
</style>
""", unsafe_allow_html=True)

# Placera chatt-elementen i sidebar men använd columns för att skapa HorizontalBlocks
# Detta gör att vi kan styla dem specifikt utan att påverka hela sidebaren (VerticalBlock)
with st.sidebar:
    # --- CHATT-KNAPP ---
    # Använd en kolumn för att skapa ett HorizontalBlock
    col_btn = st.columns(1)[0]
    with col_btn:
        st.markdown('<span id="chat-btn-marker"></span>',
                    unsafe_allow_html=True)
        # Ikon ändras beroende på om chatten är öppen
        btn_icon = "✖️" if st.session_state.chat_open else "💬"
        if st.button(btn_icon, key="floating_chat_btn"):
            st.session_state.chat_open = not st.session_state.chat_open
            st.rerun()

    # --- CHATT-FÖNSTER ---
    if st.session_state.chat_open:
        # Använd en kolumn för att skapa ett HorizontalBlock
        col_win = st.columns(1)[0]
        with col_win:
            st.markdown('<span id="chat-window-marker"></span>',
                        unsafe_allow_html=True)

            # Initiera session state för chatt-navigering
            if "active_chat_id" not in st.session_state:
                st.session_state.active_chat_id = None

            current_user = st.session_state.current_user
            user_chats = chat_manager.get_user_groups(current_user)

            # --- HEADER MED STORLEKSKNAPP ---
            col_h1, col_h2 = st.columns([5, 1])
            with col_h2:
                # Ikon för expandera/minimera
                icon = "↙️" if st.session_state.chat_expanded else "↗️"
                help_text = "Minimera" if st.session_state.chat_expanded else "Expandera"
                if st.button(icon, key="toggle_chat_size", help=help_text):
                    st.session_state.chat_expanded = not st.session_state.chat_expanded
                    st.rerun()

            # --- VY 1: CHATT-LISTA ---
            if st.session_state.active_chat_id is None:
                with col_h1:
                    st.markdown("### 💬 Dina chattar")

                # Lista befintliga chattar
                if not user_chats:
                    st.info("Du är inte med i några chattar än.")
                else:
                    for group in user_chats:
                        # Visa senaste meddelandet om det finns
                        msgs = chat_manager.get_group_messages(group["id"])
                        last_msg = msgs[-1]["content"][:30] + \
                            "..." if msgs else "Inga meddelanden"

                        # Knapp för varje chatt
                        col_c1, col_c2 = st.columns([3, 1.2])
                        with col_c1:
                            st.markdown(f"**{group['name']}**")
                            st.caption(last_msg)
                        with col_c2:
                            if st.button("Öppna", key=f"open_chat_{group['id']}", use_container_width=True):
                                st.session_state.active_chat_id = group["id"]
                                st.rerun()
                        st.divider()

                # Skapa ny chatt (endast om behörighet finns - här antar vi alla eller admin)
                user_role = user_manager.users[current_user].role if current_user in user_manager.users else "user"
                if user_role == "admin":
                    with st.expander("➕ Skapa ny chatt", expanded=False):
                        with st.form("popup_new_chat"):
                            new_chat_name = st.text_input("Gruppnamn")
                            all_users = list(user_manager.users.keys())
                            if current_user in all_users:
                                all_users.remove(current_user)
                            selected_members = st.multiselect(
                                "Deltagare", all_users)

                            if st.form_submit_button("Skapa"):
                                if new_chat_name and selected_members:
                                    members = [current_user] + selected_members
                                    chat_manager.create_group(
                                        new_chat_name, current_user, members)
                                    st.success("Chatt skapad!")
                                    st.rerun()

            # --- VY 2: AKTIV CHATT ---
            else:
                # Hitta vald grupp
                selected_group = next(
                    (g for g in user_chats if g["id"] == st.session_state.active_chat_id), None)

                if selected_group:
                    # Header med tillbaka-knapp
                    col_back, col_title = st.columns([1, 4])
                    with col_back:
                        if st.button("←", help="Tillbaka till listan"):
                            st.session_state.active_chat_id = None
                            st.rerun()
                    with col_title:
                        st.markdown(f"### {selected_group['name']}")

                    st.divider()

                    # Visa meddelanden
                    messages = chat_manager.get_group_messages(
                        selected_group["id"])

                    # Container för meddelanden (med scroll)
                    # Vi använder en fast höjd minus header/input för att det ska se bra ut
                    msg_height = 600 if st.session_state.chat_expanded else 300
                    chat_container = st.container(height=msg_height)
                    with chat_container:
                        if not messages:
                            st.caption("Inga meddelanden än. Börja skriva!")

                        for msg in messages:
                            is_me = msg["sender"] == current_user
                            with st.chat_message("user" if is_me else "assistant", avatar="👤" if is_me else "👥"):
                                st.write(
                                    f"**{msg['sender']}**: {msg['content']}")
                                st.caption(msg["timestamp"])

                    # Input för nytt meddelande
                    # Använd text_input istället för chat_input för att garantera att den hamnar i containern
                    with st.form(key=f"chat_form_{selected_group['id']}", clear_on_submit=True):
                        col_in1, col_in2 = st.columns([4, 1])
                        with col_in1:
                            prompt = st.text_input(
                                "Meddelande", key=f"chat_input_{selected_group['id']}", label_visibility="collapsed", placeholder="Skriv meddelande...")
                        with col_in2:
                            submit_msg = st.form_submit_button(
                                "Skicka", use_container_width=True)

                        if submit_msg and prompt:
                            chat_manager.add_message(
                                selected_group["id"], current_user, prompt)
                            st.rerun()
                else:
                    st.session_state.active_chat_id = None
                    st.rerun()
