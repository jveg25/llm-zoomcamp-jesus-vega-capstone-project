"""Streamlit chat UI: talks to the FastAPI backend over HTTP."""
import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Personal Instructor", page_icon="🔋")
st.title("🔋 Personal Instructor — BESS knowledge base")

if "messages" not in st.session_state:
    st.session_state.messages = []      # [{role, content, conversation_id, sources}]

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
                          timeout=10)
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


for msg in st.session_state.messages:
    render_message(msg)

if question := st.chat_input("Ask about battery energy storage systems..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"), st.spinner("Searching the papers..."):
        resp = requests.post(f"{API_URL}/ask", json={"question": question}, timeout=60)
        resp.raise_for_status()
        data = resp.json()

    st.session_state.messages.append({
        "role": "assistant",
        "content": data["answer"],
        "conversation_id": data["conversation_id"],
        "sources": data["sources"],
    })
    st.rerun()      # re-run so the new message renders through the same path as history

