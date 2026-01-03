# Copilot Instructions for Unithread App

## Project Overview
Multi-tenant Streamlit app for small business financial management, receipt tracking, budgeting, and team communication. Three entry points:
- **`main.py`**: Primary dashboard with expenses, revenue, budgeting, chat, and calendar (modern)
- **`kvitto_app.py`**: Receipt/expense management with image/PDF support (standalone)
- **`foretags_ekonomi.py`**: Legacy economics view (transitioning to main.py)

## Architecture & Data Flow
**Hybrid Persistence**: JSON files locally + Google Sheets/Drive backend
- **Local dev**: JSON files in `foretag_data/` (`utgifter.json`, `intakter.json`, `kvitton.json`, `kalender.json`, `chatt.json`)
- **Cloud prod**: `db_handler.py` syncs to Google Sheets via `gspread` + file uploads to Google Drive
- **Migration**: `migrate_to_cloud.py` moves JSON→Sheets with pandas-based data cleaning (handles NaN/Infinity issues)
- **Auth**: `service_account.json` (local) or `st.secrets["gcp_service_account"]` (production)

File storage: `foretag_data/filer/` with subdirs for `kvitton/` (receipts), `bokforing/` (accounting), `kalender_filer/` (calendar).

## Code Conventions
- **Swedish-only naming**: `utgifter`, `intakter`, `ladda_`, `spara_`, all UI labels in Swedish
- **Pathlib mandatory**: `Path(__file__).parent / "foretag_data"` - never string path concatenation
- **JSON + UTF-8 required**: Always `encoding='utf-8', ensure_ascii=False` for å/ä/ö characters
- **Session state for state**: `st.session_state.admin_logged_in`, `active_chat_id`, `current_user` control flow
- **Class-based managers**: `UserManager`, `ChatManager`, `RoleControl` (main.py lines 570-730) encapsulate data operations

## Multi-Tenant Pattern
Fixed businesses: `["Unithread", "Merchoteket"]`. Data structure keys transactions by `bolag`:
```python
{"Unithread": {"utgifter": [...], "total": 5000}, "Merchoteket": {...}}
```
`UserManager.add_user()` sets role (admin/user) and permissions list per user.

## Key Dev Workflows
- **`streamlit run main.py`** – Primary app with chat, calendar, admin panel
- **`streamlit run kvitto_app.py`** – Receipts-only view with image/PDF handling
- **`python migrate_to_cloud.py`** – Migrate JSON to Google Sheets (cleans NaN/Inf with pandas)
- **`python init_budget.py` / `migrate_budget.py`** – Separate tooling for budget fixes

## Critical Patterns
1. **Business isolation**: All load/save check `BUSINESSES` list; no shared data across orgs
2. **Google API resilience**: `db_handler._retry_api_call()` retries 3x on network failure (500/502/503/timeout)
3. **File uploads**: `db.upload_file()` returns webViewLink for Drive files; local fallback in dev
4. **Visualization**: Plotly Express (`px`) + custom CSS for gradients, cards, animations
5. **Auth layering**: `auth.check_login()` at app start; session state + role-based access control in `RoleControl`

## Common Edits
- **Add expense/revenue category**: Edit list in `main.py` line ~580 (`EXPENSE_CATEGORIES`, `REVENUE_CATEGORIES`)
- **User management**: Use `main.py` admin panel UI or call `UserManager` methods directly
- **Receipt upload**: `st.file_uploader()` → `save_receipt_image()` → `db.upload_file()` for cloud sync
- **Chat**: Managed by `ChatManager` class; persisted in `chatt.json` / Google Sheets `chatt` worksheet
