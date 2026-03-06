"""
Automated tests for Unithread App — Flask backend.
Uses an in-memory mock DB so no Google Sheets API calls are made.
Run with: python -m pytest tests/ -v
"""

import json
import io
import sys
import os
import pytest
import bcrypt
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# In-memory mock DB (replaces google_sheets.db)
# ---------------------------------------------------------------------------

class MockDB:
    """In-memory database that mimics GoogleSheetsDB interface."""

    def __init__(self):
        self._data = {}

    def load_data(self, sheet_name):
        return list(self._data.get(sheet_name, []))

    def save_data(self, sheet_name, data_list):
        self._data[sheet_name] = list(data_list)

    def append_row(self, sheet_name, row_dict):
        if sheet_name not in self._data:
            self._data[sheet_name] = []
        self._data[sheet_name].append(dict(row_dict))

    def delete_rows_by_field(self, sheet_name, field, value):
        data = self.load_data(sheet_name)
        filtered = [row for row in data if str(row.get(field, "")) != str(value)]
        self.save_data(sheet_name, filtered)

    def update_rows_by_field(self, sheet_name, field, value, updates):
        data = self.load_data(sheet_name)
        for row in data:
            if str(row.get(field, "")) == str(value):
                row.update(updates)
        self.save_data(sheet_name, data)

    def clear_cache(self):
        pass

    def reset(self):
        """Clear all data for test isolation."""
        self._data.clear()


# Create mock before importing app
mock_db = MockDB()


# ---------------------------------------------------------------------------
# Patch google_sheets module before importing app
# ---------------------------------------------------------------------------

# Create a mock google_sheets module
mock_gs_module = MagicMock()
mock_gs_module.db = mock_db
sys.modules['google_sheets'] = mock_gs_module

# Now import the Flask app
from app import app, _hash_password, _verify_password, _validate_amount, _sanitize_string


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_db():
    """Reset mock DB before each test."""
    mock_db.reset()
    yield


@pytest.fixture
def client():
    """Flask test client."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    app.config['RATELIMIT_ENABLED'] = False  # Disable rate limiting for testing
    with app.test_client() as client:
        yield client


@pytest.fixture
def admin_user():
    """Create an admin user and return their credentials."""
    pw_hash = _hash_password("SecurePass123")
    mock_db.save_data("users", [{
        "username": "TestAdmin",
        "password_hash": pw_hash,
        "role": "admin",
        "permissions": json.dumps(["access_settings", "access_reports", "create_chat", "archive_chat"]),
    }])
    return {"username": "TestAdmin", "password": "SecurePass123"}


@pytest.fixture
def regular_user():
    """Create a regular user."""
    pw_hash = _hash_password("UserPass456")
    mock_db.save_data("users", [{
        "username": "TestUser",
        "password_hash": pw_hash,
        "role": "user",
        "permissions": "[]",
    }])
    return {"username": "TestUser", "password": "UserPass456"}


@pytest.fixture
def logged_in_admin(client, admin_user):
    """Client logged in as admin."""
    client.post("/api/login", json=admin_user)
    return client


@pytest.fixture
def logged_in_user(client, regular_user):
    """Client logged in as regular user."""
    client.post("/api/login", json=regular_user)
    return client


# =====================================================================
# Password hashing tests
# =====================================================================

class TestPasswordHashing:
    def test_hash_password_returns_bcrypt(self):
        h = _hash_password("testpass")
        assert h.startswith("$2b$")

    def test_verify_correct_password(self):
        h = _hash_password("mypassword")
        assert _verify_password("mypassword", h) is True

    def test_verify_wrong_password(self):
        h = _hash_password("mypassword")
        assert _verify_password("wrongpassword", h) is False

    def test_verify_legacy_sha256(self):
        """Legacy SHA-256 hashes should still verify."""
        import hashlib
        legacy = hashlib.sha256("oldpass".encode()).hexdigest()
        assert _verify_password("oldpass", legacy) is True
        assert _verify_password("wrongpass", legacy) is False

    def test_different_passwords_different_hashes(self):
        h1 = _hash_password("password1")
        h2 = _hash_password("password2")
        assert h1 != h2

    def test_same_password_different_salts(self):
        h1 = _hash_password("samepass")
        h2 = _hash_password("samepass")
        assert h1 != h2  # bcrypt uses random salt


# =====================================================================
# Input validation tests
# =====================================================================

class TestValidation:
    def test_validate_amount_positive(self):
        assert _validate_amount(100) == 100.0

    def test_validate_amount_zero(self):
        assert _validate_amount(0) == 0.0

    def test_validate_amount_string(self):
        assert _validate_amount("42.50") == 42.5

    def test_validate_amount_negative_raises(self):
        with pytest.raises(ValueError, match="negativt"):
            _validate_amount(-50)

    def test_validate_amount_too_large_raises(self):
        with pytest.raises(ValueError, match="för stort"):
            _validate_amount(10_000_000_000)

    def test_validate_amount_non_numeric_raises(self):
        with pytest.raises(ValueError, match="Ogiltigt"):
            _validate_amount("hello")

    def test_sanitize_string(self):
        assert _sanitize_string("  hello world  ") == "hello world"

    def test_sanitize_string_max_length(self):
        result = _sanitize_string("a" * 1000, max_length=10)
        assert len(result) == 10

    def test_sanitize_string_none(self):
        assert _sanitize_string(None) == ""

    def test_sanitize_string_non_string(self):
        assert _sanitize_string(42) == "42"


# =====================================================================
# Auth API tests
# =====================================================================

class TestAuth:
    def test_login_success(self, client, admin_user):
        res = client.post("/api/login", json=admin_user)
        data = res.get_json()
        assert data["ok"] is True
        assert data["user"] == "TestAdmin"
        assert data["role"] == "admin"

    def test_login_wrong_password(self, client, admin_user):
        res = client.post("/api/login", json={
            "username": "TestAdmin",
            "password": "wrongpass",
        })
        assert res.status_code == 401
        assert res.get_json()["ok"] is False

    def test_login_nonexistent_user(self, client):
        res = client.post("/api/login", json={
            "username": "ghost",
            "password": "nope",
        })
        assert res.status_code == 401

    def test_login_empty_fields(self, client):
        res = client.post("/api/login", json={
            "username": "",
            "password": "",
        })
        assert res.status_code == 400

    def test_logout(self, logged_in_admin):
        res = logged_in_admin.post("/api/logout")
        data = res.get_json()
        assert data["ok"] is True

        # Should be logged out now
        res = logged_in_admin.get("/api/me")
        assert res.status_code == 401

    def test_me_endpoint(self, logged_in_admin):
        res = logged_in_admin.get("/api/me")
        data = res.get_json()
        assert data["user"] == "TestAdmin"
        assert data["role"] == "admin"

    def test_me_unauthenticated(self, client):
        res = client.get("/api/me")
        assert res.status_code == 401


# =====================================================================
# Expense API tests
# =====================================================================

class TestExpenses:
    def test_add_expense(self, logged_in_admin):
        res = logged_in_admin.post("/api/expenses", json={
            "bolag": "Unithread",
            "datum": "2026-03-01",
            "kategori": "IT & Programvara",
            "beskrivning": "GitHub Pro",
            "leverantor": "GitHub",
            "belopp": 299,
            "moms_sats": 25,
        })
        data = res.get_json()
        assert data["ok"] is True
        assert data["expense"]["belopp"] == 299

    def test_add_expense_negative_amount(self, logged_in_admin):
        res = logged_in_admin.post("/api/expenses", json={
            "bolag": "Unithread",
            "belopp": -100,
        })
        assert res.status_code == 400
        assert "negativt" in res.get_json()["error"]

    def test_add_expense_invalid_bolag(self, logged_in_admin):
        res = logged_in_admin.post("/api/expenses", json={
            "bolag": "Hackers Inc",
            "belopp": 100,
        })
        assert res.status_code == 400
        assert "Ogiltigt bolag" in res.get_json()["error"]

    def test_add_expense_invalid_vat(self, logged_in_admin):
        res = logged_in_admin.post("/api/expenses", json={
            "bolag": "Unithread",
            "belopp": 100,
            "moms_sats": 99,
        })
        assert res.status_code == 400
        assert "momssats" in res.get_json()["error"]

    def test_get_expenses(self, logged_in_admin):
        logged_in_admin.post("/api/expenses", json={
            "bolag": "Unithread",
            "belopp": 500,
            "beskrivning": "Test",
        })
        res = logged_in_admin.get("/api/expenses")
        data = res.get_json()
        assert len(data) == 1
        assert data[0]["belopp"] == 500

    def test_get_expenses_filter_bolag(self, logged_in_admin):
        logged_in_admin.post("/api/expenses", json={"bolag": "Unithread", "belopp": 100})
        logged_in_admin.post("/api/expenses", json={"bolag": "Merchoteket", "belopp": 200})
        res = logged_in_admin.get("/api/expenses?bolag=Unithread")
        data = res.get_json()
        assert len(data) == 1
        assert data[0]["bolag"] == "Unithread"

    def test_delete_expense(self, logged_in_admin):
        res = logged_in_admin.post("/api/expenses", json={
            "bolag": "Unithread",
            "belopp": 100,
        })
        eid = res.get_json()["expense"]["id"]
        logged_in_admin.delete(f"/api/expenses/{eid}")
        res = logged_in_admin.get("/api/expenses")
        assert len(res.get_json()) == 0

    def test_expense_unauthenticated(self, client):
        res = client.get("/api/expenses")
        assert res.status_code == 401


# =====================================================================
# Revenue API tests
# =====================================================================

class TestRevenue:
    def test_add_revenue(self, logged_in_admin):
        res = logged_in_admin.post("/api/revenue", json={
            "bolag": "Unithread",
            "beskrivning": "Försäljning",
            "kund": "Kund AB",
            "belopp": 10000,
        })
        data = res.get_json()
        assert data["ok"] is True
        assert data["revenue"]["belopp"] == 10000

    def test_add_revenue_negative_amount(self, logged_in_admin):
        res = logged_in_admin.post("/api/revenue", json={
            "bolag": "Unithread",
            "belopp": -500,
        })
        assert res.status_code == 400

    def test_add_revenue_invalid_bolag(self, logged_in_admin):
        res = logged_in_admin.post("/api/revenue", json={
            "bolag": "FakeCompany",
            "belopp": 100,
        })
        assert res.status_code == 400

    def test_delete_revenue(self, logged_in_admin):
        res = logged_in_admin.post("/api/revenue", json={
            "bolag": "Unithread",
            "belopp": 100,
        })
        rid = res.get_json()["revenue"]["id"]
        logged_in_admin.delete(f"/api/revenue/{rid}")
        res = logged_in_admin.get("/api/revenue")
        assert len(res.get_json()) == 0


# =====================================================================
# Admin API tests
# =====================================================================

class TestAdmin:
    def test_create_user(self, logged_in_admin):
        res = logged_in_admin.post("/api/admin/users", json={
            "username": "NewUser",
            "password": "StrongPass123",
            "role": "user",
        })
        assert res.get_json()["ok"] is True

    def test_create_user_weak_password(self, logged_in_admin):
        res = logged_in_admin.post("/api/admin/users", json={
            "username": "WeakUser",
            "password": "123",
            "role": "user",
        })
        assert res.status_code == 400
        assert "minst 6" in res.get_json()["error"]

    def test_create_user_empty_password(self, logged_in_admin):
        res = logged_in_admin.post("/api/admin/users", json={
            "username": "NoPassUser",
            "password": "",
            "role": "user",
        })
        assert res.status_code == 400

    def test_create_user_invalid_role(self, logged_in_admin):
        res = logged_in_admin.post("/api/admin/users", json={
            "username": "BadRole",
            "password": "StrongPass",
            "role": "superadmin",
        })
        assert res.status_code == 400
        assert "Ogiltig roll" in res.get_json()["error"]

    def test_create_duplicate_user(self, logged_in_admin):
        logged_in_admin.post("/api/admin/users", json={
            "username": "Dup",
            "password": "Password123",
            "role": "user",
        })
        res = logged_in_admin.post("/api/admin/users", json={
            "username": "Dup",
            "password": "Password123",
            "role": "user",
        })
        assert res.status_code == 409

    def test_get_users(self, logged_in_admin):
        res = logged_in_admin.get("/api/admin/users")
        users = res.get_json()
        assert isinstance(users, list)
        assert any(u["username"] == "TestAdmin" for u in users)
        # Should NOT expose password hashes
        for u in users:
            assert "password_hash" not in u

    def test_delete_protected_user(self, logged_in_admin):
        res = logged_in_admin.delete("/api/admin/users/Viktor")
        assert res.status_code == 403

    def test_regular_user_cannot_admin(self, logged_in_user):
        res = logged_in_user.get("/api/admin/users")
        assert res.status_code == 403

    def test_update_user_password(self, logged_in_admin):
        logged_in_admin.post("/api/admin/users", json={
            "username": "PwChange",
            "password": "OldPass123",
            "role": "user",
        })
        res = logged_in_admin.put("/api/admin/users/PwChange", json={
            "password": "NewPass789",
        })
        assert res.get_json()["ok"] is True

    def test_update_user_short_password(self, logged_in_admin):
        logged_in_admin.post("/api/admin/users", json={
            "username": "ShortPw",
            "password": "OldPass123",
            "role": "user",
        })
        res = logged_in_admin.put("/api/admin/users/ShortPw", json={
            "password": "abc",
        })
        assert res.status_code == 400


# =====================================================================
# Calendar API tests
# =====================================================================

class TestCalendar:
    def test_add_event(self, logged_in_admin):
        res = logged_in_admin.post("/api/calendar/events", json={
            "title": "Styrelsemöte",
            "datum": "2026-04-15",
            "time": "14:00",
            "type": "Möte",
        })
        data = res.get_json()
        assert data["ok"] is True
        assert data["event"]["title"] == "Styrelsemöte"

    def test_get_events(self, logged_in_admin):
        logged_in_admin.post("/api/calendar/events", json={
            "title": "Test",
            "datum": "2026-03-15",
        })
        res = logged_in_admin.get("/api/calendar/events?year=2026&month=3")
        data = res.get_json()
        assert len(data) >= 1

    def test_delete_event(self, logged_in_admin):
        res = logged_in_admin.post("/api/calendar/events", json={
            "title": "Delete me",
            "datum": "2026-03-01",
        })
        eid = res.get_json()["event"]["id"]
        logged_in_admin.delete(f"/api/calendar/events/{eid}")
        res = logged_in_admin.get("/api/calendar/events")
        assert all(e["id"] != eid for e in res.get_json())


# =====================================================================
# Todo API tests
# =====================================================================

class TestTodos:
    def test_add_todo(self, logged_in_admin):
        res = logged_in_admin.post("/api/todos", json={
            "task": "Boka möte",
            "priority": "Hög",
            "deadline": "2026-03-10",
        })
        data = res.get_json()
        assert data["ok"] is True
        assert data["todo"]["task"] == "Boka möte"

    def test_update_todo(self, logged_in_admin):
        res = logged_in_admin.post("/api/todos", json={"task": "Fix bug"})
        tid = res.get_json()["todo"]["id"]
        logged_in_admin.put(f"/api/todos/{tid}", json={"done": True})
        res = logged_in_admin.get("/api/todos")
        todo = next(t for t in res.get_json() if t["id"] == tid)
        assert todo["done"] is True or str(todo["done"]).lower() == "true"

    def test_delete_todo(self, logged_in_admin):
        res = logged_in_admin.post("/api/todos", json={"task": "Remove me"})
        tid = res.get_json()["todo"]["id"]
        logged_in_admin.delete(f"/api/todos/{tid}")
        res = logged_in_admin.get("/api/todos")
        assert all(t["id"] != tid for t in res.get_json())


# =====================================================================
# Chat API tests
# =====================================================================

class TestChat:
    def test_create_group(self, logged_in_admin):
        res = logged_in_admin.post("/api/chat/groups", json={
            "name": "Utveckling",
            "members": ["TestAdmin"],
        })
        data = res.get_json()
        assert data["ok"] is True
        assert data["group"]["name"] == "Utveckling"

    def test_send_and_get_messages(self, logged_in_admin):
        group_res = logged_in_admin.post("/api/chat/groups", json={
            "name": "Test",
            "members": ["TestAdmin"],
        })
        gid = group_res.get_json()["group"]["id"]

        logged_in_admin.post(f"/api/chat/groups/{gid}/messages", json={
            "content": "Hej allihopa!",
        })

        res = logged_in_admin.get(f"/api/chat/groups/{gid}/messages")
        msgs = res.get_json()
        assert len(msgs) == 1
        assert msgs[0]["content"] == "Hej allihopa!"
        assert msgs[0]["sender"] == "TestAdmin"


# =====================================================================
# Customer/CRM API tests
# =====================================================================

class TestCRM:
    def test_add_customer(self, logged_in_admin):
        res = logged_in_admin.post("/api/customers", json={
            "name": "Anna Svensson",
            "company": "AB Företag",
            "email": "anna@foretag.se",
            "bolag": "Unithread",
            "stage": "Lead",
        })
        data = res.get_json()
        assert data["ok"] is True
        assert data["customer"]["name"] == "Anna Svensson"

    def test_update_customer_stage(self, logged_in_admin):
        res = logged_in_admin.post("/api/customers", json={
            "name": "Stage Test",
            "bolag": "Unithread",
        })
        cid = res.get_json()["customer"]["id"]
        logged_in_admin.put(f"/api/customers/{cid}/stage", json={"stage": "Vunnen"})
        res = logged_in_admin.get("/api/customers")
        cust = next(c for c in res.get_json() if c["id"] == cid)
        assert cust["stage"] == "Vunnen"

    def test_pipeline(self, logged_in_admin):
        logged_in_admin.post("/api/customers", json={
            "name": "Pipeline Test",
            "bolag": "Unithread",
            "stage": "Lead",
        })
        res = logged_in_admin.get("/api/pipeline")
        data = res.get_json()
        assert "Lead" in data
        assert data["Lead"]["count"] >= 1


# =====================================================================
# Dashboard API tests
# =====================================================================

class TestDashboard:
    def test_dashboard_returns_data(self, logged_in_admin):
        res = logged_in_admin.get("/api/dashboard")
        data = res.get_json()
        assert "summary" in data
        assert "Unithread" in data["summary"]
        assert "Merchoteket" in data["summary"]
        assert "category_breakdown" in data
        assert "monthly_trend" in data
        assert "pending_receipts" in data

    def test_dashboard_unauthenticated(self, client):
        res = client.get("/api/dashboard")
        assert res.status_code == 401


# =====================================================================
# Quote API tests
# =====================================================================

class TestQuotes:
    def test_create_quote(self, logged_in_admin):
        res = logged_in_admin.post("/api/quotes", json={
            "customer_name": "Test Kund",
            "bolag": "Unithread",
            "title": "Webbutveckling",
            "items": [
                {"description": "Design", "quantity": 1, "unit_price": 5000, "moms": 25, "total": 5000},
                {"description": "Utveckling", "quantity": 10, "unit_price": 1000, "moms": 25, "total": 10000},
            ],
        })
        data = res.get_json()
        assert data["ok"] is True
        assert data["quote"]["subtotal"] == 15000

    def test_update_quote_status(self, logged_in_admin):
        res = logged_in_admin.post("/api/quotes", json={
            "customer_name": "Status Test",
            "bolag": "Unithread",
            "title": "Test",
            "items": [],
        })
        qid = res.get_json()["quote"]["id"]
        logged_in_admin.put(f"/api/quotes/{qid}/status", json={"status": "Skickad"})
        res = logged_in_admin.get("/api/quotes")
        quote = next(q for q in res.get_json() if q["id"] == qid)
        assert quote["status"] == "Skickad"


# =====================================================================
# Invoice API tests
# =====================================================================

class TestInvoices:
    def test_create_invoice(self, logged_in_admin):
        res = logged_in_admin.post("/api/invoices", json={
            "customer_name": "Faktura Kund",
            "bolag": "Unithread",
            "title": "Webbutveckling",
            "due_date": "2025-07-15",
            "items": [
                {"description": "Design", "quantity": 1, "unit_price": 5000, "moms": 25, "total": 5000},
            ],
        })
        data = res.get_json()
        assert data["ok"] is True
        assert data["invoice"]["id"].startswith("F-")
        assert data["invoice"]["status"] == "Obetald"
        assert data["invoice"]["total"] == 5000

    def test_list_invoices(self, logged_in_admin):
        logged_in_admin.post("/api/invoices", json={
            "customer_name": "List Test",
            "bolag": "Unithread",
            "title": "Test",
            "items": [],
        })
        res = logged_in_admin.get("/api/invoices")
        data = res.get_json()
        assert len(data) >= 1

    def test_update_invoice_status(self, logged_in_admin):
        res = logged_in_admin.post("/api/invoices", json={
            "customer_name": "Status Test",
            "bolag": "Unithread",
            "title": "Test",
            "items": [],
        })
        iid = res.get_json()["invoice"]["id"]
        logged_in_admin.put(f"/api/invoices/{iid}/status", json={"status": "Betald"})
        res = logged_in_admin.get("/api/invoices")
        inv = next(i for i in res.get_json() if i["id"] == iid)
        assert inv["status"] == "Betald"

    def test_delete_invoice(self, logged_in_admin):
        res = logged_in_admin.post("/api/invoices", json={
            "customer_name": "Delete Test",
            "bolag": "Unithread",
            "title": "Test",
            "items": [],
        })
        iid = res.get_json()["invoice"]["id"]
        res = logged_in_admin.delete(f"/api/invoices/{iid}")
        assert res.get_json()["ok"] is True

    def test_convert_quote_to_invoice(self, logged_in_admin):
        # Create a quote first
        res = logged_in_admin.post("/api/quotes", json={
            "customer_name": "Convert Test",
            "bolag": "Unithread",
            "title": "Offert till faktura",
            "items": [
                {"description": "Tjänst", "quantity": 2, "unit_price": 3000, "moms": 25, "total": 6000},
            ],
        })
        qid = res.get_json()["quote"]["id"]
        # Set to Accepterad
        logged_in_admin.put(f"/api/quotes/{qid}/status", json={"status": "Accepterad"})
        # Convert to invoice
        res = logged_in_admin.post(f"/api/quotes/{qid}/convert-to-invoice")
        data = res.get_json()
        assert data["ok"] is True
        assert data["invoice"]["quote_id"] == qid
        assert data["invoice"]["total"] == 6000
        assert data["invoice"]["customer_name"] == "Convert Test"
        # Quote should be marked as Fakturerad
        res = logged_in_admin.get("/api/quotes")
        quote = next(q for q in res.get_json() if q["id"] == qid)
        assert quote["status"] == "Fakturerad"

    def test_filter_invoices_by_status(self, logged_in_admin):
        logged_in_admin.post("/api/invoices", json={
            "customer_name": "Filter Test",
            "bolag": "Unithread",
            "title": "Test",
            "items": [],
        })
        res = logged_in_admin.get("/api/invoices?status=Obetald")
        data = res.get_json()
        for inv in data:
            assert inv["status"] == "Obetald"


# =====================================================================
# Budget warnings tests
# =====================================================================

class TestBudgetWarnings:
    def test_no_warnings_without_budget(self, logged_in_admin):
        res = logged_in_admin.get("/api/budget/warnings")
        data = res.get_json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_warning_when_over_80_percent(self, logged_in_admin):
        import json as _json
        from datetime import date
        # Set a budget
        logged_in_admin.post("/api/budget", json={
            "bolag": "Unithread",
            "total": 10000,
            "kategorier": {"IT & Programvara": 5000},
        })
        # Add expenses exceeding 80% of category budget (4100 / 5000 = 82%)
        logged_in_admin.post("/api/expenses", json={
            "bolag": "Unithread",
            "datum": date.today().isoformat(),
            "kategori": "IT & Programvara",
            "beskrivning": "Cloud hosting",
            "belopp": 4100,
            "moms_sats": 25,
        })
        res = logged_in_admin.get("/api/budget/warnings")
        data = res.get_json()
        assert len(data) >= 1
        it_warning = next((w for w in data if w["kategori"] == "IT & Programvara"), None)
        assert it_warning is not None
        assert it_warning["level"] == "warning"
        assert it_warning["pct"] >= 80

    def test_danger_when_over_100_percent(self, logged_in_admin):
        from datetime import date
        logged_in_admin.post("/api/budget", json={
            "bolag": "Unithread",
            "total": 5000,
            "kategorier": {"Marknadsföring": 2000},
        })
        logged_in_admin.post("/api/expenses", json={
            "bolag": "Unithread",
            "datum": date.today().isoformat(),
            "kategori": "Marknadsföring",
            "beskrivning": "Ads",
            "belopp": 2500,
            "moms_sats": 25,
        })
        res = logged_in_admin.get("/api/budget/warnings")
        data = res.get_json()
        mkt_warning = next((w for w in data if w["kategori"] == "Marknadsföring"), None)
        assert mkt_warning is not None
        assert mkt_warning["level"] == "danger"
        assert mkt_warning["pct"] >= 100


# =====================================================================
# Dashboard enhanced data tests
# =====================================================================

class TestDashboardEnhanced:
    def test_dashboard_budget_vs_actual(self, logged_in_admin):
        res = logged_in_admin.get("/api/dashboard")
        data = res.get_json()
        assert "budget_vs_actual" in data
        assert "revenue_breakdown" in data

    def test_dashboard_has_monthly_profit_data(self, logged_in_admin):
        res = logged_in_admin.get("/api/dashboard")
        data = res.get_json()
        # Monthly trend should have revenue and expenses for profit calc
        for month in data["monthly_trend"]:
            assert "revenue" in month
            assert "expenses" in month


# =====================================================================
# Integrations API tests
# =====================================================================

class TestIntegrations:
    def test_get_platforms(self, logged_in_admin):
        res = logged_in_admin.get("/api/integrations/platforms")
        data = res.get_json()
        assert len(data) == 6
        platforms = [p["platform"] for p in data]
        assert "shopify" in platforms
        assert "gelato" in platforms
        assert "tiktok_ads" in platforms
        assert "meta_ads" in platforms
        assert "snapchat_ads" in platforms
        assert "google_ads" in platforms

    def test_save_integration(self, logged_in_admin):
        res = logged_in_admin.post("/api/integrations", json={
            "platform": "shopify",
            "bolag": "Unithread",
            "shop_domain": "test-store.myshopify.com",
            "access_token": "shpat_test1234567890",
        })
        data = res.get_json()
        assert data["ok"] is True

    def test_get_integrations_masked(self, logged_in_admin):
        # First save one
        logged_in_admin.post("/api/integrations", json={
            "platform": "meta_ads",
            "bolag": "Unithread",
            "access_token": "EAAG_long_token_here_12345",
            "ad_account_id": "act_123456",
        })
        res = logged_in_admin.get("/api/integrations")
        data = res.get_json()
        assert len(data) >= 1
        meta = next((i for i in data if i["platform"] == "meta_ads"), None)
        assert meta is not None
        # Access token should be masked
        assert "••••" in meta["access_token"]

    def test_delete_integration(self, logged_in_admin):
        # Create then delete
        res = logged_in_admin.post("/api/integrations", json={
            "platform": "gelato",
            "bolag": "Unithread",
            "api_key": "test_gelato_key",
        })
        data = res.get_json()
        # Get the real id from the list
        all_ints = logged_in_admin.get("/api/integrations").get_json()
        gelato = next((i for i in all_ints if i["platform"] == "gelato"), None)
        assert gelato is not None
        res = logged_in_admin.delete(f"/api/integrations/{gelato['id']}")
        assert res.get_json()["ok"] is True

    def test_toggle_integration(self, logged_in_admin):
        logged_in_admin.post("/api/integrations", json={
            "platform": "tiktok_ads",
            "bolag": "Unithread",
            "access_token": "test_token",
            "advertiser_id": "12345",
        })
        all_ints = logged_in_admin.get("/api/integrations").get_json()
        tiktok = next((i for i in all_ints if i["platform"] == "tiktok_ads"), None)
        assert tiktok is not None
        # Toggle off
        res = logged_in_admin.put(f"/api/integrations/{tiktok['id']}/toggle")
        assert res.get_json()["ok"] is True

    def test_integrations_summary(self, logged_in_admin):
        # Add an integration first
        logged_in_admin.post("/api/integrations", json={
            "platform": "google_ads",
            "bolag": "Unithread",
            "developer_token": "test",
            "client_id": "test",
            "client_secret": "test",
            "refresh_token": "test",
            "customer_id": "1234567890",
        })
        res = logged_in_admin.get("/api/integrations/summary")
        data = res.get_json()
        assert isinstance(data, list)

    def test_regular_user_cannot_save_integration(self, logged_in_user):
        res = logged_in_user.post("/api/integrations", json={
            "platform": "shopify",
            "bolag": "Unithread",
        })
        assert res.status_code == 403


# =====================================================================
# Integration adapters unit tests
# =====================================================================

class TestIntegrationAdapters:
    def test_get_all_platforms_metadata(self):
        from integrations import get_all_platforms
        platforms = get_all_platforms()
        assert len(platforms) == 6
        for p in platforms:
            assert "platform" in p
            assert "display_name" in p
            assert "icon" in p
            assert "required_fields" in p
            assert isinstance(p["required_fields"], list)

    def test_create_adapter_shopify(self):
        from integrations import create_adapter
        adapter = create_adapter("shopify", {"shop_domain": "test", "access_token": "abc"})
        assert adapter is not None
        assert adapter.PLATFORM == "shopify"
        assert "myshopify.com" in adapter.shop

    def test_create_adapter_unknown(self):
        from integrations import create_adapter
        adapter = create_adapter("unknown_platform", {})
        assert adapter is None

    def test_adapter_retry_logic(self):
        from integrations import ShopifyAdapter
        adapter = ShopifyAdapter({"shop_domain": "fake", "access_token": "fake"})
        # test_connection should fail gracefully with invalid creds
        result = adapter.test_connection()
        assert result["ok"] is False
        assert "message" in result

    def test_gelato_adapter_has_correct_fields(self):
        from integrations import GelatoAdapter
        assert len(GelatoAdapter.REQUIRED_FIELDS) == 1
        assert GelatoAdapter.REQUIRED_FIELDS[0]["key"] == "api_key"

    def test_google_ads_adapter_strips_dashes(self):
        from integrations import GoogleAdsAdapter
        adapter = GoogleAdsAdapter({
            "developer_token": "x", "client_id": "x",
            "client_secret": "x", "refresh_token": "x",
            "customer_id": "123-456-7890"
        })
        assert adapter.customer_id == "1234567890"


# =====================================================================
# Chat group deletion tests
# =====================================================================

class TestChatDeletion:
    def test_admin_can_delete_group(self, logged_in_admin):
        res = logged_in_admin.post("/api/chat/groups", json={
            "name": "Delete me",
            "members": ["TestAdmin"],
        })
        gid = res.get_json()["group"]["id"]
        # Add a message
        logged_in_admin.post(f"/api/chat/groups/{gid}/messages", json={"content": "Hi"})
        # Delete the group
        res = logged_in_admin.delete(f"/api/chat/groups/{gid}")
        assert res.get_json()["ok"] is True
        # Verify group is gone
        res = logged_in_admin.get("/api/chat/groups")
        assert all(g.get("id") != gid for g in res.get_json())
        # Verify messages are also deleted
        msgs = mock_db.load_data("chat_messages")
        assert all(m.get("group_id") != gid for m in msgs)

    def test_creator_can_delete_own_group(self, logged_in_user):
        res = logged_in_user.post("/api/chat/groups", json={
            "name": "User group",
            "members": ["TestUser"],
        })
        gid = res.get_json()["group"]["id"]
        res = logged_in_user.delete(f"/api/chat/groups/{gid}")
        assert res.get_json()["ok"] is True

    def test_non_creator_cannot_delete(self, client):
        # Set up both users in DB at once
        admin_pw = _hash_password("SecurePass123")
        user_pw = _hash_password("UserPass456")
        mock_db.save_data("users", [
            {"username": "TestAdmin", "password_hash": admin_pw, "role": "admin", "permissions": "[]"},
            {"username": "TestUser", "password_hash": user_pw, "role": "user", "permissions": "[]"},
        ])
        # Admin creates group
        client.post("/api/login", json={"username": "TestAdmin", "password": "SecurePass123"})
        res = client.post("/api/chat/groups", json={
            "name": "Admin group",
            "members": ["TestAdmin", "TestUser"],
        })
        gid = res.get_json()["group"]["id"]
        client.post("/api/logout")
        # Regular user tries to delete
        client.post("/api/login", json={"username": "TestUser", "password": "UserPass456"})
        res = client.delete(f"/api/chat/groups/{gid}")
        assert res.status_code == 403

    def test_delete_nonexistent_group(self, logged_in_admin):
        res = logged_in_admin.delete("/api/chat/groups/nonexistent")
        assert res.status_code == 404


# =====================================================================
# Project management tests
# =====================================================================

class TestProjects:
    def test_create_project(self, logged_in_admin):
        res = logged_in_admin.post("/api/projects", json={
            "name": "Nytt webbprojekt",
            "description": "Bygg en ny hemsida",
            "bolag": "Unithread",
            "members": ["TestAdmin"],
        })
        data = res.get_json()
        assert data["ok"] is True
        assert data["project"]["name"] == "Nytt webbprojekt"
        assert data["project"]["status"] == "Aktivt"

    def test_get_projects(self, logged_in_admin):
        logged_in_admin.post("/api/projects", json={
            "name": "P1",
            "bolag": "Unithread",
            "members": ["TestAdmin"],
        })
        res = logged_in_admin.get("/api/projects")
        projects = res.get_json()
        assert len(projects) == 1
        assert projects[0]["name"] == "P1"

    def test_update_project(self, logged_in_admin):
        res = logged_in_admin.post("/api/projects", json={
            "name": "Old name",
            "bolag": "Unithread",
        })
        pid = res.get_json()["project"]["id"]
        logged_in_admin.put(f"/api/projects/{pid}", json={
            "name": "New name",
            "status": "Pausat",
        })
        res = logged_in_admin.get("/api/projects")
        proj = next(p for p in res.get_json() if p["id"] == pid)
        assert proj["name"] == "New name"
        assert proj["status"] == "Pausat"

    def test_delete_project(self, logged_in_admin):
        res = logged_in_admin.post("/api/projects", json={
            "name": "Delete me",
            "bolag": "Unithread",
        })
        pid = res.get_json()["project"]["id"]
        res = logged_in_admin.delete(f"/api/projects/{pid}")
        assert res.get_json()["ok"] is True
        res = logged_in_admin.get("/api/projects")
        assert all(p.get("id") != pid for p in res.get_json())

    def test_delete_project_permission(self, client):
        # Set up both users in DB at once
        admin_pw = _hash_password("SecurePass123")
        user_pw = _hash_password("UserPass456")
        mock_db.save_data("users", [
            {"username": "TestAdmin", "password_hash": admin_pw, "role": "admin", "permissions": "[]"},
            {"username": "TestUser", "password_hash": user_pw, "role": "user", "permissions": "[]"},
        ])
        # Admin creates project
        client.post("/api/login", json={"username": "TestAdmin", "password": "SecurePass123"})
        res = client.post("/api/projects", json={
            "name": "Admin project",
            "bolag": "Unithread",
            "members": ["TestAdmin", "TestUser"],
        })
        pid = res.get_json()["project"]["id"]
        client.post("/api/logout")
        # Regular user tries to delete
        client.post("/api/login", json={"username": "TestUser", "password": "UserPass456"})
        res = client.delete(f"/api/projects/{pid}")
        assert res.status_code == 403

    def test_creator_auto_added_to_members(self, logged_in_admin):
        res = logged_in_admin.post("/api/projects", json={
            "name": "Auto member",
            "bolag": "Unithread",
            "members": [],
        })
        proj = res.get_json()["project"]
        members = proj["members"]
        if isinstance(members, str):
            members = json.loads(members)
        assert "TestAdmin" in members


# =====================================================================
# Project tasks tests
# =====================================================================

class TestProjectTasks:
    def _create_project(self, client):
        res = client.post("/api/projects", json={
            "name": "Task test project",
            "bolag": "Unithread",
            "members": ["TestAdmin"],
        })
        return res.get_json()["project"]["id"]

    def test_create_task(self, logged_in_admin):
        pid = self._create_project(logged_in_admin)
        res = logged_in_admin.post(f"/api/projects/{pid}/tasks", json={
            "title": "Design mockups",
            "description": "Create wireframes",
            "assigned_to": "TestAdmin",
            "priority": "Hög",
            "deadline": "2026-06-15",
        })
        data = res.get_json()
        assert data["ok"] is True
        assert data["task"]["title"] == "Design mockups"
        assert data["task"]["status"] == "Att göra"

    def test_get_tasks(self, logged_in_admin):
        pid = self._create_project(logged_in_admin)
        logged_in_admin.post(f"/api/projects/{pid}/tasks", json={
            "title": "Task 1",
        })
        logged_in_admin.post(f"/api/projects/{pid}/tasks", json={
            "title": "Task 2",
        })
        res = logged_in_admin.get(f"/api/projects/{pid}/tasks")
        assert len(res.get_json()) == 2

    def test_update_task_status(self, logged_in_admin):
        pid = self._create_project(logged_in_admin)
        res = logged_in_admin.post(f"/api/projects/{pid}/tasks", json={
            "title": "Progress me",
        })
        tid = res.get_json()["task"]["id"]
        logged_in_admin.put(f"/api/projects/{pid}/tasks/{tid}", json={
            "status": "Pågår",
        })
        res = logged_in_admin.get(f"/api/projects/{pid}/tasks")
        task = next(t for t in res.get_json() if t["id"] == tid)
        assert task["status"] == "Pågår"

    def test_delete_task(self, logged_in_admin):
        pid = self._create_project(logged_in_admin)
        res = logged_in_admin.post(f"/api/projects/{pid}/tasks", json={
            "title": "Delete me",
        })
        tid = res.get_json()["task"]["id"]
        logged_in_admin.delete(f"/api/projects/{pid}/tasks/{tid}")
        res = logged_in_admin.get(f"/api/projects/{pid}/tasks")
        assert all(t["id"] != tid for t in res.get_json())

    def test_task_deadline_creates_calendar_event(self, logged_in_admin):
        pid = self._create_project(logged_in_admin)
        res = logged_in_admin.post(f"/api/projects/{pid}/tasks", json={
            "title": "Important deadline",
            "deadline": "2026-07-01",
            "assigned_to": "TestAdmin",
        })
        tid = res.get_json()["task"]["id"]
        # Check calendar events
        events = mock_db.load_data("calendar_events")
        cal_events = [e for e in events if e.get("task_id") == tid]
        assert len(cal_events) == 1
        assert cal_events[0]["type"] == "Projektdeadline"
        assert cal_events[0]["datum"] == "2026-07-01"
        assert "Important deadline" in cal_events[0]["title"]

    def test_delete_task_removes_calendar_event(self, logged_in_admin):
        pid = self._create_project(logged_in_admin)
        res = logged_in_admin.post(f"/api/projects/{pid}/tasks", json={
            "title": "Will be deleted",
            "deadline": "2026-07-15",
        })
        tid = res.get_json()["task"]["id"]
        # Verify event exists
        events = mock_db.load_data("calendar_events")
        assert any(e.get("task_id") == tid for e in events)
        # Delete task
        logged_in_admin.delete(f"/api/projects/{pid}/tasks/{tid}")
        # Verify event is gone
        events = mock_db.load_data("calendar_events")
        assert not any(e.get("task_id") == tid for e in events)


# =====================================================================
# Project files tests
# =====================================================================

class TestProjectFiles:
    def _create_project(self, client):
        res = client.post("/api/projects", json={
            "name": "File test project",
            "bolag": "Unithread",
        })
        return res.get_json()["project"]["id"]

    def test_upload_file(self, logged_in_admin, tmp_path):
        pid = self._create_project(logged_in_admin)
        # Use tmp_path for uploads during tests
        app.config["PROJECT_UPLOAD_FOLDER"] = tmp_path
        data = {
            "files": (io.BytesIO(b"test file content"), "testdoc.pdf"),
        }
        res = logged_in_admin.post(
            f"/api/projects/{pid}/files",
            data=data,
            content_type="multipart/form-data",
        )
        result = res.get_json()
        assert result["ok"] is True
        assert len(result["files"]) == 1
        assert "testdoc" in result["files"][0]["original_name"]

    def test_list_files(self, logged_in_admin, tmp_path):
        pid = self._create_project(logged_in_admin)
        app.config["PROJECT_UPLOAD_FOLDER"] = tmp_path
        data = {"files": (io.BytesIO(b"content"), "note.txt")}
        logged_in_admin.post(
            f"/api/projects/{pid}/files", data=data, content_type="multipart/form-data"
        )
        res = logged_in_admin.get(f"/api/projects/{pid}/files")
        files = res.get_json()
        assert len(files) == 1

    def test_delete_file(self, logged_in_admin, tmp_path):
        pid = self._create_project(logged_in_admin)
        app.config["PROJECT_UPLOAD_FOLDER"] = tmp_path
        data = {"files": (io.BytesIO(b"content"), "remove_me.txt")}
        res = logged_in_admin.post(
            f"/api/projects/{pid}/files", data=data, content_type="multipart/form-data"
        )
        fid = res.get_json()["files"][0]["id"]
        res = logged_in_admin.delete(f"/api/projects/{pid}/files/{fid}")
        assert res.get_json()["ok"] is True
        res = logged_in_admin.get(f"/api/projects/{pid}/files")
        assert len(res.get_json()) == 0
