# Copilot Instructions for Företagsekonomi Project

## Project Overview
This is a Streamlit-based financial management and receipt tracking system designed for small businesses (specifically "Unithread" and "Merchoteket"). It handles bookkeeping, receipts, budgeting, and calendar events.

## Architecture & Data Flow
- **Framework**: Streamlit (Python).
- **Data Persistence**: JSON-based flat files. No SQL database is used.
  - Primary data location: `foretag_data/` directory.
  - Key data files: `utgifter.json`, `intakter.json`, `kvitton.json`, `kalender.json`.
- **File Storage**: 
  - Receipts and documents are stored locally in `foretag_data/filer/` or `kvitto_bilder/`.
  - Supports Images (PIL) and PDFs (PyMuPDF/fitz).

## Key Components
- **`foretags_ekonomi.py`**: The main application entry point for business economics. Handles expenses, revenue, and budgeting.
- **`kvitto_app.py`**: Dedicated application for receipt management and user expenses.
- **`foretag_data/`**: Contains all persistent state (JSON) and uploaded files.

## Coding Conventions
- **Language**: The codebase uses **Swedish** for variable names, function names, UI labels, and comments (e.g., `load_expenses`, `spara_kvitto`, `intakter`).
- **Path Handling**: Always use `pathlib.Path` for file system operations. Avoid string manipulation for paths.
  - Example: `DATA_DIR = Path(__file__).parent / "foretag_data"`
- **Data Loading/Saving**: 
  - Use dedicated `load_*` and `save_*` functions for each data type.
  - Always specify `encoding='utf-8'` and `ensure_ascii=False` when working with JSON to support Swedish characters.
- **Visualization**: Use **Plotly Express** (`px`) or **Plotly Graph Objects** (`go`) for charts.
- **Authentication**: Simple session-state based admin authentication (`check_admin_password`).

## Critical Workflows
- **Running the App**: 
  - Run via Streamlit: `streamlit run foretags_ekonomi.py` or `streamlit run kvitto_app.py`.
- **Dependency Management**: Standard Python libraries + `streamlit`, `pandas`, `plotly`, `Pillow`, `pymupdf`.

## Specific Patterns
- **Session State**: Heavily relies on `st.session_state` for managing user sessions and admin login status.
- **Error Handling**: Use `st.error()` to display user-facing errors and `st.success()` for confirmation.
