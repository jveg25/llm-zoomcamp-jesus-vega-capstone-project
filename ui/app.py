"""Streamlit chat UI: talks to the FastAPI backend over HTTP."""
import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
AUTH_URL = os.getenv("AUTH_URL", "http://localhost:9999")

st.set_page_config(page_title="Personal Instructor", page_icon="🔋")
st.title("🔋 Personal Instructor — BESS knowledge base")

if "messages" not in st.session_state:
    st.session_state.messages = []      # [{role, content, conversation_id, sources}]
if "token" not in st.session_state:
    st.session_state.token = None

def auth_headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}


def login(email: str, password: str) -> bool:
    r = requests.post(f"{AUTH_URL}/token?grant_type=password",
                      json={"email": email, "password": password}, timeout=10)
    if r.ok:
        st.session_state.token = r.json()["access_token"]
        return True
    return False


def signup(email: str, password: str) -> bool:
    r = requests.post(f"{AUTH_URL}/signup",
                      json={"email": email, "password": password}, timeout=10)
    return r.ok


def auth_gate() -> None:
    """Render login/signup forms, then stop the script until a token exists."""
    st.subheader("Sign in")
    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])
    with tab_login, st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Log in"):
            if login(email, password):
                st.rerun()
            else:
                st.error("Invalid email or password.")
    with tab_signup, st.form("signup_form"):
        email = st.text_input("Email", key="su_email")
        password = st.text_input("Password", type="password", key="su_pw")
        if st.form_submit_button("Create account"):
            if signup(email, password):
                st.success("Account created. Log in — access needs admin approval.")
            else:
                st.error("Sign-up failed (email may already be registered).")
    st.stop()



def feedback_buttons(conversation_id: int) -> None:
    voted_key = f"voted_{conversation_id}"
    if st.session_state.get(voted_key):
        st.caption(f"Feedback: {'👍' if st.session_state[voted_key] == 1 else '👎'}")
        return
    col_up, col_down, _ = st.columns([1, 1, 8])
    for col, value, icon in [(col_up, 1, "👍"), (col_down, -1, "👎")]:
        if col.button(icon, key=f"fb_{conversation_id}_{value}"):
            requests.post(f"{API_URL}/feedback",
                          json={"conversation_id": conversation_id, "value": value},
                          headers=auth_headers(), timeout=10)
            st.session_state[voted_key] = value
            st.rerun()

def render_message(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("Sources"):
                for s in msg["sources"]:
                    st.markdown(f"- **{s['title']}** — {s['section'] or 'n/a'}")
        if msg["role"] == "assistant" and msg.get("conversation_id"):
            feedback_buttons(msg["conversation_id"])


if not st.session_state.token:
    auth_gate()      # st.stop() inside: nothing below renders when logged out

with st.sidebar:
    if st.button("Log out"):
        st.session_state.token = None
        st.session_state.messages = []
        st.rerun()

for msg in st.session_state.messages:
    render_message(msg)

if question := st.chat_input("Ask about battery energy storage systems..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"), st.spinner("Searching the papers..."):
        resp = requests.post(f"{API_URL}/ask", json={"question": question},
                             headers=auth_headers(), timeout=60)
        if resp.status_code == 401:                 # token expired (1h TTL)
            st.session_state.token = None
            st.warning("Session expired — please log in again.")
            st.rerun()
        if resp.status_code == 403:                 # pending user
            st.warning("Your access is pending admin approval.")
            st.stop()
        resp.raise_for_status()
        data = resp.json()

    st.session_state.messages.append({
        "role": "assistant",
        "content": data["answer"],
        "conversation_id": data["conversation_id"],
        "sources": data["sources"],
    })
    st.rerun()      # re-run so the new message renders through the same path as history

