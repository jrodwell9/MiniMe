import json
import sqlite3


def create_mock_sqlite_db(db_path):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("DROP TABLE IF EXISTS sessions")
        cursor.execute("DROP TABLE IF EXISTS steps")

        cursor.execute("""
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                timestamp TEXT,
                model_routed TEXT,
                final_status TEXT
            )""")
        cursor.execute("""
            CREATE TABLE steps (
                step_number INTEGER,
                session_id TEXT,
                tool_name TEXT,
                tool_input TEXT,
                observation TEXT,
                is_error INTEGER,
                latency_ms REAL,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )""")

        # Insert a mock session
        cursor.execute(
            "INSERT INTO sessions (session_id, timestamp, model_routed, final_status) VALUES (?, ?, ?, ?)",
            ("mock-sqlite-session-1", "2026-08-31T12:00:00Z", "claude-3-opus", "success"),
        )

        # Insert mock steps for the session
        cursor.execute(
            "INSERT INTO steps (step_number, session_id, tool_name, tool_input, observation, is_error, latency_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                "mock-sqlite-session-1",
                "Bash",
                json.dumps({"command": "echo hello from sqlite"}),
                "hello from sqlite",
                0,
                100.0,
            ),
        )
        cursor.execute(
            "INSERT INTO steps (step_number, session_id, tool_name, tool_input, observation, is_error, latency_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                2,
                "mock-sqlite-session-1",
                "Read",
                json.dumps({"file_path": "db_file.txt"}),
                "db file content",
                0,
                50.0,
            ),
        )

        conn.commit()
        print(f"Mock SQLite DB created at {db_path}")
    except sqlite3.Error as e:
        print(f"Error creating mock SQLite DB: {e}")
    finally:
        if conn:
            conn.close()
