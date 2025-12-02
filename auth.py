import streamlit as st
import json
import hashlib
from pathlib import Path
from datetime import datetime
import uuid
from db_handler import db

# USERS_FILE = Path(__file__).parent / "foretag_data" / "system_users.json"
# SESSIONS_FILE = Path(__file__).parent / "foretag_data" / "sessions.json"
# ACTIVITY_LOG_FILE = Path(__file__).parent / \
#     "foretag_data" / "aktivitetslogg.json"


@st.cache_data(ttl=300)
def load_users():
    try:
        rows = db.load_data("system_users")
        users = {}
        for row in rows:
            username = row.get("username")
            if username:
                permissions_raw = row.get("permissions", "")
                permissions = []

                if permissions_raw:
                    if isinstance(permissions_raw, str):
                        if permissions_raw.strip().startswith("["):
                            try:
                                permissions = json.loads(permissions_raw)
                            except:
                                permissions = []
                        else:
                            # Handle comma-separated string (legacy/migration format)
                            permissions = [
                                p.strip() for p in permissions_raw.split(",") if p.strip()]
                    elif isinstance(permissions_raw, list):
                        permissions = permissions_raw

                users[username] = {
                    "password_hash": row.get("password_hash"),
                    "role": row.get("role"),
                    "permissions": permissions
                }
        return users
    except Exception:
        return {}


def save_users(users_data):
    rows = []
    for username, data in users_data.items():
        rows.append({
            "username": username,
            "password_hash": data.get("password_hash"),
            "role": data.get("role"),
            "permissions": json.dumps(data.get("permissions", []), ensure_ascii=False)
        })
    try:
        db.save_data("system_users", rows)
        load_users.clear()
    except Exception as e:
        print(f"Error saving users: {e}")


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(username, password):
    users = load_users()
    if username in users:
        return users[username]["password_hash"] == hash_password(password)
    return False


def log_activity(user, action, details):
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": user,
        "action": action,
        "details": details
    }

    try:
        log_data = db.load_data("aktivitetslogg")
        log_data.append(log_entry)
        if len(log_data) > 100:
            log_data = log_data[-100:]
        db.save_data("aktivitetslogg", log_data)
    except Exception as e:
        print(f"Error logging activity: {e}")


def create_user(username, password, role="user", permissions=None):
    load_users.clear()
    users = load_users()
    if username in users:
        return False

    users[username] = {
        "password_hash": hash_password(password),
        "role": role,
        "permissions": permissions or []
    }
    save_users(users)
    return True


def update_password(username, new_password):
    load_users.clear()
    users = load_users()
    if username in users:
        users[username]["password_hash"] = hash_password(new_password)
        save_users(users)
        return True
    return False


@st.cache_data(ttl=300)
def load_sessions():
    try:
        rows = db.load_data("sessions")
        sessions = {}
        for row in rows:
            token = row.get("token")
            if token:
                sessions[token] = {
                    "username": row.get("username"),
                    "expires": float(row.get("expires", 0))
                }
        return sessions
    except Exception:
        return {}


def save_sessions(sessions):
    rows = []
    for token, data in sessions.items():
        rows.append({
            "token": token,
            "username": data.get("username"),
            "expires": data.get("expires")
        })
    try:
        db.save_data("sessions", rows)
        load_sessions.clear()
    except Exception as e:
        print(f"Error saving sessions: {e}")


def create_session(username):
    token = str(uuid.uuid4())
    sessions = load_sessions()
    # Rensa gamla sessioner
    now = datetime.now().timestamp()
    sessions = {k: v for k, v in sessions.items() if v.get("expires", 0) > now}

    # Skapa ny session (giltig i 30 dagar)
    sessions[token] = {
        "username": username,
        "expires": now + (30 * 24 * 3600)
    }
    save_sessions(sessions)
    return token


def validate_session(token):
    sessions = load_sessions()
    if token in sessions:
        session = sessions[token]
        if session.get("expires", 0) > datetime.now().timestamp():
            return session["username"]
    return None


def logout():
    # Ta bort session från fil
    token = st.query_params.get("token")
    if token:
        sessions = load_sessions()
        if token in sessions:
            del sessions[token]
            save_sessions(sessions)

    # Rensa state och params
    st.query_params.clear()
    st.session_state.current_user = None
    st.rerun()


def check_login():
    if "current_user" not in st.session_state:
        st.session_state.current_user = None

    # Försök återställa session från URL-token
    if not st.session_state.current_user:
        token = st.query_params.get("token")
        if token:
            username = validate_session(token)
            if username:
                st.session_state.current_user = username

    # Ensure permissions are loaded if user is logged in
    if st.session_state.current_user:
        if "user_permissions" not in st.session_state:
            users = load_users()
            if st.session_state.current_user in users:
                st.session_state.user_permissions = users[st.session_state.current_user].get(
                    "permissions", [])
            else:
                st.session_state.user_permissions = []
        return st.session_state.current_user

    st.title("🔐 Inloggning")

    with st.form("login_form"):
        username = st.selectbox("Användare", options=list(load_users().keys()))
        password = st.text_input("Lösenord", type="password")
        submitted = st.form_submit_button("Logga in")

        if submitted:
            if verify_password(username, password):
                st.session_state.current_user = username

                # Load permissions immediately
                users = load_users()
                st.session_state.user_permissions = users[username].get(
                    "permissions", [])

                # Skapa session och spara token i URL
                token = create_session(username)
                st.query_params["token"] = token
                st.rerun()
            else:
                st.error("Fel lösenord")

    return None


def has_permission(permission):
    return permission in st.session_state.get("user_permissions", [])
