# NL2SL - Natural Language to SQL Assistant

A LangChain-powered system that converts natural language questions into SQL queries and executes them on a MySQL database.

## 📋 Project Information

**Course:** COSC 444 – Database Systems (Khalifa University)  
**Semester:** Spring 2026  
**Deadline:** 6/4/2026  
**Project Type:** Mini Project  
**Group Size:** 2-4 students

---

## 🎯 Objective

Build a system that allows users to ask questions in natural language, which are then translated into SQL queries, executed on a MySQL database, and presented as readable results.

### Key Features:
- ✅ Natural language input processing
- ✅ AI-powered SQL generation using Google Gemini + LangChain
- ✅ MySQL database integration
- ✅ Read-only query execution (safety first)
- ✅ Multi-table query support (SELECT, JOIN, GROUP BY)
- ✅ Comprehensive error handling
- ✅ Transparent SQL query display

---

## 🗂️ Project Structure

```
NL2SL/
├── README.md                 # Project overview
├── applications.py           # Main application code
├── .env                       # Environment variables (git-ignored)
├── .gitignore                # Git ignore rules
├── schema/                   # Database schema files
│   └── schema.sql            # Database creation script
├── tests/                    # Test cases and validation
└── venv/                     # Virtual environment (git-ignored)
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- MySQL Server running locally
- Virtual environment (venv)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd NL2SL
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   Create a `.env` file with:
   ```
   GEMINI_API_KEY=your_api_key_here
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=your_mysql_password
   DB_NAME=school_db
   GEMINI_MODEL=gemini-2.5-flash
   ```

5. **Set up the database**
   ```bash
   mysql -u root -p < schema/schema.sql
   ```

6. **Run the CLI application**
   ```bash
   python3 applications.py
   ```

7. **Run the dashboard (recommended)**
   ```bash
   streamlit run dashboard.py
   ```

---

## 📚 Database Schema

### Core Entities (Required)
- **Students:** Student information with enrollment tracking
- **Teachers:** Faculty information
- **Courses:** Course offerings
- **Enrollments:** Student-Course relationships

### Optional Extensions
- departments
- classrooms
- attendance
- assignments
- student_clubs

---

## 🔍 Supported Query Types

The system must handle at least:

### 1. Simple Lookup
```
Question: "List all courses."
Type: Single-table SELECT with WHERE clause
```

### 2. Join Query
```
Question: "Which students take Database Systems?"
Type: INNER JOIN across multiple tables
```

### 3. Aggregation
```
Question: "How many students are enrolled in each course?"
Type: GROUP BY with COUNT aggregation
```

---

## 🛡️ Safety Features

- ✅ **Read-Only Enforcement:** System blocks INSERT, UPDATE, DELETE, DROP, ALTER
- ✅ **Input Validation:** Validates and sanitizes all natural language input
- ✅ **SQL Inspection:** All generated SQL is visible to users before execution
- ✅ **Error Handling:** Graceful management of failures instead of crashing

---

## ⚙️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Language** | Python 3.9+ |
| **LLM Framework** | LangChain |
| **LLM Model** | Google Gemini 2.5 Flash |
| **Database** | MySQL 8.0+ |
| **ORM** | SQLAlchemy |
| **MySQL Driver** | PyMySQL |
| **Configuration** | python-dotenv |


---

## 🧪 Testing

The project includes comprehensive testing with:
- Simple lookup queries
- Join queries
- Aggregation queries
- Error/edge cases

---

## 📝 Example Usage

```python
# Question: "How many students are enrolled?"
# Generated SQL: SELECT COUNT(*) FROM enrollments;
# Result: 45
# Response: "There are 45 students enrolled in total."
```

---

## ✅ Evaluation Criteria

- **Database Design (20%):** Normalization, keys, relationships
- **SQL Integration (20%):** MySQL integration, multi-table queries
- **LangChain Functionality (25%):** NLP to SQL conversion, answer quality
- **Error Handling (10%):** Robust failure management
- **Demonstration (10%):** Clear presentation of functionality
- **Report (15%):** Documentation completeness and clarity

---

## 📧 Notes

- Generated SQL is always displayed to the user for transparency
- Database access uses minimal required permissions (read-only)
- All configuration is managed through `.env` file (not committed to Git)
- Virtual environment is excluded from version control

---

**Last Updated:** April 2, 2026
