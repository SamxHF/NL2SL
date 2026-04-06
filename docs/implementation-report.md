# Implementation: SQL Functionality, LangChain Workflow, and Error Handling

This section supports the formal project report requirements for **implemented SQL-related functionalities**, **the LangChain workflow**, and **errors handled by the group**.

---

## 1. Implemented SQL-related functionalities

### 1.1 Database connectivity

- The application connects to **MySQL** using **SQLAlchemy** with the **PyMySQL** driver (`mysql+pymysql://…`).
- Connection parameters (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`) are loaded from environment variables via `python-dotenv`, so credentials are not hard-coded for deployment.

### 1.2 Natural language to SQL execution

- User questions are passed to a **LangChain SQL agent** that:
  - Inspects the live schema through LangChain’s `SQLDatabase` wrapper.
  - Generates **MySQL-compatible SQL** using **Google Gemini** (`ChatGoogleGenerativeAI`, default model `gemini-2.5-flash`, `temperature=0` for deterministic SQL).
  - Executes queries through the toolkit’s query tool, which ultimately calls `SQLDatabase.run()`.

### 1.3 Read-only enforcement (safety)

Safety is implemented in **two layers**:

1. **Prompt-level:** A custom agent prefix (`AGENT_PREFIX`) instructs the model to produce only **SELECT**-style read queries and to refuse data-modification requests.
2. **Application-level:** `SQLDatabase.run` is wrapped so that every executed statement is checked by `is_read_only_query()`. Only statements that start with safe prefixes (`SELECT`, `SHOW`, `DESCRIBE` / `DESC`, `EXPLAIN`) and do **not** contain dangerous keywords (e.g. `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, …) are passed to MySQL. Otherwise the run returns a **blocked** message instead of executing the query.

This aligns with the project requirement to restrict execution to **read-only** behavior and to document that model-generated SQL is inherently risky.

### 1.4 Transparency (generated SQL visible)

- The agent is created with `return_intermediate_steps=True`.
- After each run, the last executed `sql_db_query` tool call is extracted with `extract_sql_from_steps()` and shown in the **Streamlit** UI as **“Generated SQL”** in a code block, so users can verify what ran against the database.

### 1.5 Supported query patterns (course database)

The agent can answer questions that map to:

- **Simple lookups** (single-table `SELECT`).
- **Joins** across related tables (e.g. students, courses, enrollments).
- **Aggregations** (`GROUP BY`, `COUNT`, etc.), as long as they remain read-only.

The Streamlit dashboard also ships **example prompts** aligned with the minimum coverage (list courses, unenrolled students, enrollments per course).

### 1.6 Conversation context (follow-up questions)

- The dashboard maintains chat history in Streamlit session state.
- Before each new question, up to the **last five Q&A turns** are summarized and prepended as context so follow-up questions (e.g. “same but only for CS courses”) can be interpreted without repeating the full prior question.

### 1.7 CLI vs web UI

- **`applications.py`:** Interactive CLI; prints agent output and, when available, the last generated SQL from intermediate steps.
- **`dashboard.py`:** Primary demo UI with chat, SQL display, DB status, and configuration warnings.

---

## 2. LangChain workflow

**Step-by-step:**

1. **Input:** The user’s question (optionally prefixed with recent dialogue) is passed as `input` to the agent executor’s `invoke`.
2. **LLM:** `ChatGoogleGenerativeAI` decides which toolkit tool to call next (e.g. list tables, get schema, run a query).
3. **Tools:** `SQLDatabaseToolkit` exposes LangChain’s standard SQL tools bound to our `SQLDatabase` instance.
4. **Execution:** When the agent issues `sql_db_query`, the SQL string is validated by `is_read_only_query` inside the wrapped `db.run` before MySQL runs it.
5. **Loop:** The agent may iterate (up to `max_iterations=10`) until it can answer from query results. Parsing issues can be retried via `handle_parsing_errors=True`.
6. **Output:** The executor returns:
   - **`output`:** Final answer string for the user.
   - **`intermediate_steps`:** Pairs of (tool action, observation) used to recover the **last executed SQL** for the UI.

---

## 3. Errors handled by the group

| Situation | Handling |
|-----------|----------|
| **Missing API key** | `get_gemini_client()` raises if `GEMINI_API_KEY` is unset; the dashboard surfaces configuration warnings in the sidebar when env vars are incomplete. |
| **Gemini rate limits / quota** | `format_query_error()` detects HTTP 429, `RESOURCE_EXHAUSTED`, and similar messages and returns a short, user-friendly explanation with optional retry timing parsed from the error text. |
| **Unsafe or non–read-only SQL** | Blocked at `db.run` before execution; the observation returned to the agent indicates the query was not permitted (read-only policy). |
| **Agent / LLM parsing errors** | `handle_parsing_errors=True` on the SQL agent reduces hard failures when the model’s tool call format is wrong. |
| **Database unreachable** | `check_db_connection()` runs `SELECT 1` on startup; the UI shows offline status, connection details in an expander, and informs the user that queries will fail until MySQL is available. |
| **Generic exceptions during `invoke`** | Wrapped in `format_query_error` where applicable, or the raw message is shown so the app does not crash silently. |
| **CLI database errors** | `SQLAlchemyError` is caught separately in the CLI loop and printed as a database error. |

**Note:** Some edge cases (e.g. empty result sets, hallucinated table names) are partially addressed indirectly: empty results still flow back as normal observations, and schema tools reduce wrong-table mistakes. The group can document additional test cases in the **testing record** as required by the project brief.

---

## 4. File map (for the report)

| File | Role |
|------|------|
| `applications.py` | DB URI, Gemini client, read-only `SQLDatabase` wrapper, `create_sql_agent`, SQL extraction, error formatting, CLI entry point. |
| `dashboard.py` | Streamlit UI, context window (last 5 turns), SQL display, DB health and config warnings. |

---

*You can paste this document into your report as-is or split sections under “Implementation details” and “LangChain design.”*
