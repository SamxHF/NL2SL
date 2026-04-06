import os

import streamlit as st
from sqlalchemy import create_engine, text

from applications import (
    build_db_uri,
    create_sql_agent_langchain,
    extract_last_query_result_from_steps,
    extract_sql_from_steps,
    format_query_error,
    get_gemini_client,
)


st.set_page_config(page_title="NL2SQL Assistant", page_icon="🗃️", layout="wide")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

            .stApp {
                background: #f8f9fc;
                font-family: 'Inter', sans-serif;
            }

            /* ── Sidebar ── */
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
                border-right: 1px solid rgba(148, 163, 184, 0.15);
            }
            [data-testid="stSidebar"] * {
                color: #e2e8f0 !important;
            }
            [data-testid="stSidebar"] .stButton > button {
                width: 100%;
                border-radius: 8px;
                border: 1px solid rgba(148, 163, 184, 0.25);
                background: rgba(255,255,255,0.06);
                color: #e2e8f0 !important;
                font-weight: 600;
                padding: 0.5rem 1rem;
                transition: background 0.2s;
            }
            [data-testid="stSidebar"] .stButton > button:hover {
                background: rgba(255,255,255,0.12);
                border-color: rgba(148, 163, 184, 0.4);
            }
            [data-testid="stSidebar"] hr {
                border-color: rgba(148, 163, 184, 0.2) !important;
            }

            /* ── Hero banner ── */
            .hero {
                background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0c4a6e 100%);
                border-radius: 16px;
                padding: 2rem 2.25rem;
                margin-bottom: 1.25rem;
                position: relative;
                overflow: hidden;
            }
            .hero::before {
                content: '';
                position: absolute;
                top: -40%; right: -10%;
                width: 320px; height: 320px;
                background: radial-gradient(circle, rgba(56,189,248,0.15) 0%, transparent 70%);
                border-radius: 50%;
            }
            .hero-title {
                margin: 0;
                font-size: 1.75rem;
                font-weight: 800;
                color: #ffffff !important;
                letter-spacing: -0.3px;
                line-height: 1.2;
            }
            .hero-title span {
                background: linear-gradient(90deg, #38bdf8, #818cf8);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .hero-sub {
                margin: 0.35rem 0 0 0;
                color: #94a3b8 !important;
                font-size: 0.95rem;
                font-weight: 400;
                line-height: 1.5;
            }

            /* ── Status bar ── */
            .status-bar {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                margin-bottom: 1.25rem;
            }
            .pill {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                border-radius: 999px;
                padding: 5px 14px;
                font-size: 0.8rem;
                font-weight: 600;
                border: 1px solid #e2e8f0;
                background: #ffffff;
                color: #475569;
            }
            .pill .dot {
                width: 7px; height: 7px;
                border-radius: 50%;
                display: inline-block;
            }
            .pill .dot.green  { background: #22c55e; box-shadow: 0 0 6px rgba(34,197,94,0.45); }
            .pill .dot.red    { background: #ef4444; box-shadow: 0 0 6px rgba(239,68,68,0.4); }
            .pill .dot.blue   { background: #3b82f6; box-shadow: 0 0 6px rgba(59,130,246,0.35); }
            .pill .dot.amber  { background: #f59e0b; box-shadow: 0 0 6px rgba(245,158,11,0.35); }

            /* ── Welcome / example cards ── */
            .welcome-section {
                text-align: center;
                padding: 2.5rem 1rem 1rem;
            }
            .welcome-icon {
                font-size: 2.5rem;
                margin-bottom: 0.5rem;
            }
            .welcome-heading {
                font-size: 1.2rem;
                font-weight: 700;
                color: #1e293b !important;
                margin: 0 0 0.25rem;
            }
            .welcome-text {
                color: #64748b !important;
                font-size: 0.9rem;
                margin: 0 0 1.75rem;
            }

            /* ── Chat messages ── */
            .stChatMessage {
                border-radius: 14px;
                border: 1px solid #e2e8f0;
                background: #ffffff;
                box-shadow: 0 1px 4px rgba(15,23,42,0.04);
            }

            /* ── Main-area buttons ── */
            .stApp > section > div .stButton > button {
                border-radius: 10px;
                border: 1px solid #c7d2fe;
                background: linear-gradient(135deg, #6366f1 0%, #818cf8 100%);
                color: #ffffff !important;
                font-weight: 600;
                padding: 0.45rem 1rem;
                transition: opacity 0.2s;
            }
            .stApp > section > div .stButton > button:hover {
                opacity: 0.9;
            }

            /* ── Chat input ── */
            .stChatInputContainer {
                border-top: 1px solid #e2e8f0;
                background: rgba(248,250,252,0.95);
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <div class="hero">
            <h1 class="hero-title">🗃️ NL2SQL <span>Assistant</span></h1>
            <p class="hero-sub">Ask questions in plain English — get instant SQL results from your course database.</p>
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
    except Exception as exc:
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


def run_query(question: str) -> dict:
    """Run a question through the agent.
    Returns {"answer": str, "sql": str | None, "execution_result": str | None}.
    """
    _, agent = init_agent()
    try:
        response = agent.invoke({"input": question.strip()})
        answer = response.get("output", "No response generated")
        steps = response.get("intermediate_steps", [])
        queries = extract_sql_from_steps(steps) if steps else []
        execution_result = extract_last_query_result_from_steps(steps) if steps else None
        return {
            "answer": answer,
            "sql": queries[-1] if queries else None,
            "execution_result": execution_result,
        }
    except Exception as exc:
        return {"answer": format_query_error(exc), "sql": None, "execution_result": None}


def render_assistant_message(msg: dict) -> None:
    """Render an assistant message, showing the SQL block when available."""
    if msg.get("sql"):
        st.caption("Generated SQL")
        st.code(msg["sql"], language="sql")
    if msg.get("execution_result"):
        st.caption("Execution Result")
        st.code(msg["execution_result"], language=None)
    st.markdown(msg["content"])


EXAMPLES = [
    {"icon": "📋", "title": "List all courses", "desc": "Show every course in the catalog", "prompt": "List all courses"},
    {"icon": "🔍", "title": "Unenrolled students", "desc": "Find students not in any course", "prompt": "Which students are not enrolled in any course?"},
    {"icon": "📊", "title": "Enrollments per course", "desc": "Count students in each course", "prompt": "How many students are enrolled in each course?"},
]


def main() -> None:
    inject_styles()
    render_hero()

    # ── Sidebar ──
    with st.sidebar:
        st.markdown("#### ⚙️ Control Panel")
        st.caption("Model")
        st.code("gemini-2.5-flash", language=None)
        st.caption("Query Mode")
        st.code("Read-only (SELECT only)", language=None)
        st.divider()

        config_warnings = get_config_warnings()
        if config_warnings:
            st.warning("Configuration incomplete")
            for item in config_warnings:
                st.markdown(f"- {item}")
        else:
            st.success("All systems configured")

        st.divider()
        if st.button("🔄  Reload Agent"):
            init_agent.clear()
            st.rerun()
        if st.button("🗑️  Clear Chat"):
            st.session_state.messages = []
            st.rerun()

    # ── Status bar ──
    db_uri = build_db_uri()
    ok, status = check_db_connection(db_uri)
    db_dot = "green" if ok else "red"
    db_label = "Database Online" if ok else "Database Offline"
    st.markdown(
        f"""
        <div class="status-bar">
            <span class="pill"><span class="dot {db_dot}"></span>{db_label}</span>
            <span class="pill"><span class="dot blue"></span>Gemini 2.5 Flash</span>
            <span class="pill"><span class="dot green"></span>Read-only Mode</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not ok:
        st.info("Database is currently unavailable. You can still chat, but queries will fail until the DB is up.")
        with st.expander("Connection details"):
            st.code(status)

    # ── Session state ──
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # ── Welcome screen with example cards ──
    if not st.session_state.messages:
        st.markdown(
            """
            <div class="welcome-section">
                <div class="welcome-icon">💬</div>
                <p class="welcome-heading">What would you like to know?</p>
                <p class="welcome-text">Ask any question about your database in plain English, or try one of these examples:</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        cols = st.columns(len(EXAMPLES))
        for col, ex in zip(cols, EXAMPLES):
            with col:
                if st.button(f"{ex['icon']}  {ex['title']}", key=ex["title"], use_container_width=True):
                    st.session_state.pending_prompt = ex["prompt"]
                    st.rerun()

    # ── Chat history ──
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                render_assistant_message(msg)
            else:
                st.markdown(msg["content"])

    # ── Input handling ──
    pending = st.session_state.pop("pending_prompt", None) if "pending_prompt" in st.session_state else None
    question = pending or st.chat_input("Ask a question about your database…")

    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Querying…"):
                result = run_query(question)
            if result["sql"]:
                st.caption("Generated SQL")
                st.code(result["sql"], language="sql")
            if result["execution_result"]:
                st.caption("Execution Result")
                st.code(result["execution_result"], language=None)
            st.markdown(result["answer"])

        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
            "sql": result["sql"],
            "execution_result": result["execution_result"],
        })


if __name__ == "__main__":
    main()
