"""Streamlit chat UI: talks to the FastAPI backend over HTTP."""
import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
AUTH_URL = os.getenv("AUTH_URL", "http://localhost:9999")

ROLES = ("pending", "user", "admin")

if "role" not in st.session_state:
    st.session_state.role = None

st.set_page_config(page_title="Personal Instructor", page_icon="🔋")
st.title("🔋 Personal Instructor — BESS knowledge base")

if "messages" not in st.session_state:
    st.session_state.messages = []      # [{role, content, conversation_id, sources}]
if "token" not in st.session_state:
    st.session_state.token = None


def render_admin() -> None:
    st.header("🛠️ Admin panel")
    tab_upload, tab_users, tab_docs, tab_queue = st.tabs(
        ["Upload", "Users", "Documents", "Review queue"])

    with tab_upload:
        uploaded = st.file_uploader("Upload a document",
                                    type=["pdf", "txt", "md", "csv", "json"])
        if uploaded and st.session_state.get("proposed_file") != uploaded.name:
            with st.spinner("Parsing and extracting metadata..."):
                r = requests.post(f"{API_URL}/admin/upload", headers=auth_headers(),
                                  files={"file": (uploaded.name, uploaded.getvalue())}, timeout=120)
            if r.ok:
                st.session_state.proposed = r.json()
                st.session_state.proposed_file = uploaded.name
            else:
                st.error(r.json().get("detail", "Upload failed"))
        if st.session_state.get("proposed"):
            p = st.session_state.proposed
            st.caption(f"Review the metadata for **{p['filename']}**, then ingest:")
            with st.form("ingest_form"):
                title = st.text_input("Title", p["title"])
                authors = st.text_input("Authors", p["authors"])
                year = st.text_input("Year", str(p["year"] or ""))
                source_url = st.text_input("Source URL", "")
                if st.form_submit_button("Ingest into knowledge base"):
                    body = {"filename": p["filename"], "title": title, "authors": authors,
                            "year": int(year) if year.strip().isdigit() else None,
                            "source_url": source_url}
                    with st.spinner("Chunking, embedding, loading..."):
                        ing = requests.post(f"{API_URL}/admin/ingest", headers=auth_headers(),
                                            json=body, timeout=300)
                    if ing.ok:
                        st.success(f"Ingested (paper_id={ing.json()['paper_id']}).")
                        st.session_state.proposed = None
                        st.session_state.proposed_file = None
                    else:
                        st.error(ing.json().get("detail", "Ingest failed"))

    with tab_users:
        users = requests.get(f"{API_URL}/admin/users", headers=auth_headers(), timeout=10).json()
        for u in users:
            c1, c2 = st.columns([3, 2])
            c1.write(f"{u['email']}  ·  **{u['role']}**")
            if u["user_id"] == st.session_state.get("user_id"):
                c2.caption("you")                      # no dropdown for yourself
                continue
            new_role = c2.selectbox("role", ROLES, index=ROLES.index(u["role"]),
                                    key=f"role_{u['user_id']}", label_visibility="collapsed")
            if new_role != u["role"]:
                requests.post(f"{API_URL}/admin/users/{u['user_id']}/role",
                              json={"role": new_role}, headers=auth_headers(), timeout=10)
                st.rerun()

    with tab_docs:
        docs = requests.get(f"{API_URL}/admin/documents", headers=auth_headers(), timeout=10).json()
        for d in docs:
            with st.expander(f"{d['title'][:70]}  ·  {d['chunks']} chunks"):
                with st.form(f"doc_{d['id']}"):
                    title = st.text_input("Title", d["title"], key=f"t_{d['id']}")
                    authors = st.text_input("Authors", d["authors"], key=f"a_{d['id']}")
                    year = st.text_input("Year", str(d["year"] or ""), key=f"y_{d['id']}")
                    source_url = st.text_input("Source URL", d["source_url"], key=f"u_{d['id']}")
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("💾 Save"):
                        requests.put(f"{API_URL}/admin/documents/{d['id']}", headers=auth_headers(),
                                     json={"title": title, "authors": authors,
                                           "year": int(year) if year.strip().isdigit() else None,
                                           "source_url": source_url}, timeout=10)
                        st.rerun()
                    if c2.form_submit_button("🗑️ Delete"):
                        requests.delete(f"{API_URL}/admin/documents/{d['id']}",
                                        headers=auth_headers(), timeout=10)
                        st.rerun()

    with tab_queue:
        items = requests.get(f"{API_URL}/admin/unanswered", headers=auth_headers(), timeout=10).json()
        if not items:
            st.info("No pending questions.")
        for it in items:
            with st.expander(f"[{it['status']}] {it['question'][:70]}"):
                ans = st.text_area("Answer", value=it.get("human_answer") or "", key=f"ans_{it['id']}")
                if st.button("Answer & integrate into KB", key=f"int_{it['id']}"):
                    requests.post(f"{API_URL}/admin/unanswered/{it['id']}/integrate",
                                  json={"answer": ans}, headers=auth_headers(), timeout=30)
                    st.success("Integrated — the agent will answer this from now on.")
                    st.rerun()


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
        st.session_state.role = None
        st.session_state.messages = []
        st.rerun()

if st.session_state.role is None:
    me = requests.get(f"{API_URL}/me", headers=auth_headers(), timeout=10)
    if me.ok:
        st.session_state.role = me.json().get("role")
        st.session_state.user_id = me.json().get("user_id")
    else:
        st.session_state.role = "pending"

views = ["💬 Chat"] + (["🛠️ Admin"] if st.session_state.role == "admin" else [])
view = st.sidebar.radio("View", views)

if view == "🛠️ Admin":
    render_admin()
    st.stop()          # admin view shown; skip the chat code below

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

