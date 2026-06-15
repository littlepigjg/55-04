import sqlite3
import os
from pathlib import Path
from typing import Optional


class _MemorySafeConnection:
    def __init__(self, conn, is_memory):
        self._conn = conn
        self._is_memory = is_memory

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._conn.__exit__(exc_type, exc_val, exc_tb)
        if not self._is_memory:
            self._conn.close()
        return False


class DatabaseConnection:
    _instance = None

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    def __new__(cls, db_path: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        if not cls._instance._initialized or (db_path and db_path != cls._instance.db_path):
            cls._instance._init(db_path)
        return cls._instance

    def _init(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(Path.home(), ".ebook_reader_tracker", "reading.db")
        self.db_path = db_path
        if db_path != ':memory:':
            Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
        self._persistent_conn = None
        self._create_tables()
        self._initialized = True

    def connect(self):
        is_memory = self.db_path == ':memory:'
        if is_memory:
            if self._persistent_conn is None:
                self._persistent_conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self._persistent_conn.row_factory = sqlite3.Row
            return _MemorySafeConnection(self._persistent_conn, True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return _MemorySafeConnection(conn, False)

    def _create_tables(self):
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.executescript("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                title TEXT,
                author TEXT,
                file_format TEXT,
                total_pages INTEGER,
                total_words INTEGER,
                total_chapters INTEGER,
                date_added TEXT,
                last_read TEXT,
                status TEXT DEFAULT 'not_started'
            );

            CREATE TABLE IF NOT EXISTS reading_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                file_format TEXT NOT NULL,
                chapter TEXT,
                chapter_index INTEGER,
                paragraph_id TEXT,
                paragraph_index INTEGER,
                page_number INTEGER,
                page_x REAL,
                page_y REAL,
                percentage REAL,
                word_count INTEGER DEFAULT 0,
                last_updated TEXT,
                mobi_record_index INTEGER,
                mobi_byte_position INTEGER,
                mobi_content_hash TEXT,
                FOREIGN KEY (book_id) REFERENCES books (id)
            );

            CREATE TABLE IF NOT EXISTS reading_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds INTEGER DEFAULT 0,
                effective_duration INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 0,
                pages_read INTEGER DEFAULT 0,
                words_read INTEGER DEFAULT 0,
                FOREIGN KEY (book_id) REFERENCES books (id)
            );

            CREATE TABLE IF NOT EXISTS reading_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                position_data TEXT,
                FOREIGN KEY (session_id) REFERENCES reading_sessions (id)
            );

            CREATE TABLE IF NOT EXISTS reading_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_type TEXT NOT NULL,
                target_value INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                description TEXT,
                created_at TEXT,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS book_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                pages_read INTEGER DEFAULT 0,
                minutes_read INTEGER DEFAULT 0,
                words_read INTEGER DEFAULT 0,
                UNIQUE(book_id, date),
                FOREIGN KEY (book_id) REFERENCES books (id)
            );

            CREATE TABLE IF NOT EXISTS activity_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                details TEXT
            );
        """)
            conn.commit()
            self._migrate(conn)

    def _migrate(self, conn):
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(reading_positions)")
            columns = {row[1] for row in cursor.fetchall()}
            if 'mobi_record_index' not in columns:
                cursor.execute("ALTER TABLE reading_positions ADD COLUMN mobi_record_index INTEGER")
            if 'mobi_byte_position' not in columns:
                cursor.execute("ALTER TABLE reading_positions ADD COLUMN mobi_byte_position INTEGER")
            if 'mobi_content_hash' not in columns:
                cursor.execute("ALTER TABLE reading_positions ADD COLUMN mobi_content_hash TEXT")
            conn.commit()
        except Exception:
            pass
