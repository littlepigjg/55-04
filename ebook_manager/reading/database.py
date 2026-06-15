import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict, field


@dataclass
class ReadingPosition:
    book_id: int
    file_path: str
    file_format: str
    chapter: Optional[str] = None
    chapter_index: Optional[int] = None
    paragraph_id: Optional[str] = None
    paragraph_index: Optional[int] = None
    page_number: Optional[int] = None
    page_x: Optional[float] = None
    page_y: Optional[float] = None
    percentage: Optional[float] = None
    word_count: int = 0
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ReadingSession:
    book_id: int
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: int = 0
    effective_duration: int = 0
    is_active: int = 0
    pages_read: int = 0
    words_read: int = 0


@dataclass
class ReadingGoal:
    goal_type: str
    target_value: int
    start_date: str
    end_date: str
    description: str = ""
    id: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    is_active: int = 1


class ReadingDatabase:
    _instance = None

    def __new__(cls, db_path: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init(db_path)
        return cls._instance

    def _init(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(Path.home(), ".ebook_reader_tracker", "reading.db")
        self.db_path = db_path
        Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
        self._create_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
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
                )
            """)

            cursor.execute("""
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
                    FOREIGN KEY (book_id) REFERENCES books (id)
                )
            """)

            cursor.execute("""
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
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reading_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    book_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    position_data TEXT,
                    FOREIGN KEY (session_id) REFERENCES reading_sessions (id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reading_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_type TEXT NOT NULL,
                    target_value INTEGER NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS book_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    pages_read INTEGER DEFAULT 0,
                    minutes_read INTEGER DEFAULT 0,
                    words_read INTEGER DEFAULT 0,
                    UNIQUE(book_id, date),
                    FOREIGN KEY (book_id) REFERENCES books (id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT
                )
            """)
            conn.commit()

    def add_book(self, file_path: str, title: str = "", author: str = "", 
                 file_format: str = "", total_pages: int = 0, 
                 total_words: int = 0, total_chapters: int = 0) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM books WHERE file_path = ?", (file_path,))
            row = cursor.fetchone()
            if row:
                return row[0]
            
            cursor.execute("""
                INSERT INTO books 
                (file_path, title, author, file_format, total_pages, 
                 total_words, total_chapters, date_added, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (file_path, title, author, file_format, total_pages,
                  total_words, total_chapters, datetime.now().isoformat(), 'not_started'))
            conn.commit()
            return cursor.lastrowid

    def update_book_status(self, book_id: int, status: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE books SET status = ?, last_read = ? WHERE id = ?
            """, (status, datetime.now().isoformat(), book_id))
            conn.commit()

    def save_position(self, position: ReadingPosition) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            book_id = position.book_id
            
            cursor.execute("SELECT id FROM reading_positions WHERE book_id = ?", (book_id,))
            row = cursor.fetchone()
            
            if row:
                cursor.execute("""
                    UPDATE reading_positions SET
                        chapter = ?, chapter_index = ?, paragraph_id = ?,
                        paragraph_index = ?, page_number = ?, page_x = ?, page_y = ?,
                        percentage = ?, word_count = ?, last_updated = ?
                    WHERE id = ?
                """, (position.chapter, position.chapter_index, position.paragraph_id,
                      position.paragraph_index, position.page_number, position.page_x, position.page_y,
                      position.percentage, position.word_count, position.last_updated, row[0]))
                pos_id = row[0]
            else:
                cursor.execute("""
                    INSERT INTO reading_positions
                    (book_id, file_path, file_format, chapter, chapter_index, 
                     paragraph_id, paragraph_index, page_number, page_x, page_y,
                     percentage, word_count, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (book_id, position.file_path, position.file_format,
                      position.chapter, position.chapter_index, position.paragraph_id,
                      position.paragraph_index, position.page_number, position.page_x, position.page_y,
                      position.percentage, position.word_count, position.last_updated))
                pos_id = cursor.lastrowid
            
            cursor.execute("""
                UPDATE books SET last_read = ?, status = ? WHERE id = ?
            """, (datetime.now().isoformat(), 'reading', book_id))
            
            conn.commit()
            return pos_id

    def get_position(self, book_id: int) -> Optional[ReadingPosition]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reading_positions WHERE book_id = ?", (book_id,))
            row = cursor.fetchone()
            if row:
                return ReadingPosition(
                    book_id=row['book_id'],
                    file_path=row['file_path'],
                    file_format=row['file_format'],
                    chapter=row['chapter'],
                    chapter_index=row['chapter_index'],
                    paragraph_id=row['paragraph_id'],
                    paragraph_index=row['paragraph_index'],
                    page_number=row['page_number'],
                    page_x=row['page_x'],
                    page_y=row['page_y'],
                    percentage=row['percentage'],
                    word_count=row['word_count'],
                    last_updated=row['last_updated']
                )
            return None

    def start_session(self, book_id: int) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reading_sessions (book_id, start_time, is_active)
                VALUES (?, ?, 1)
            """, (book_id, datetime.now().isoformat()))
            session_id = cursor.lastrowid
            conn.commit()
            return session_id

    def end_session(self, session_id: int, effective_duration: int = 0,
                    pages_read: int = 0, words_read: int = 0) -> Optional[ReadingSession]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reading_sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            start_time = datetime.fromisoformat(row['start_time'])
            end_time = datetime.now()
            duration_seconds = int((end_time - start_time).total_seconds())
            
            if effective_duration == 0:
                effective_duration = duration_seconds
            
            cursor.execute("""
                UPDATE reading_sessions SET
                    end_time = ?, duration_seconds = ?, effective_duration = ?,
                    is_active = 0, pages_read = ?, words_read = ?
                WHERE id = ?
            """, (end_time.isoformat(), duration_seconds, effective_duration,
                  pages_read, words_read, session_id))
            
            cursor.execute("""
                UPDATE books SET last_read = ? WHERE id = ?
            """, (end_time.isoformat(), row['book_id']))
            
            date_str = end_time.strftime('%Y-%m-%d')
            minutes_read = effective_duration // 60
            cursor.execute("""
                INSERT INTO book_progress (book_id, date, pages_read, minutes_read, words_read)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(book_id, date) DO UPDATE SET
                    pages_read = pages_read + ?,
                    minutes_read = minutes_read + ?,
                    words_read = words_read + ?
            """, (row['book_id'], date_str, pages_read, minutes_read, words_read,
                  pages_read, minutes_read, words_read))
            
            conn.commit()
            
            cursor.execute("SELECT * FROM reading_sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            return ReadingSession(
                book_id=row['book_id'],
                start_time=row['start_time'],
                end_time=row['end_time'],
                duration_seconds=row['duration_seconds'],
                effective_duration=row['effective_duration'],
                is_active=row['is_active'],
                pages_read=row['pages_read'],
                words_read=row['words_read']
            )

    def get_active_session(self, book_id: int) -> Optional[int]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM reading_sessions 
                WHERE book_id = ? AND is_active = 1
                ORDER BY start_time DESC LIMIT 1
            """, (book_id,))
            row = cursor.fetchone()
            return row[0] if row else None

    def add_record(self, session_id: int, book_id: int, event_type: str, 
                   position_data: Optional[Dict] = None):
        with self._connect() as conn:
            cursor = conn.cursor()
            data_json = json.dumps(position_data) if position_data else None
            cursor.execute("""
                INSERT INTO reading_records 
                (session_id, book_id, timestamp, event_type, position_data)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, book_id, datetime.now().isoformat(), event_type, data_json))
            conn.commit()

    def add_activity_event(self, session_id: Optional[int], event_type: str, details: Optional[Dict] = None):
        with self._connect() as conn:
            cursor = conn.cursor()
            details_json = json.dumps(details) if details else None
            cursor.execute("""
                INSERT INTO activity_events (session_id, event_type, timestamp, details)
                VALUES (?, ?, ?, ?)
            """, (session_id, event_type, datetime.now().isoformat(), details_json))
            conn.commit()

    def add_goal(self, goal: ReadingGoal) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reading_goals 
                (goal_type, target_value, start_date, end_date, description, created_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (goal.goal_type, goal.target_value, goal.start_date, 
                  goal.end_date, goal.description, goal.created_at, goal.is_active))
            conn.commit()
            return cursor.lastrowid

    def get_active_goals(self) -> List[ReadingGoal]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM reading_goals WHERE is_active = 1
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            return [ReadingGoal(
                id=row['id'],
                goal_type=row['goal_type'],
                target_value=row['target_value'],
                start_date=row['start_date'],
                end_date=row['end_date'],
                description=row['description'],
                created_at=row['created_at'],
                is_active=row['is_active']
            ) for row in rows]

    def complete_goal(self, goal_id: int):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE reading_goals SET is_active = 0 WHERE id = ?", (goal_id,))
            conn.commit()

    def get_reading_statistics(self, start_date: str, end_date: str) -> Dict[str, Any]:
        with self._connect() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(effective_duration), 0) as total_seconds,
                    COALESCE(SUM(pages_read), 0) as total_pages,
                    COALESCE(SUM(words_read), 0) as total_words,
                    COUNT(DISTINCT book_id) as books_read
                FROM reading_sessions 
                WHERE DATE(start_time) BETWEEN ? AND ? 
                AND is_active = 0
            """, (start_date, end_date))
            stats = dict(cursor.fetchone())
            
            cursor.execute("""
                SELECT DATE(start_time) as date, 
                       SUM(effective_duration) as duration,
                       SUM(pages_read) as pages
                FROM reading_sessions
                WHERE DATE(start_time) BETWEEN ? AND ?
                AND is_active = 0
                GROUP BY DATE(start_time)
                ORDER BY date
            """, (start_date, end_date))
            daily = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("""
                SELECT strftime('%H', start_time) as hour,
                       SUM(effective_duration) as duration
                FROM reading_sessions
                WHERE DATE(start_time) BETWEEN ? AND ?
                AND is_active = 0
                GROUP BY strftime('%H', start_time)
                ORDER BY hour
            """, (start_date, end_date))
            hourly = [dict(row) for row in cursor.fetchall()]
            
            return {
                'total_seconds': stats['total_seconds'],
                'total_minutes': stats['total_seconds'] // 60,
                'total_hours': stats['total_seconds'] // 3600,
                'total_pages': stats['total_pages'],
                'total_words': stats['total_words'],
                'books_read': stats['books_read'],
                'daily_data': daily,
                'hourly_data': hourly
            }

    def get_book_progress(self, book_id: int) -> Dict[str, Any]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(effective_duration), 0) as total_seconds,
                    COALESCE(SUM(pages_read), 0) as total_pages,
                    COALESCE(SUM(words_read), 0) as total_words,
                    COUNT(*) as sessions_count
                FROM reading_sessions 
                WHERE book_id = ? AND is_active = 0
            """, (book_id,))
            stats = dict(cursor.fetchone())
            
            cursor.execute("SELECT MIN(start_time) as first_read FROM reading_sessions WHERE book_id = ?", (book_id,))
            first_read = cursor.fetchone()['first_read']
            
            cursor.execute("SELECT MAX(end_time) as last_read FROM reading_sessions WHERE book_id = ?", (book_id,))
            last_read = cursor.fetchone()['last_read']
            
            if first_read and last_read:
                first = datetime.fromisoformat(first_read)
                last = datetime.fromisoformat(last_read)
                days_to_complete = (last.date() - first.date()).days + 1
            else:
                days_to_complete = None
            
            return {
                'total_minutes': stats['total_seconds'] // 60,
                'total_hours': stats['total_seconds'] // 3600,
                'total_pages': stats['total_pages'],
                'total_words': stats['total_words'],
                'sessions_count': stats['sessions_count'],
                'first_read': first_read,
                'last_read': last_read,
                'days_to_complete': days_to_complete
            }

    def get_books_in_range(self, start_date: str, end_date: str) -> List[Dict]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT b.id, b.title, b.author, b.file_format, b.status,
                       b.last_read, b.date_added,
                       COALESCE(SUM(rs.effective_duration), 0) as total_duration,
                       COALESCE(SUM(rs.pages_read), 0) as total_pages
                FROM books b
                LEFT JOIN reading_sessions rs ON b.id = rs.book_id
                WHERE DATE(rs.start_time) BETWEEN ? AND ? OR DATE(b.date_added) BETWEEN ? AND ?
                GROUP BY b.id
                ORDER BY b.last_read DESC
            """, (start_date, end_date, start_date, end_date))
            return [dict(row) for row in cursor.fetchall()]

    def export_to_csv(self, start_date: str, end_date: str, output_path: str):
        import csv
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    rs.id as session_id,
                    b.title,
                    b.author,
                    b.file_format,
                    rs.start_time,
                    rs.end_time,
                    rs.duration_seconds,
                    rs.effective_duration,
                    rs.pages_read,
                    rs.words_read
                FROM reading_sessions rs
                JOIN books b ON rs.book_id = b.id
                WHERE DATE(rs.start_time) BETWEEN ? AND ?
                AND rs.is_active = 0
                ORDER BY rs.start_time
            """, (start_date, end_date))
            rows = cursor.fetchall()
            
            with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['Session ID', '书名', '作者', '格式', '开始时间', '结束时间', 
                               '总时长(秒)', '有效时长(秒)', '阅读页数', '阅读字数'])
                for row in rows:
                    writer.writerow([row['session_id'], row['title'], row['author'], 
                                   row['file_format'], row['start_time'], row['end_time'],
                                   row['duration_seconds'], row['effective_duration'],
                                   row['pages_read'], row['words_read']])
