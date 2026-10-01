import sqlite3
import streamlit as st
from services.paths import DB_PATH

_DB_PATH = str(DB_PATH)


@st.cache_resource
def _open_connection(db_path: str) -> sqlite3.Connection:
    # One shared connection per database file, reused across Streamlit reruns.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _get_connection() -> sqlite3.Connection:
    # Reads _DB_PATH at call time, so tests can point it at a temporary file.
    return _open_connection(_DB_PATH)


def init_db() -> None:
    conn = _get_connection()
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exercises (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL REFERENCES users(id),
                exercise_name TEXT    NOT NULL,
                reps          INTEGER NOT NULL DEFAULT 0,
                sets          INTEGER NOT NULL DEFAULT 0,
                time          INTEGER NOT NULL DEFAULT 0,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def get_user(username: str):
    conn = _get_connection()
    return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def create_user(username: str):
    conn = _get_connection()
    with conn:
        conn.execute("INSERT INTO users (username) VALUES (?)", (username,))
    return get_user(username)


def get_or_create_user(username: str):
    user = get_user(username)
    if user is None:
        user = create_user(username)
    return user


def add_exercise(user_id, exercise_name, reps, sets, time):
    conn = _get_connection()
    with conn:
        existing = conn.execute(
            """
            SELECT * FROM exercises
            WHERE user_id = ? AND exercise_name = ? AND Date(created_at) = Date('now')
            """,
            (user_id, exercise_name),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE exercises SET reps = reps + ?, sets = sets + ?, time = time + ? WHERE id = ?",
                (reps, sets, time, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO exercises (user_id, exercise_name, sets, reps, time) VALUES (?, ?, ?, ?, ?)",
                (user_id, exercise_name, sets, reps, time),
            )


def get_users_exercises(user_id):
    conn = _get_connection()
    return conn.execute("SELECT * FROM exercises WHERE user_id = ?", (user_id,)).fetchall()
