import os
import re
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit

load_dotenv()


AGENT_PREFIX = (
    "You are a MySQL database assistant for a school database.\n"
    "Given an input question, create a syntactically correct MySQL query to run, "
    "then look at the results of the query and return the answer.\n\n"
    "CRITICAL SAFETY RULES:\n"
    "- You must ONLY generate SELECT queries.\n"
    "- NEVER use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, "
    "REPLACE, RENAME, GRANT, or REVOKE.\n"
    "- If a user asks to modify data, refuse and explain this is read-only.\n\n"
    "Always include the exact SQL query you executed in your final answer "
    "so the user can verify it."
)


def build_db_uri() -> str:
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "mm123456")
    db_name = os.getenv("DB_NAME", "school_db")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"


def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in .env")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0,
    )


def is_read_only_query(sql: str) -> bool:
    """Return True only when *sql* is a safe, non-mutating statement."""
    sql_clean = sql.strip().lower()
    safe_starts = ("select", "show", "describe", "desc", "explain")
    if not any(sql_clean.startswith(p) for p in safe_starts):
        return False
    dangerous = [
        "insert", "update", "delete", "drop", "alter",
        "truncate", "create", "replace", "rename", "grant", "revoke",
    ]
    for kw in dangerous:
        if re.search(rf"\b{kw}\b", sql_clean):
            return False
    return True


def create_sql_agent_langchain(db_uri: str, llm):
    """Create a LangChain SQL agent with read-only enforcement and
    intermediate-step capture so the generated SQL is visible."""
    db = SQLDatabase.from_uri(db_uri)

    _original_run = db.run

    def _safe_run(command: str, *args, **kwargs):
        if not is_read_only_query(command):
            return "BLOCKED: Only read-only SELECT queries are permitted on this database."
        return _original_run(command, *args, **kwargs)

    db.run = _safe_run

    toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    agent = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5,
        prefix=AGENT_PREFIX,
        agent_executor_kwargs={"return_intermediate_steps": True},
    )
    return agent


def extract_sql_from_steps(steps: list) -> list[str]:
    """Pull executed SQL statements from LangChain agent intermediate steps."""
    queries = []
    for action, _observation in steps:
        if action.tool == "sql_db_query":
            inp = action.tool_input
            if isinstance(inp, dict):
                inp = inp.get("query", str(inp))
            queries.append(str(inp).strip())
    return queries


def extract_last_query_result_from_steps(steps: list) -> str | None:
    """Return the observation from the last sql_db_query tool call."""
    for action, observation in reversed(steps):
        if action.tool == "sql_db_query":
            return str(observation).strip()
    return None


def format_query_error(exc: Exception) -> str:
    """Convert LLM / database failures into short user-facing messages."""
    code = getattr(exc, "code", None)
    status = str(getattr(exc, "status", "")).upper()
    message = str(exc)
    upper_message = message.upper()

    if code == 429 or status == "RESOURCE_EXHAUSTED" or "RESOURCE_EXHAUSTED" in upper_message:
        retry_match = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s", message, re.IGNORECASE)
        retry_text = " in a few seconds"
        if retry_match:
            retry_seconds = retry_match.group(1)
            retry_text = f" in about {retry_seconds} seconds"
        return (
            "Gemini quota is temporarily exhausted. "
            f"Please try again{retry_text}, or switch to a different API key/model if this keeps happening."
        )

    return message


def get_model_name() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# ===== Reference helpers (kept for report / fallback; not used by the agent) =====

def get_schema_text(engine) -> str:
    schema_sql = """
    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
    ORDER BY TABLE_NAME, ORDINAL_POSITION
    """
    with engine.connect() as conn:
        rows = conn.execute(text(schema_sql)).fetchall()

    grouped = {}
    for table_name, column_name, data_type in rows:
        grouped.setdefault(table_name, []).append(f"{column_name} ({data_type})")

    parts = []
    for table, cols in grouped.items():
        parts.append(f"Table: {table}\nColumns: " + ", ".join(cols))
    return "\n\n".join(parts)


def extract_sql(raw_text: str) -> str:
    raw_text = raw_text.strip()
    sql_block = re.search(r"```sql\s*(.*?)```", raw_text, re.IGNORECASE | re.DOTALL)
    if sql_block:
        return sql_block.group(1).strip()
    code_block = re.search(r"```\s*(.*?)```", raw_text, re.DOTALL)
    if code_block:
        return code_block.group(1).strip()
    return raw_text


def generate_sql(question: str, schema_text: str, client, model_name: str) -> str:
    prompt = f"""
You are a MySQL SQL assistant.

Generate exactly ONE valid MySQL SELECT query for the user question.

Rules:
1. Only output SQL.
2. Only generate a read-only SELECT statement.
3. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or other destructive statements.
4. Use only the tables and columns that appear in the schema below.
5. If the question cannot be answered using this schema, output exactly:
NOT_ANSWERABLE

Database schema:
{schema_text}

User question:
{question}
"""
    response = client.models.generate_content(model=model_name, contents=prompt)
    return extract_sql(response.text)


def run_sql(engine, sql: str):
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.fetchall()
        columns = result.keys()
        return columns, rows


def summarize_answer(question: str, sql: str, columns, rows, client, model_name: str) -> str:
    prompt = f"""
You are a helpful database course teaching assistant.

Given the user question, SQL, and SQL result, write a short plain-English answer.

Question:
{question}

SQL:
{sql}

Columns:
{list(columns)}

Rows:
{rows}
"""
    response = client.models.generate_content(model=model_name, contents=prompt)
    return response.text.strip()


# ===== CLI entry point =====

def main():
    db_uri = build_db_uri()
    llm = get_gemini_client()

    print("=" * 60)
    print("NL2SQL Starter (Gemini + MySQL)")
    print("Type 'exit' to quit.")
    print("=" * 60)

    print("\n[Initializing LangChain SQL Agent...]")
    try:
        agent = create_sql_agent_langchain(db_uri, llm)
        print("[Agent Ready]\n")
    except Exception as e:
        print(f"[Error initializing agent] {str(e)}")
        return

    while True:
        question = input("\nEnter your question: ").strip()

        if question.lower() == "exit":
            print("Bye.")
            break

        if not question:
            print("Please enter a question.")
            continue

        try:
            result = agent.invoke({"input": question})

            steps = result.get("intermediate_steps", [])
            queries = extract_sql_from_steps(steps)
            query_result = extract_last_query_result_from_steps(steps)
            if queries:
                print(f"\n[Generated SQL]\n{queries[-1]}")
            if query_result:
                print(f"\n[Query Result]\n{query_result}")

            print(f"\n[Final Answer]")
            print(result.get("output", "No response generated"))

        except SQLAlchemyError as e:
            print("\n[Database Error]")
            print(str(e))
        except Exception as e:
            print("\n[Error]")
            print(format_query_error(e))


if __name__ == "__main__":
    main()
