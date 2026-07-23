# services/db.py
from __future__ import annotations

import os
import sqlite3
import logging
from contextlib import contextmanager
from typing import Optional, Union

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_TYPE = os.getenv("DB_TYPE", "").strip().lower()

# If DB_TYPE is not set, infer it from DATABASE_URL
if not DB_TYPE:
    if DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://"):
        DB_TYPE = "postgres"
    else:
        DB_TYPE = "sqlite"

# ---------------------------------------------------------------------
# PostgreSQL pool
# ---------------------------------------------------------------------
_pg_pool = None

if DB_TYPE == "postgres":
    try:
        import psycopg2
        from psycopg2.pool import SimpleConnectionPool
    except Exception as exc:
        raise RuntimeError(
            "psycopg2 is required for PostgreSQL. Install it with: pip install psycopg2-binary"
        ) from exc

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing for PostgreSQL")

    # Lazy-created pool so the app can import cleanly.
    def _get_pg_pool():
        global _pg_pool
        if _pg_pool is None:
            _pg_pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=DATABASE_URL,
            )
        return _pg_pool


# ---------------------------------------------------------------------
# SQLite fallback (optional, useful for local dev)
# ---------------------------------------------------------------------
SQLITE_PATH = os.getenv("SQLITE_PATH", "veyra.db").strip()


def _get_sqlite_connection():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def get_db_connection():
    """
    Returns a database connection for either PostgreSQL or SQLite.
    PostgreSQL is preferred for Render deployment.
    """
    if DB_TYPE == "postgres":
        pool = _get_pg_pool()
        conn = pool.getconn()
        return conn

    return _get_sqlite_connection()


def release_db_connection(conn) -> None:
    """
    Returns a PostgreSQL connection back to the pool.
    Closes SQLite connections.
    """
    if conn is None:
        return

    if DB_TYPE == "postgres":
        try:
            pool = _get_pg_pool()
            pool.putconn(conn)
        except Exception:
            logger.exception("Failed to release PostgreSQL connection")
    else:
        try:
            conn.close()
        except Exception:
            logger.exception("Failed to close SQLite connection")


@contextmanager
def db_cursor():
    """
    Optional helper:
        with db_cursor() as cur:
            cur.execute(...)
    """
    conn = get_db_connection()
    cur = None
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        release_db_connection(conn)


def init_db():
    """
    Create only the minimal tables needed for the new upload-first pipeline.

    IMPORTANT:
    - This does NOT recreate your old document/AI tables.
    - It only ensures `users` exists if you are starting fresh locally,
      and creates `uploaded_files` for the upload pipeline.
    """
    conn = get_db_connection()
    cur = None
    try:
        cur = conn.cursor()

        if DB_TYPE == "postgres":
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS uploaded_files (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    original_filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    file_url TEXT NOT NULL,
                    content_type TEXT,
                    file_size BIGINT,
                    upload_status TEXT DEFAULT 'uploaded',
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_uploaded_files_user_id
                ON uploaded_files(user_id)
                """
            )

        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS uploaded_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    original_filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    file_url TEXT NOT NULL,
                    content_type TEXT,
                    file_size INTEGER,
                    upload_status TEXT DEFAULT 'uploaded',
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_uploaded_files_user_id
                ON uploaded_files(user_id)
                """
            )

        conn.commit()
        logger.info("Database initialized successfully")

    except Exception:
        conn.rollback()
        logger.exception("Failed to initialize database")
        raise

    finally:
        if cur is not None:
            cur.close()
        release_db_connection(conn)