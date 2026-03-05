"""
Unithread App — Flask backend.
REST API for expenses, revenue, receipts, calendar, chat, CRM, quotes, admin.
"""

import os
import io
import json
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask, request, jsonify, session, render_template,
    send_from_directory, redirect, url_for, send_file
)
from werkzeug.utils import secure_filename

from google_sheets import db

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "unithread-secret-key-2026-change-me")
app.config["UPLOAD_FOLDER"] = Path(__file__).parent / "uploads" / "receipts"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

BUSINESSES = ["Unithread", "Merchoteket"]

EXPENSE_CATEGORIES = [
    "Varuinköp", "Marknadsföring", "IT & Programvara", "Lokalhyra",
    "Transport & Logistik", "Design & Produktion", "Juridik & Konsulter",
    "Bank & Avgifter", "Övrigt",
]
REVENUE_CATEGORIES = [
    "Produktförsäljning", "Tjänster", "Konsultarvode", "Övrigt",
]
RECEIPT_CATEGORIES = EXPENSE_CATEGORIES
CALENDAR_TYPES = ["Möte", "Deadline", "Påminnelse", "Betalning", "Övrigt"]
VAT_RATES = [0, 6, 12, 25]

# CRM
CUSTOMER_STAGES = ["Lead", "Kontaktad", "Offert skickad", "Förhandling", "Vunnen", "Förlorad"]
CUSTOMER_SOURCES = ["Hemsida", "Referens", "LinkedIn", "Mässa", "Kall kontakt", "Övrigt"]
QUOTE_STATUSES = ["Utkast", "Skickad", "Accepterad", "Avvisad", "Fakturerad"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return jsonify({"error": "Ej inloggad"}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return jsonify({"error": "Ej inloggad"}), 401
        if session.get("role") != "admin":
            return jsonify({"error": "Behörighet saknas"}), 403
        return f(*args, **kwargs)
    return decorated


def _log_activity(user, action, details=""):
    try:
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": user,
            "action": action,
            "details": details,
        }
        logs = db.load_data("activity_log")
        logs.append(entry)
        if len(logs) > 200:
            logs = logs[-200:]
        db.save_data("activity_log", logs)
    except Exception:
        pass


def _parse_permissions(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith("["):
            try:
                return json.loads(raw)
            except Exception:
                return []
        return [p.strip() for p in raw.split(",") if p.strip()]
    return []


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(Path(__file__).parent / "static", "favicon.ico")


@app.route("/")
def index():
    if "user" not in session:
        return render_template("login.html")
    return render_template("app.html",
                           user=session["user"],
                           role=session.get("role", "user"))


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ---------------------------------------------------------------------------
# Auth API
# ---------------------------------------------------------------------------

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    password = data.get("password", "")

    users = db.load_data("users")
    for u in users:
        if u.get("username") == username:
            if u.get("password_hash") == _hash(password):
                session["user"] = username
                session["role"] = u.get("role", "user")
                session["permissions"] = _parse_permissions(u.get("permissions"))
                _log_activity(username, "Loggade in")
                return jsonify({"ok": True, "user": username, "role": session["role"]})
            return jsonify({"ok": False, "error": "Fel lösenord"}), 401
    return jsonify({"ok": False, "error": "Användaren finns inte"}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    user = session.get("user")
    if user:
        _log_activity(user, "Loggade ut")
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me")
@login_required
def api_me():
    return jsonify({
        "user": session["user"],
        "role": session.get("role", "user"),
        "permissions": session.get("permissions", []),
    })


@app.route("/api/users-list")
@login_required
def api_users_list():
    """Return just usernames (for chat member selection etc.)"""
    users = db.load_data("users")
    return jsonify([u.get("username") for u in users if u.get("username")])


@app.route("/api/constants")
@login_required
def api_constants():
    return jsonify({
        "businesses": BUSINESSES,
        "expense_categories": EXPENSE_CATEGORIES,
        "revenue_categories": REVENUE_CATEGORIES,
        "receipt_categories": RECEIPT_CATEGORIES,
        "calendar_types": CALENDAR_TYPES,
        "vat_rates": VAT_RATES,
        "customer_stages": CUSTOMER_STAGES,
        "customer_sources": CUSTOMER_SOURCES,
        "quote_statuses": QUOTE_STATUSES,
    })


# ---------------------------------------------------------------------------
# Dashboard API
# ---------------------------------------------------------------------------

@app.route("/api/dashboard")
@login_required
def api_dashboard():
    expenses = db.load_data("expenses")
    revenue = db.load_data("revenue")
    goals = db.load_data("goals")
    receipts = db.load_data("receipts")
    logs = db.load_data("activity_log")

    now = datetime.now()
    current_month = now.strftime("%Y-%m")

    # Summaries per business
    summary = {}
    for biz in BUSINESSES:
        biz_exp = [e for e in expenses if e.get("bolag") == biz]
        biz_rev = [r for r in revenue if r.get("bolag") == biz]

        month_exp = sum(
            float(e.get("belopp", 0))
            for e in biz_exp
            if str(e.get("datum", "")).startswith(current_month)
        )
        month_rev = sum(
            float(r.get("belopp", 0))
            for r in biz_rev
            if str(r.get("datum", "")).startswith(current_month)
        )
        total_exp = sum(float(e.get("belopp", 0)) for e in biz_exp)
        total_rev = sum(float(r.get("belopp", 0)) for r in biz_rev)

        biz_goal = next((g for g in goals if g.get("bolag") == biz), {})

        summary[biz] = {
            "month_expenses": month_exp,
            "month_revenue": month_rev,
            "total_expenses": total_exp,
            "total_revenue": total_rev,
            "profit": total_rev - total_exp,
            "annual_revenue_goal": float(biz_goal.get("annual_revenue", 0)),
            "annual_profit_goal": float(biz_goal.get("annual_profit", 0)),
        }

    # Expense breakdown by category (current year)
    year = str(now.year)
    cat_totals = {}
    for e in expenses:
        if str(e.get("datum", "")).startswith(year):
            cat = e.get("kategori", "Övrigt")
            cat_totals[cat] = cat_totals.get(cat, 0) + float(e.get("belopp", 0))

    # Monthly trend (last 6 months)
    monthly = []
    for i in range(5, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        key = f"{y}-{m:02d}"
        m_exp = sum(float(e.get("belopp", 0)) for e in expenses if str(e.get("datum", "")).startswith(key))
        m_rev = sum(float(r.get("belopp", 0)) for r in revenue if str(r.get("datum", "")).startswith(key))
        monthly.append({"month": key, "expenses": m_exp, "revenue": m_rev})

    # Pending receipts
    pending_count = len([r for r in receipts if r.get("status") == "inlamnat"])

    return jsonify({
        "summary": summary,
        "category_breakdown": cat_totals,
        "monthly_trend": monthly,
        "pending_receipts": pending_count,
        "recent_activity": (logs[-10:] if logs else [])[::-1],
    })


# ---------------------------------------------------------------------------
# Expenses API
# ---------------------------------------------------------------------------

@app.route("/api/expenses", methods=["GET"])
@login_required
def get_expenses():
    data = db.load_data("expenses")
    bolag = request.args.get("bolag")
    month = request.args.get("month")  # YYYY-MM
    if bolag and bolag != "Alla":
        data = [e for e in data if e.get("bolag") == bolag]
    if month:
        data = [e for e in data if str(e.get("datum", "")).startswith(month)]
    # Sort by date desc
    data.sort(key=lambda x: x.get("datum", ""), reverse=True)
    return jsonify(data)


@app.route("/api/expenses", methods=["POST"])
@login_required
def add_expense():
    d = request.get_json(force=True)
    expense = {
        "id": str(uuid.uuid4())[:8],
        "bolag": d.get("bolag", BUSINESSES[0]),
        "datum": d.get("datum", date.today().isoformat()),
        "kategori": d.get("kategori", "Övrigt"),
        "beskrivning": d.get("beskrivning", ""),
        "leverantor": d.get("leverantor", ""),
        "belopp": float(d.get("belopp", 0)),
        "moms_sats": int(d.get("moms_sats", 25)),
    }
    expense["moms_belopp"] = round(
        expense["belopp"] * expense["moms_sats"] / (100 + expense["moms_sats"]), 2
    )
    db.append_row("expenses", expense)
    _log_activity(session["user"], "Lade till utgift",
                  f"{expense['beskrivning']} — {expense['belopp']} kr ({expense['bolag']})")
    return jsonify({"ok": True, "expense": expense})


@app.route("/api/expenses/<eid>", methods=["PUT"])
@login_required
def update_expense(eid):
    updates = request.get_json(force=True)
    data = db.load_data("expenses")
    for row in data:
        if str(row.get("id")) == eid:
            row.update(updates)
            if "belopp" in updates or "moms_sats" in updates:
                belopp = float(row.get("belopp", 0))
                sats = int(row.get("moms_sats", 25))
                row["moms_belopp"] = round(belopp * sats / (100 + sats), 2)
            break
    db.save_data("expenses", data)
    _log_activity(session["user"], "Uppdaterade utgift", eid)
    return jsonify({"ok": True})


@app.route("/api/expenses/<eid>", methods=["DELETE"])
@login_required
def delete_expense(eid):
    data = db.load_data("expenses")
    data = [e for e in data if str(e.get("id")) != eid]
    db.save_data("expenses", data)
    _log_activity(session["user"], "Raderade utgift", eid)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Revenue API
# ---------------------------------------------------------------------------

@app.route("/api/revenue", methods=["GET"])
@login_required
def get_revenue():
    data = db.load_data("revenue")
    bolag = request.args.get("bolag")
    month = request.args.get("month")
    if bolag and bolag != "Alla":
        data = [r for r in data if r.get("bolag") == bolag]
    if month:
        data = [r for r in data if str(r.get("datum", "")).startswith(month)]
    data.sort(key=lambda x: x.get("datum", ""), reverse=True)
    return jsonify(data)


@app.route("/api/revenue", methods=["POST"])
@login_required
def add_revenue():
    d = request.get_json(force=True)
    rev = {
        "id": str(uuid.uuid4())[:8],
        "bolag": d.get("bolag", BUSINESSES[0]),
        "datum": d.get("datum", date.today().isoformat()),
        "kategori": d.get("kategori", "Övrigt"),
        "beskrivning": d.get("beskrivning", ""),
        "kund": d.get("kund", ""),
        "belopp": float(d.get("belopp", 0)),
    }
    db.append_row("revenue", rev)
    _log_activity(session["user"], "Lade till intäkt",
                  f"{rev['beskrivning']} — {rev['belopp']} kr ({rev['bolag']})")
    return jsonify({"ok": True, "revenue": rev})


@app.route("/api/revenue/<rid>", methods=["DELETE"])
@login_required
def delete_revenue(rid):
    data = db.load_data("revenue")
    data = [r for r in data if str(r.get("id")) != rid]
    db.save_data("revenue", data)
    _log_activity(session["user"], "Raderade intäkt", rid)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Budget API
# ---------------------------------------------------------------------------

@app.route("/api/budget", methods=["GET"])
@login_required
def get_budget():
    data = db.load_data("budget")
    result = {}
    for row in data:
        biz = row.get("bolag")
        if biz:
            result[biz] = {
                "total": float(row.get("total", 0)),
                "kategorier": json.loads(row["kategorier"]) if isinstance(row.get("kategorier"), str) and row["kategorier"].strip().startswith("{") else {},
            }
    return jsonify(result)


@app.route("/api/budget", methods=["POST"])
@login_required
def save_budget():
    d = request.get_json(force=True)
    bolag = d.get("bolag")
    budget_row = {
        "bolag": bolag,
        "total": float(d.get("total", 0)),
        "kategorier": json.dumps(d.get("kategorier", {}), ensure_ascii=False),
    }
    data = db.load_data("budget")
    found = False
    for row in data:
        if row.get("bolag") == bolag:
            row.update(budget_row)
            found = True
            break
    if not found:
        data.append(budget_row)
    db.save_data("budget", data)
    _log_activity(session["user"], "Uppdaterade budget", bolag)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Goals API
# ---------------------------------------------------------------------------

@app.route("/api/goals", methods=["GET"])
@login_required
def get_goals():
    data = db.load_data("goals")
    result = {}
    for row in data:
        biz = row.get("bolag")
        if biz:
            result[biz] = {
                "annual_revenue": float(row.get("annual_revenue", 0)),
                "annual_profit": float(row.get("annual_profit", 0)),
            }
    return jsonify(result)


@app.route("/api/goals", methods=["POST"])
@login_required
def save_goals():
    d = request.get_json(force=True)
    bolag = d.get("bolag")
    goal = {
        "bolag": bolag,
        "annual_revenue": float(d.get("annual_revenue", 0)),
        "annual_profit": float(d.get("annual_profit", 0)),
    }
    data = db.load_data("goals")
    found = False
    for row in data:
        if row.get("bolag") == bolag:
            row.update(goal)
            found = True
            break
    if not found:
        data.append(goal)
    db.save_data("goals", data)
    _log_activity(session["user"], "Uppdaterade mål", bolag)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Receipts API
# ---------------------------------------------------------------------------

@app.route("/api/receipts", methods=["GET"])
@login_required
def get_receipts():
    data = db.load_data("receipts")
    status = request.args.get("status")
    bolag = request.args.get("bolag")
    month = request.args.get("month")
    if status:
        data = [r for r in data if r.get("status") == status]
    if bolag and bolag != "Alla":
        data = [r for r in data if r.get("bolag") == bolag]
    if month:
        data = [r for r in data if str(r.get("datum", "")).startswith(month)]
    data.sort(key=lambda x: x.get("created", ""), reverse=True)
    return jsonify(data)


@app.route("/api/receipts", methods=["POST"])
@login_required
def add_receipt():
    bolag = request.form.get("bolag", BUSINESSES[0])
    beskrivning = request.form.get("beskrivning", "")
    belopp = float(request.form.get("belopp", 0))
    kategori = request.form.get("kategori", "Övrigt")
    datum = request.form.get("datum", date.today().isoformat())

    # Handle file uploads
    files = request.files.getlist("files")
    file_paths = []
    for f in files:
        if f and f.filename:
            fname = f"{uuid.uuid4().hex[:8]}_{secure_filename(f.filename)}"
            save_path = app.config["UPLOAD_FOLDER"] / fname
            save_path.parent.mkdir(parents=True, exist_ok=True)
            f.save(str(save_path))
            file_paths.append(fname)

    receipt = {
        "id": str(uuid.uuid4())[:8],
        "user": session["user"],
        "bolag": bolag,
        "datum": datum,
        "beskrivning": beskrivning,
        "belopp": belopp,
        "kategori": kategori,
        "status": "inlamnat",
        "files": json.dumps(file_paths, ensure_ascii=False),
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    db.append_row("receipts", receipt)
    _log_activity(session["user"], "Laddade upp kvitto",
                  f"{beskrivning} — {belopp} kr")
    return jsonify({"ok": True, "receipt": receipt})


@app.route("/api/receipts/<rid>/status", methods=["PUT"])
@login_required
def update_receipt_status(rid):
    d = request.get_json(force=True)
    new_status = d.get("status")  # godkannt / avvisat
    data = db.load_data("receipts")
    for row in data:
        if str(row.get("id")) == rid:
            row["status"] = new_status
            break
    db.save_data("receipts", data)
    _log_activity(session["user"], f"Kvitto {new_status}", rid)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Calendar API
# ---------------------------------------------------------------------------

@app.route("/api/calendar/events", methods=["GET"])
@login_required
def get_events():
    data = db.load_data("calendar_events")
    year = request.args.get("year")
    month = request.args.get("month")
    if year and month:
        prefix = f"{year}-{int(month):02d}"
        data = [e for e in data if str(e.get("datum", "")).startswith(prefix)]
    data.sort(key=lambda x: (x.get("datum", ""), x.get("time", "")))
    return jsonify(data)


@app.route("/api/calendar/events", methods=["POST"])
@login_required
def add_event():
    d = request.get_json(force=True)
    event = {
        "id": f"evt_{uuid.uuid4().hex[:8]}",
        "title": d.get("title", ""),
        "datum": d.get("datum", date.today().isoformat()),
        "time": d.get("time", ""),
        "type": d.get("type", "Övrigt"),
        "business": d.get("business", "Alla"),
        "beskrivning": d.get("beskrivning", ""),
        "created_by": session["user"],
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    db.append_row("calendar_events", event)
    _log_activity(session["user"], "Skapade händelse", event["title"])
    return jsonify({"ok": True, "event": event})


@app.route("/api/calendar/events/<eid>", methods=["DELETE"])
@login_required
def delete_event(eid):
    data = db.load_data("calendar_events")
    data = [e for e in data if str(e.get("id")) != eid]
    db.save_data("calendar_events", data)
    _log_activity(session["user"], "Raderade händelse", eid)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Todos API
# ---------------------------------------------------------------------------

@app.route("/api/todos", methods=["GET"])
@login_required
def get_todos():
    data = db.load_data("todos")
    data.sort(key=lambda x: (
        str(x.get("done", "False")).lower() == "true",
        {"Hög": 0, "Medel": 1, "Låg": 2}.get(x.get("priority", "Medel"), 1),
    ))
    return jsonify(data)


@app.route("/api/todos", methods=["POST"])
@login_required
def add_todo():
    d = request.get_json(force=True)
    todo = {
        "id": f"todo_{uuid.uuid4().hex[:8]}",
        "task": d.get("task", ""),
        "priority": d.get("priority", "Medel"),
        "deadline": d.get("deadline", ""),
        "done": False,
        "created_by": session["user"],
        "created": datetime.now().strftime("%Y-%m-%d"),
    }
    db.append_row("todos", todo)
    return jsonify({"ok": True, "todo": todo})


@app.route("/api/todos/<tid>", methods=["PUT"])
@login_required
def update_todo(tid):
    d = request.get_json(force=True)
    data = db.load_data("todos")
    for row in data:
        if str(row.get("id")) == tid:
            row.update(d)
            break
    db.save_data("todos", data)
    return jsonify({"ok": True})


@app.route("/api/todos/<tid>", methods=["DELETE"])
@login_required
def delete_todo(tid):
    data = db.load_data("todos")
    data = [t for t in data if str(t.get("id")) != tid]
    db.save_data("todos", data)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Chat API
# ---------------------------------------------------------------------------

@app.route("/api/chat/groups", methods=["GET"])
@login_required
def get_chat_groups():
    groups = db.load_data("chat_groups")
    user = session["user"]
    result = []
    for g in groups:
        members = g.get("members", "[]")
        if isinstance(members, str):
            try:
                members = json.loads(members)
            except Exception:
                members = []
        if user in members or session.get("role") == "admin":
            g["members"] = members
            result.append(g)
    return jsonify(result)


@app.route("/api/chat/groups", methods=["POST"])
@login_required
def create_chat_group():
    d = request.get_json(force=True)
    group = {
        "id": str(uuid.uuid4())[:8],
        "name": d.get("name", "Ny grupp"),
        "created_by": session["user"],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "members": json.dumps(d.get("members", [session["user"]]), ensure_ascii=False),
        "archived": False,
    }
    db.append_row("chat_groups", group)
    _log_activity(session["user"], "Skapade chattgrupp", group["name"])
    return jsonify({"ok": True, "group": group})


@app.route("/api/chat/groups/<gid>/messages", methods=["GET"])
@login_required
def get_messages(gid):
    messages = db.load_data("chat_messages")
    msgs = [m for m in messages if str(m.get("group_id")) == gid]
    msgs.sort(key=lambda x: x.get("timestamp", ""))
    return jsonify(msgs)


@app.route("/api/chat/groups/<gid>/messages", methods=["POST"])
@login_required
def send_message(gid):
    d = request.get_json(force=True)
    msg = {
        "id": str(uuid.uuid4())[:8],
        "group_id": gid,
        "sender": session["user"],
        "content": d.get("content", ""),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    db.append_row("chat_messages", msg)
    return jsonify({"ok": True, "message": msg})


# ---------------------------------------------------------------------------
# Admin API
# ---------------------------------------------------------------------------

@app.route("/api/admin/users", methods=["GET"])
@admin_required
def admin_get_users():
    users = db.load_data("users")
    # Don't send password hashes to client
    safe = []
    for u in users:
        safe.append({
            "username": u.get("username"),
            "role": u.get("role"),
            "permissions": _parse_permissions(u.get("permissions")),
        })
    return jsonify(safe)


@app.route("/api/admin/users", methods=["POST"])
@admin_required
def admin_create_user():
    d = request.get_json(force=True)
    username = d.get("username", "").strip()
    password = d.get("password", "1234")
    role = d.get("role", "user")
    permissions = d.get("permissions", [])

    users = db.load_data("users")
    for u in users:
        if u.get("username") == username:
            return jsonify({"ok": False, "error": "Användaren finns redan"}), 409

    new_user = {
        "username": username,
        "password_hash": _hash(password),
        "role": role,
        "permissions": json.dumps(permissions, ensure_ascii=False),
    }
    users.append(new_user)
    db.save_data("users", users)
    _log_activity(session["user"], "Skapade användare", username)
    return jsonify({"ok": True})


@app.route("/api/admin/users/<username>", methods=["PUT"])
@admin_required
def admin_update_user(username):
    d = request.get_json(force=True)
    users = db.load_data("users")
    for u in users:
        if u.get("username") == username:
            if "role" in d:
                u["role"] = d["role"]
            if "permissions" in d:
                u["permissions"] = json.dumps(d["permissions"], ensure_ascii=False)
            if "password" in d and d["password"]:
                u["password_hash"] = _hash(d["password"])
            break
    db.save_data("users", users)
    _log_activity(session["user"], "Uppdaterade användare", username)
    return jsonify({"ok": True})


@app.route("/api/admin/users/<username>", methods=["DELETE"])
@admin_required
def admin_delete_user(username):
    if username in ("Viktor", "admin"):
        return jsonify({"ok": False, "error": "Kan inte ta bort denna användare"}), 403
    users = db.load_data("users")
    users = [u for u in users if u.get("username") != username]
    db.save_data("users", users)
    _log_activity(session["user"], "Raderade användare", username)
    return jsonify({"ok": True})


@app.route("/api/admin/activity-log")
@login_required
def get_activity_log():
    logs = db.load_data("activity_log")
    logs.reverse()
    return jsonify(logs[:100])


# ---------------------------------------------------------------------------
# CRM — Customers API
# ---------------------------------------------------------------------------

@app.route("/api/customers", methods=["GET"])
@login_required
def get_customers():
    data = db.load_data("customers")
    stage = request.args.get("stage")
    bolag = request.args.get("bolag")
    search = request.args.get("q", "").lower()
    if stage and stage != "Alla":
        data = [c for c in data if c.get("stage") == stage]
    if bolag and bolag != "Alla":
        data = [c for c in data if c.get("bolag") == bolag]
    if search:
        data = [c for c in data if search in (c.get("name", "") + c.get("email", "") + c.get("company", "")).lower()]
    data.sort(key=lambda x: x.get("updated", x.get("created", "")), reverse=True)
    return jsonify(data)


@app.route("/api/customers", methods=["POST"])
@login_required
def add_customer():
    d = request.get_json(force=True)
    customer = {
        "id": f"cust_{uuid.uuid4().hex[:8]}",
        "name": d.get("name", ""),
        "company": d.get("company", ""),
        "email": d.get("email", ""),
        "phone": d.get("phone", ""),
        "bolag": d.get("bolag", BUSINESSES[0]),
        "stage": d.get("stage", "Lead"),
        "source": d.get("source", "Övrigt"),
        "value": float(d.get("value", 0)),
        "notes": d.get("notes", ""),
        "assigned_to": d.get("assigned_to", session["user"]),
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    db.append_row("customers", customer)
    _log_activity(session["user"], "Lade till kund", customer["name"])
    return jsonify({"ok": True, "customer": customer})


@app.route("/api/customers/<cid>", methods=["PUT"])
@login_required
def update_customer(cid):
    updates = request.get_json(force=True)
    data = db.load_data("customers")
    for row in data:
        if str(row.get("id")) == cid:
            row.update(updates)
            row["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    db.save_data("customers", data)
    _log_activity(session["user"], "Uppdaterade kund", cid)
    return jsonify({"ok": True})


@app.route("/api/customers/<cid>", methods=["DELETE"])
@login_required
def delete_customer(cid):
    data = db.load_data("customers")
    data = [c for c in data if str(c.get("id")) != cid]
    db.save_data("customers", data)
    _log_activity(session["user"], "Raderade kund", cid)
    return jsonify({"ok": True})


@app.route("/api/customers/<cid>/notes", methods=["POST"])
@login_required
def add_customer_note(cid):
    d = request.get_json(force=True)
    note = {
        "id": f"note_{uuid.uuid4().hex[:6]}",
        "customer_id": cid,
        "text": d.get("text", ""),
        "author": session["user"],
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    db.append_row("customer_notes", note)
    return jsonify({"ok": True, "note": note})


@app.route("/api/customers/<cid>/notes", methods=["GET"])
@login_required
def get_customer_notes(cid):
    data = db.load_data("customer_notes")
    notes = [n for n in data if str(n.get("customer_id")) == cid]
    notes.sort(key=lambda x: x.get("created", ""), reverse=True)
    return jsonify(notes)


# ---------------------------------------------------------------------------
# CRM — Pipeline API (customers grouped by stage)
# ---------------------------------------------------------------------------

@app.route("/api/pipeline", methods=["GET"])
@login_required
def get_pipeline():
    customers = db.load_data("customers")
    bolag = request.args.get("bolag")
    if bolag and bolag != "Alla":
        customers = [c for c in customers if c.get("bolag") == bolag]

    pipeline = {}
    for stage in CUSTOMER_STAGES:
        stage_custs = [c for c in customers if c.get("stage") == stage]
        total_value = sum(float(c.get("value", 0)) for c in stage_custs)
        pipeline[stage] = {"customers": stage_custs, "count": len(stage_custs), "total_value": total_value}
    return jsonify(pipeline)


@app.route("/api/customers/<cid>/stage", methods=["PUT"])
@login_required
def update_customer_stage(cid):
    d = request.get_json(force=True)
    new_stage = d.get("stage")
    data = db.load_data("customers")
    name = ""
    for row in data:
        if str(row.get("id")) == cid:
            row["stage"] = new_stage
            row["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            name = row.get("name", cid)
            break
    db.save_data("customers", data)
    _log_activity(session["user"], f"Flyttade kund till {new_stage}", name)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Quotes / Offerter API
# ---------------------------------------------------------------------------

@app.route("/api/quotes", methods=["GET"])
@login_required
def get_quotes():
    data = db.load_data("quotes")
    status = request.args.get("status")
    bolag = request.args.get("bolag")
    if status and status != "Alla":
        data = [q for q in data if q.get("status") == status]
    if bolag and bolag != "Alla":
        data = [q for q in data if q.get("bolag") == bolag]
    data.sort(key=lambda x: x.get("created", ""), reverse=True)
    return jsonify(data)


@app.route("/api/quotes", methods=["POST"])
@login_required
def create_quote():
    d = request.get_json(force=True)
    items = d.get("items", [])
    subtotal = sum(float(it.get("total", 0)) for it in items)
    moms_total = sum(
        float(it.get("total", 0)) * int(it.get("moms", 25)) / (100 + int(it.get("moms", 25)))
        for it in items
    )

    quote = {
        "id": f"Q-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
        "customer_id": d.get("customer_id", ""),
        "customer_name": d.get("customer_name", ""),
        "bolag": d.get("bolag", BUSINESSES[0]),
        "title": d.get("title", "Offert"),
        "description": d.get("description", ""),
        "items": json.dumps(items, ensure_ascii=False),
        "subtotal": round(subtotal, 2),
        "moms_total": round(moms_total, 2),
        "total": round(subtotal, 2),
        "valid_until": d.get("valid_until", ""),
        "status": "Utkast",
        "created_by": session["user"],
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    db.append_row("quotes", quote)
    _log_activity(session["user"], "Skapade offert", f"{quote['id']} — {quote['customer_name']}")
    return jsonify({"ok": True, "quote": quote})


@app.route("/api/quotes/<qid>", methods=["PUT"])
@login_required
def update_quote(qid):
    updates = request.get_json(force=True)
    data = db.load_data("quotes")
    for row in data:
        if str(row.get("id")) == qid:
            if "items" in updates:
                items = updates["items"]
                updates["items"] = json.dumps(items, ensure_ascii=False)
                updates["subtotal"] = round(sum(float(it.get("total", 0)) for it in items), 2)
                updates["moms_total"] = round(sum(
                    float(it.get("total", 0)) * int(it.get("moms", 25)) / (100 + int(it.get("moms", 25)))
                    for it in items
                ), 2)
                updates["total"] = updates["subtotal"]
            row.update(updates)
            row["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    db.save_data("quotes", data)
    _log_activity(session["user"], "Uppdaterade offert", qid)
    return jsonify({"ok": True})


@app.route("/api/quotes/<qid>", methods=["DELETE"])
@login_required
def delete_quote(qid):
    data = db.load_data("quotes")
    data = [q for q in data if str(q.get("id")) != qid]
    db.save_data("quotes", data)
    _log_activity(session["user"], "Raderade offert", qid)
    return jsonify({"ok": True})


@app.route("/api/quotes/<qid>/status", methods=["PUT"])
@login_required
def update_quote_status(qid):
    d = request.get_json(force=True)
    new_status = d.get("status")
    data = db.load_data("quotes")
    for row in data:
        if str(row.get("id")) == qid:
            row["status"] = new_status
            row["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    db.save_data("quotes", data)
    _log_activity(session["user"], f"Offert {new_status}", qid)
    return jsonify({"ok": True})


@app.route("/api/quotes/<qid>/pdf")
@login_required
def generate_quote_pdf(qid):
    """Generate a PDF for a quote."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER

    data = db.load_data("quotes")
    quote = None
    for q in data:
        if str(q.get("id")) == qid:
            quote = q
            break
    if not quote:
        return jsonify({"error": "Offert ej hittad"}), 404

    items = quote.get("items", "[]")
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except Exception:
            items = []

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=30*mm, bottomMargin=20*mm,
                            leftMargin=25*mm, rightMargin=25*mm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='RightAlign', parent=styles['Normal'], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='CenterAlign', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10))
    styles.add(ParagraphStyle(name='SmallGray', parent=styles['Normal'], fontSize=8, textColor=colors.gray))

    elements = []

    # Header
    elements.append(Paragraph(f"<b>{quote.get('bolag', 'Unithread')}</b>", styles['Title']))
    elements.append(Spacer(1, 5*mm))

    # Quote title & ID
    elements.append(Paragraph(f"<b>OFFERT</b> {quote['id']}", styles['Heading2']))
    elements.append(Spacer(1, 3*mm))

    # Customer & date info
    info_data = [
        ["Kund:", quote.get("customer_name", "—"),
         "Datum:", quote.get("created", "")[:10]],
        ["Titel:", quote.get("title", ""),
         "Giltig till:", quote.get("valid_until", "—")],
    ]
    info_table = Table(info_data, colWidths=[55, 150, 65, 100])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.gray),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.gray),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 8*mm))

    if quote.get("description"):
        elements.append(Paragraph(quote["description"], styles['Normal']))
        elements.append(Spacer(1, 5*mm))

    # Items table
    table_header = ['#', 'Beskrivning', 'Antal', 'À-pris', 'Moms %', 'Summa']
    table_data = [table_header]
    for i, item in enumerate(items, 1):
        table_data.append([
            str(i),
            str(item.get("description", "")),
            str(item.get("quantity", 1)),
            f"{float(item.get('unit_price', 0)):,.0f} kr",
            f"{item.get('moms', 25)}%",
            f"{float(item.get('total', 0)):,.0f} kr",
        ])

    col_widths = [25, 180, 45, 70, 45, 70]
    items_table = Table(table_data, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 5*mm))

    # Totals
    subtotal = float(quote.get("subtotal", 0))
    moms_total = float(quote.get("moms_total", 0))
    total = float(quote.get("total", 0))
    totals_data = [
        ['', '', '', '', 'Delsumma:', f"{subtotal:,.0f} kr"],
        ['', '', '', '', 'Moms:', f"{moms_total:,.0f} kr"],
        ['', '', '', '', 'TOTALT:', f"{total:,.0f} kr"],
    ]
    totals_table = Table(totals_data, colWidths=col_widths)
    totals_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (-2, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (-2, -1), (-1, -1), 11),
        ('LINEABOVE', (-2, -1), (-1, -1), 1, colors.HexColor('#4f46e5')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 15*mm))

    elements.append(Paragraph(f"Skapad av {quote.get('created_by', '')} · Unithread", styles['SmallGray']))

    doc.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf',
                     download_name=f"Offert_{quote['id']}.pdf", as_attachment=False)


# ---------------------------------------------------------------------------
# Export API — PDF / Excel
# ---------------------------------------------------------------------------

@app.route("/api/export/expenses")
@login_required
def export_expenses():
    fmt = request.args.get("format", "excel")
    bolag = request.args.get("bolag")
    month = request.args.get("month")
    data = db.load_data("expenses")
    if bolag and bolag != "Alla":
        data = [e for e in data if e.get("bolag") == bolag]
    if month:
        data = [e for e in data if str(e.get("datum", "")).startswith(month)]
    data.sort(key=lambda x: x.get("datum", ""), reverse=True)

    if fmt == "excel":
        return _export_excel(data, "Utgifter",
                             ["datum", "bolag", "kategori", "beskrivning", "leverantor", "belopp", "moms_sats", "moms_belopp"],
                             ["Datum", "Bolag", "Kategori", "Beskrivning", "Leverantör", "Belopp", "Moms %", "Momsbelopp"])
    else:
        return _export_pdf_table("Utgiftsrapport", data,
                                 ["datum", "bolag", "kategori", "beskrivning", "belopp"],
                                 ["Datum", "Bolag", "Kategori", "Beskrivning", "Belopp"])


@app.route("/api/export/revenue")
@login_required
def export_revenue():
    fmt = request.args.get("format", "excel")
    bolag = request.args.get("bolag")
    month = request.args.get("month")
    data = db.load_data("revenue")
    if bolag and bolag != "Alla":
        data = [r for r in data if r.get("bolag") == bolag]
    if month:
        data = [r for r in data if str(r.get("datum", "")).startswith(month)]
    data.sort(key=lambda x: x.get("datum", ""), reverse=True)

    if fmt == "excel":
        return _export_excel(data, "Intäkter",
                             ["datum", "bolag", "kategori", "beskrivning", "kund", "belopp"],
                             ["Datum", "Bolag", "Kategori", "Beskrivning", "Kund", "Belopp"])
    else:
        return _export_pdf_table("Intäktsrapport", data,
                                 ["datum", "bolag", "kategori", "beskrivning", "kund", "belopp"],
                                 ["Datum", "Bolag", "Kategori", "Beskrivning", "Kund", "Belopp"])


@app.route("/api/export/customers")
@login_required
def export_customers():
    data = db.load_data("customers")
    return _export_excel(data, "Kunder",
                         ["name", "company", "email", "phone", "bolag", "stage", "value", "assigned_to", "created"],
                         ["Namn", "Företag", "E-post", "Telefon", "Bolag", "Stadie", "Värde", "Ansvarig", "Skapad"])


def _export_excel(data, sheet_title, fields, headers):
    """Generic Excel export."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title

    # Header style
    header_fill = PatternFill(start_color="4f46e5", end_color="4f46e5", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=10)
    border = Border(bottom=Side(style='thin', color='e2e8f0'))

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')

    for row_idx, item in enumerate(data, 2):
        for col_idx, field in enumerate(fields, 1):
            val = item.get(field, "")
            try:
                val = float(val)
            except (ValueError, TypeError):
                pass
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = border

    # Auto-width columns
    for col in ws.columns:
        max_len = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     download_name=f"{sheet_title}_{date.today().isoformat()}.xlsx", as_attachment=True)


def _export_pdf_table(title, data, fields, headers):
    """Generic PDF table export."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=20*mm, bottomMargin=15*mm,
                            leftMargin=15*mm, rightMargin=15*mm)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(f"<b>{title}</b>", styles['Title']),
        Paragraph(f"Exporterad {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']),
        Spacer(1, 8*mm),
    ]

    table_data = [headers]
    for item in data[:500]:
        row = []
        for field in fields:
            val = item.get(field, "")
            if field == "belopp":
                try:
                    val = f"{float(val):,.0f} kr"
                except (ValueError, TypeError):
                    pass
            row.append(str(val)[:50])
        table_data.append(row)

    n_cols = len(headers)
    col_width = (landscape(A4)[0] - 30*mm) / n_cols
    t = Table(table_data, colWidths=[col_width] * n_cols)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)

    doc.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf',
                     download_name=f"{title}_{date.today().isoformat()}.pdf", as_attachment=True)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.config["UPLOAD_FOLDER"].mkdir(parents=True, exist_ok=True)
    app.run(debug=True, port=5000)
