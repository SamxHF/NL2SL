import os

import streamlit as st
from sqlalchemy import create_engine, text

from applications import build_db_uri, create_sql_agent_langchain, get_gemini_client


st.set_page_config(page_title="NSL2 Dashboard", page_icon="🧭", layout="wide")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background: radial-gradient(circle at 8% 2%, #e0f2fe 0%, #f0f9ff 42%, #f8fafc 100%);
            }

            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
                border-right: 1px solid rgba(148, 163, 184, 0.25);
            }

            [data-testid="stSidebar"] * {
                color: #000000;
            }

            .stApp, .stApp * {
                color: #000000;
            }

            .hero-wrap {
                border: 1px solid #bae6fd;
                border-radius: 18px;
                padding: 16px 18px;
                background: linear-gradient(120deg, #ffffff 0%, #f8fafc 55%, #f0f9ff 100%);
                box-shadow: 0 8px 22px rgba(14, 116, 144, 0.10);
                margin-bottom: 10px;
            }

            .hero-row {
                display: flex;
                align-items: center;
                gap: 14px;
            }

            .hero-title {
                margin: 0;
                font-size: 1.55rem;
                font-weight: 800;
                letter-spacing: 0.2px;
                color: #000000 !important;
                line-height: 1.1;
                text-shadow: none;
            }

            .hero-sub {
                margin: 2px 0 0 0;
                color: #000000 !important;
                font-size: 0.94rem;
                font-weight: 600;
            }

            .status-wrap {
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
                margin: 8px 0 14px 0;
            }

            .status-pill {
                border-radius: 999px;
                padding: 6px 10px;
                font-size: 0.82rem;
                border: 1px solid #7dd3fc;
                background: #fff;
                color: #000000;
            }

            .stChatMessage {
                border-radius: 14px;
                border: 1px solid #cbd5e1;
                background: rgba(255, 255, 255, 0.86);
                box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
            }

            .stButton > button {
                border-radius: 10px;
                border: 1px solid #93c5fd;
                background: linear-gradient(90deg, #0ea5e9 0%, #06b6d4 100%);
                color: #ffffff;
                font-weight: 600;
            }

            .stButton > button:hover {
                border-color: #38bdf8;
                background: linear-gradient(90deg, #0284c7 0%, #0891b2 100%);
            }

            .stChatInputContainer {
                border-top: 1px solid #cbd5e1;
                background: rgba(248, 250, 252, 0.95);
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_logo_header() -> None:
    st.markdown(
        f"""
        <div class="hero-wrap">
            <div class="hero-row">
                <div>
                    <h1 class="hero-title">NSL2 Dashboard</h1>
                    <p class="hero-sub">Natural language to SQL for your course database with a cleaner chat experience.</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def check_db_connection(db_uri: str) -> tuple[bool, str]:
    try:
        engine = create_engine(db_uri)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Connected"
    except Exception as exc:  # pragma: no cover
        return False, str(exc)


@st.cache_resource(show_spinner=False)
def init_agent():
    db_uri = build_db_uri()
    llm = get_gemini_client()
    agent = create_sql_agent_langchain(db_uri, llm)
    return db_uri, agent


def get_config_warnings() -> list[str]:
    warnings = []
    if not os.getenv("GEMINI_API_KEY"):
        warnings.append("GEMINI_API_KEY is missing in .env")

    db_password = os.getenv("DB_PASSWORD", "")
    if not db_password or db_password == "YOUR_PASSWORD_FOR_MYSQL":
        warnings.append("DB_PASSWORD is not configured yet")

    return warnings


def run_query(question: str) -> str:
    _, agent = init_agent()
    response = agent.invoke({"input": question.strip()})
    return response.get("output", "No response generated")


def main() -> None:
    inject_styles()
    render_logo_header()

    with st.sidebar:
        st.subheader("Control Panel")
        st.write("Model:", "gemini-2.5-flash")
        st.write("Mode:", "Read-only queries")

        config_warnings = get_config_warnings()
        if config_warnings:
            st.warning("Configuration is incomplete")
            for item in config_warnings:
                st.write(f"- {item}")
        else:
            st.success("Configuration looks good")

        if st.button("Reload Agent"):
            init_agent.clear()
            st.rerun()

        if st.button("Clear Chat"):
            st.session_state.messages = []
            st.rerun()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    db_uri = build_db_uri()
    ok, status = check_db_connection(db_uri)
    db_state = "DB: Online" if ok else "DB: Offline"
    db_tone = "Connected" if ok else "Unavailable"
    st.markdown(
        f"""
        <div class="status-wrap">
            <span class="status-pill">{db_state}</span>
            <span class="status-pill">Model: Gemini 2.5 Flash</span>
            <span class="status-pill">Safety: Read-only</span>
            <span class="status-pill">Status: {db_tone}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not ok:
        st.info("Database is currently unavailable. You can still chat, but query execution will fail until DB is up.")
        with st.expander("Connection details"):
            st.code(status)

    if not st.session_state.messages:
        st.markdown("Try one of these:")
        ex1, ex2, ex3 = st.columns(3)
        if ex1.button("List all courses"):
            st.session_state.pending_prompt = "List all courses"
        if ex2.button("Students not enrolled"):
            st.session_state.pending_prompt = "Which students are not enrolled in any course?"
        if ex3.button("Enrollments per course"):
            st.session_state.pending_prompt = "How many students are enrolled in each course?"

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    pending = st.session_state.pop("pending_prompt", None) if "pending_prompt" in st.session_state else None
    question = pending or st.chat_input("Ask a database question...")

    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    output = run_query(question)
                except Exception as exc:
                    output = f"Query failed: {exc}"
            st.markdown(output)

        st.session_state.messages.append({"role": "assistant", "content": output})


if __name__ == "__main__":
    main()