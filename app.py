"""
Streamlit front-end for the LangGraph coding agent.
Run with:  uv run streamlit run app.py
"""
from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from src.agent import build_agent  # noqa: E402
from src.config import (  # noqa: E402
    GOOGLE_API_KEY,
    GROQ_API_KEY,
    WORKSPACE_DIR,
    list_google_models,
    list_groq_models,
)

MAX_TOOL_CALL_RETRIES = 2  # extra attempts after the first, for malformed tool-call glitches

st.set_page_config(page_title="Coding Agent", page_icon="🛠️", layout="wide")

# --------------------------------------------------------------------------
# Styling
# --------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp { background-color: #0e1117; }
    .main-title {
        font-size: 2.1rem; font-weight: 800;
        background: linear-gradient(90deg, #6ee7b7 0%, #60a5fa 60%, #a78bfa 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .subtitle { color: #9ca3af; font-size: 0.95rem; margin-top: -6px; }
    .tool-badge {
        display: inline-block; padding: 2px 10px; border-radius: 999px;
        background: #1f2937; color: #93c5fd; font-size: 0.75rem;
        border: 1px solid #374151; margin-right: 6px;
    }
    section[data-testid="stSidebar"] { border-right: 1px solid #262730; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<p class="main-title">🛠️ Coding Agent</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">Writes, runs, and fixes code in a sandboxed workspace — powered by LangGraph.</p>',
    unsafe_allow_html=True,
)
st.write("")

# --------------------------------------------------------------------------
# Sidebar: provider / model / settings
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Settings")

    provider = st.radio("LLM provider", ["Groq", "Google"], horizontal=True)

    key_ok = GROQ_API_KEY if provider == "Groq" else GOOGLE_API_KEY
    if key_ok:
        st.success(f"{provider} API key detected", icon="✅")
    else:
        st.error(
            f"No {provider} API key found. Add it to your .env file "
            f"as {'GROQ_API_KEY' if provider == 'Groq' else 'GOOGLE_API_KEY'}.",
            icon="⚠️",
        )

    @st.cache_data(ttl=600, show_spinner=False)
    def _models(provider_name: str):
        return list_groq_models() if provider_name == "Groq" else list_google_models()

    model_options = _models(provider)
    default_index = 0
    model = st.selectbox("Model", model_options, index=default_index)

    temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.05)

    st.divider()
    if st.button("🧹 New conversation", use_container_width=True):
        st.session_state.pop("messages", None)
        st.session_state["thread_id"] = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.subheader("📁 Workspace")
    LANG_BY_EXT = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".json": "json", ".md": "markdown", ".html": "html",
        ".css": "css", ".sh": "bash", ".yaml": "yaml", ".yml": "yaml",
    }
    files = sorted(p for p in WORKSPACE_DIR.rglob("*") if p.is_file())
    if files:
        for f in files:
            rel = f.relative_to(WORKSPACE_DIR)
            with st.expander(str(rel), expanded=False):
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    content = "(binary file)"
                st.code(content[:5000], language=LANG_BY_EXT.get(f.suffix, "text"))
                st.download_button(
                    "Download", content, file_name=rel.name, key=f"dl_{rel}"
                )
    else:
        st.caption("No files yet — ask the agent to create some!")

# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = str(uuid.uuid4())


def _is_malformed_tool_call_error(e: Exception) -> bool:
    """True for the transient Groq/Llama glitch where the model emits a
    badly-formed tool-call block (e.g. tool name and JSON args run
    together). Safe to retry — a fresh generation usually succeeds."""
    text = str(e).lower()
    return "tool_use_failed" in text or "tool call validation failed" in text

# --------------------------------------------------------------------------
# Render chat history
# --------------------------------------------------------------------------
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                with st.expander(f"🔧 {tc['name']}({tc['args']})", expanded=False):
                    st.code(tc["result"], language="text")
        st.markdown(msg["content"])

# --------------------------------------------------------------------------
# Chat input + agent run
# --------------------------------------------------------------------------
user_input = st.chat_input("Ask the agent to write, explain, or fix code…")

if user_input:
    if not key_ok:
        st.error(f"Please set your {provider} API key in .env before chatting.")
        st.stop()

    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        status_placeholder = st.empty()
        tool_calls_log = []
        final_text = ""
        agent = None
        config = {"configurable": {"thread_id": st.session_state["thread_id"]}}

        for attempt in range(MAX_TOOL_CALL_RETRIES + 1):
            tool_calls_log = []
            final_text = ""
            try:
                if agent is None:
                    agent = build_agent(provider, model, temperature)

                # First attempt sends the new human message; retries resume
                # the same thread from its last good checkpoint instead of
                # resending the message (which would duplicate it).
                run_input = (
                    {"messages": [HumanMessage(content=user_input)]}
                    if attempt == 0
                    else None
                )

                with st.spinner("Thinking…" if attempt == 0 else "Retrying…"):
                    for step in agent.stream(
                        run_input, config=config, stream_mode="values"
                    ):
                        last_msg = step["messages"][-1]

                        if isinstance(last_msg, AIMessage):
                            if last_msg.content:
                                final_text = last_msg.content
                                placeholder.markdown(final_text)
                            if last_msg.tool_calls:
                                for tc in last_msg.tool_calls:
                                    st.markdown(
                                        f'<span class="tool-badge">🔧 calling {tc["name"]}</span>',
                                        unsafe_allow_html=True,
                                    )

                        elif isinstance(last_msg, ToolMessage):
                            entry = {
                                "name": last_msg.name,
                                "args": "",
                                "result": str(last_msg.content),
                            }
                            tool_calls_log.append(entry)
                            with st.expander(f"🔧 {last_msg.name} result", expanded=False):
                                st.code(str(last_msg.content), language="text")

                if not final_text:
                    final_text = "_(no text response — see tool results above)_"
                placeholder.markdown(final_text)
                status_placeholder.empty()
                break  # success

            except Exception as e:
                if _is_malformed_tool_call_error(e) and attempt < MAX_TOOL_CALL_RETRIES:
                    status_placeholder.warning(
                        f"⚠️ The model sent a malformed tool call (attempt {attempt + 1}/"
                        f"{MAX_TOOL_CALL_RETRIES + 1}) — retrying automatically…"
                    )
                    time.sleep(1.0)
                    continue
                final_text = f"❌ Error: {e}"
                placeholder.error(final_text)
                status_placeholder.empty()
                break

    st.session_state["messages"].append(
        {"role": "assistant", "content": final_text, "tool_calls": tool_calls_log}
    )
    st.rerun()