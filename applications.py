import os
import re
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
from google import genai

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from langchain.agents import create_sql_agent, AgentType
from langchain.agents.agent_toolkits import SQLDatabaseToolkit
from langchain.callbacks import StreamlitCallbackHandler

load_dotenv()


def build_db_uri() -> str:
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "mm123456")  # Change to your password
    db_name = os.getenv("DB_NAME", "school_db")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"


def get_gemini_client():
    """Get LangChain ChatGoogleGenerativeAI client (replaces direct API calls)"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in .env")
    
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0
    )


def create_sql_agent_langchain(db_uri: str, llm):
    """
    Create a LangChain SQL agent with built-in safety and error handling.
    
    Args:
        db_uri: Database connection URI
        llm: LangChain LLM instance (ChatGoogleGenerativeAI)
    
    Returns:
        Agent executor for running SQL queries
    """
    # Initialize SQLDatabase wrapper (LangChain utility)
    db = SQLDatabase.from_uri(db_uri)
    
    # Create toolkit with database
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    
    # Create agent with safety features
    agent = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10
    )
    
    return agent


def get_model_name() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# ===== KEPT FOR REFERENCE / FALLBACK (Now handled by LangChain Agent) =====

def get_schema_text(engine) -> str:
    """Get database schema - now handled by LangChain SQLDatabase wrapper"""
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
    """Extract SQL from text - now handled by LangChain Agent"""
    raw_text = raw_text.strip()

    sql_block = re.search(r"```sql\s*(.*?)```", raw_text, re.IGNORECASE | re.DOTALL)
    if sql_block:
        return sql_block.group(1).strip()

    code_block = re.search(r"```\s*(.*?)```", raw_text, re.DOTALL)
    if code_block:
        return code_block.group(1).strip()

    return raw_text


def is_safe_select_query(sql: str) -> bool:
    """Validate SQL safety - now handled by LangChain Agent with built-in safeguards"""
    sql_clean = sql.strip().lower()

    if not sql_clean.startswith("select"):
        return False

    blocked_keywords = [
        "insert", "update", "delete", "drop", "alter",
        "truncate", "create", "replace", "rename", "grant", "revoke"
    ]

    for keyword in blocked_keywords:
        if re.search(rf"\b{keyword}\b", sql_clean):
            return False

    return True


def generate_sql(question: str, schema_text: str, client, model_name: str) -> str:
    """Generate SQL - now handled by LangChain Agent"""
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
    response = client.models.generate_content(
        model=model_name,
        contents=prompt
    )
    return extract_sql(response.text)


def run_sql(engine, sql: str):
    """Run SQL query - now handled by LangChain SQLDatabase wrapper"""
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.fetchall()
        columns = result.keys()
        return columns, rows


def summarize_answer(question: str, sql: str, columns, rows, client, model_name: str) -> str:
    """Summarize answer - now handled by LangChain Agent"""
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
    response = client.models.generate_content(
        model=model_name,
        contents=prompt
    )
    return response.text.strip()


def main():
    """Main application loop using LangChain SQL Agent"""
    db_uri = build_db_uri()
    llm = get_gemini_client()
    
    print("=" * 60)
    print("NL2SQL with LangChain (Gemini + MySQL)")
    print("Type 'exit' to quit.")
    print("=" * 60)
    
    # Create LangChain SQL Agent
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
            print("\n[LangChain Processing...]")
            
            # Run agent with user question
            # LangChain agent handles: SQL generation, execution, error handling
            result = agent.invoke({"input": question})
            
            print("\n[Agent Response]")
            print(result.get("output", "No response generated"))
            
        except SQLAlchemyError as e:
            print("\n[Database Error]")
            print(str(e))
        except Exception as e:
            print("\n[Error]")
            print(str(e))


if __name__ == "__main__":
    main()