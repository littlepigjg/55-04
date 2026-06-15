import json
import csv
from datetime import datetime
from typing import Optional, List, Dict, Any

from .connection import DatabaseConnection
from ..models_ext import ReadingPosition, ReadingSession, ReadingGoal


class BookQueries:
    def __init__(self, conn: DatabaseConnection):
        self.conn = conn

    def add_book(self, file_path: str, title: str = "", author: str = "",
                 file_format: str = "", total_pages: int = 0,
                 total_words: int = 0, total_chapters: int = 0) -> int:
        with self.conn.connect() as c:
            cur = c.cursor()
            cur.execute("SELECT id FROM books WHERE file_path = ?", (file_path,))
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute("""
                INSERT INTO books
                (file_path, title, author, file_format, total_pages,
                 total_words, total_chapters, date_added, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (file_path, title, author, file_format, total_pages,
                  total_words, total_chapters, datetime.now().isoformat(), 'not_started'))
            c.commit()
            return cur.lastrowid

    def update_status(self, book_id: int, status: str):
        with self.conn.connect() as c:
            c.cursor().execute(
                "UPDATE books SET status = ?, last_read = ? WHERE id = ?",
                (status, datetime.now().isoformat(), book_id),
            )
            c.commit()

    def get_books_in_range(self, start_date: str, end_date: str) -> List[Dict]:
        with self.conn.connect() as c:
            cur = c.cursor()
            cur.execute("""
                SELECT b.id, b.title, b.author, b.file_format, b.status,
                       b.last_read, b.date_added,
                       COALESCE(SUM(rs.effective_duration), 0) as total_duration,
                       COALESCE(SUM(rs.pages_read), 0) as total_pages
                FROM books b
                LEFT JOIN reading_sessions rs ON b.id = rs.book_id
                WHERE DATE(rs.start_time) BETWEEN ? AND ?
                   OR DATE(b.date_added) BETWEEN ? AND ?
                GROUP BY b.id
                ORDER BY b.last_read DESC
            """, (start_date, end_date, start_date, end_date))
            return [dict(row) for row in cur.fetchall()]


class PositionQueries:
    def __init__(self, conn: DatabaseConnection):
        self.conn = conn

    def save(self, position: ReadingPosition) -> int:
        with self.conn.connect() as c:
            cur = c.cursor()
            cur.execute("SELECT id FROM reading_positions WHERE book_id = ?",
                        (position.book_id,))
            row = cur.fetchone()
            if row:
                cur.execute("""
                    UPDATE reading_positions SET
                        chapter=?, chapter_index=?, paragraph_id=?,
                        paragraph_index=?, page_number=?, page_x=?, page_y=?,
                        percentage=?, word_count=?, last_updated=?,
                        mobi_record_index=?, mobi_byte_position=?, mobi_content_hash=?
                    WHERE id=?
                """, (position.chapter, position.chapter_index, position.paragraph_id,
                      position.paragraph_index, position.page_number, position.page_x,
                      position.page_y, position.percentage, position.word_count,
                      position.last_updated,
                      position.mobi_record_index, position.mobi_byte_position,
                      position.mobi_content_hash,
                      row[0]))
                pos_id = row[0]
            else:
                cur.execute("""
                    INSERT INTO reading_positions
                    (book_id, file_path, file_format, chapter, chapter_index,
                     paragraph_id, paragraph_index, page_number, page_x, page_y,
                     percentage, word_count, last_updated,
                     mobi_record_index, mobi_byte_position, mobi_content_hash)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (position.book_id, position.file_path, position.file_format,
                      position.chapter, position.chapter_index, position.paragraph_id,
                      position.paragraph_index, position.page_number, position.page_x,
                      position.page_y, position.percentage, position.word_count,
                      position.last_updated,
                      position.mobi_record_index, position.mobi_byte_position,
                      position.mobi_content_hash))
                pos_id = cur.lastrowid
            cur.execute(
                "UPDATE books SET last_read=?, status='reading' WHERE id=?",
                (datetime.now().isoformat(), position.book_id),
            )
            c.commit()
            return pos_id

    def get(self, book_id: int) -> Optional[ReadingPosition]:
        with self.conn.connect() as c:
            cur = c.cursor()
            cur.execute("SELECT * FROM reading_positions WHERE book_id=?", (book_id,))
            row = cur.fetchone()
            if row:
                return ReadingPosition(
                    book_id=row['book_id'], file_path=row['file_path'],
                    file_format=row['file_format'], chapter=row['chapter'],
                    chapter_index=row['chapter_index'], paragraph_id=row['paragraph_id'],
                    paragraph_index=row['paragraph_index'], page_number=row['page_number'],
                    page_x=row['page_x'], page_y=row['page_y'],
                    percentage=row['percentage'], word_count=row['word_count'],
                    last_updated=row['last_updated'],
                    mobi_record_index=row['mobi_record_index'] if 'mobi_record_index' in row.keys() else None,
                    mobi_byte_position=row['mobi_byte_position'] if 'mobi_byte_position' in row.keys() else None,
                    mobi_content_hash=row['mobi_content_hash'] if 'mobi_content_hash' in row.keys() else None,
                )
            return None


class SessionQueries:
    def __init__(self, conn: DatabaseConnection):
        self.conn = conn

    def start(self, book_id: int) -> int:
        with self.conn.connect() as c:
            cur = c.cursor()
            cur.execute(
                "INSERT INTO reading_sessions (book_id, start_time, is_active) VALUES (?,?,1)",
                (book_id, datetime.now().isoformat()),
            )
            c.commit()
            return cur.lastrowid

    def end(self, session_id: int, effective_duration: int = 0,
            pages_read: int = 0, words_read: int = 0) -> Optional[ReadingSession]:
        with self.conn.connect() as c:
            cur = c.cursor()
            cur.execute("SELECT * FROM reading_sessions WHERE id=?", (session_id,))
            row = cur.fetchone()
            if not row:
                return None
            start_time = datetime.fromisoformat(row['start_time'])
            end_time = datetime.now()
            duration_seconds = int((end_time - start_time).total_seconds())
            if effective_duration == 0:
                effective_duration = duration_seconds
            cur.execute("""
                UPDATE reading_sessions SET
                    end_time=?, duration_seconds=?, effective_duration=?,
                    is_active=0, pages_read=?, words_read=?
                WHERE id=?
            """, (end_time.isoformat(), duration_seconds, effective_duration,
                  pages_read, words_read, session_id))
            cur.execute("UPDATE books SET last_read=? WHERE id=?",
                        (end_time.isoformat(), row['book_id']))
            date_str = end_time.strftime('%Y-%m-%d')
            minutes_read = effective_duration // 60
            cur.execute("""
                INSERT INTO book_progress (book_id, date, pages_read, minutes_read, words_read)
                VALUES (?,?,?,?,?)
                ON CONFLICT(book_id, date) DO UPDATE SET
                    pages_read=pages_read+?, minutes_read=minutes_read+?, words_read=words_read+?
            """, (row['book_id'], date_str, pages_read, minutes_read, words_read,
                  pages_read, minutes_read, words_read))
            c.commit()
            cur.execute("SELECT * FROM reading_sessions WHERE id=?", (session_id,))
            r = cur.fetchone()
            return ReadingSession(
                book_id=r['book_id'], start_time=r['start_time'], end_time=r['end_time'],
                duration_seconds=r['duration_seconds'], effective_duration=r['effective_duration'],
                is_active=r['is_active'], pages_read=r['pages_read'], words_read=r['words_read'],
            )

    def get_active(self, book_id: int) -> Optional[int]:
        with self.conn.connect() as c:
            cur = c.cursor()
            cur.execute(
                "SELECT id FROM reading_sessions WHERE book_id=? AND is_active=1 ORDER BY start_time DESC LIMIT 1",
                (book_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None

    def add_record(self, session_id: int, book_id: int, event_type: str,
                   position_data: Optional[Dict] = None):
        with self.conn.connect() as c:
            data_json = json.dumps(position_data) if position_data else None
            c.cursor().execute(
                "INSERT INTO reading_records (session_id, book_id, timestamp, event_type, position_data) VALUES (?,?,?,?,?)",
                (session_id, book_id, datetime.now().isoformat(), event_type, data_json),
            )
            c.commit()

    def add_activity_event(self, session_id: Optional[int], event_type: str,
                           details: Optional[Dict] = None):
        with self.conn.connect() as c:
            details_json = json.dumps(details) if details else None
            c.cursor().execute(
                "INSERT INTO activity_events (session_id, event_type, timestamp, details) VALUES (?,?,?,?,?)",
                (session_id, event_type, datetime.now().isoformat(), details_json),
            )
            c.commit()


class StatisticsQueries:
    def __init__(self, conn: DatabaseConnection):
        self.conn = conn

    def get_reading_statistics(self, start_date: str, end_date: str) -> Dict[str, Any]:
        with self.conn.connect() as c:
            cur = c.cursor()
            cur.execute("""
                SELECT COALESCE(SUM(effective_duration),0) as total_seconds,
                       COALESCE(SUM(pages_read),0) as total_pages,
                       COALESCE(SUM(words_read),0) as total_words,
                       COUNT(DISTINCT book_id) as books_read
                FROM reading_sessions
                WHERE DATE(start_time) BETWEEN ? AND ? AND is_active=0
            """, (start_date, end_date))
            stats = dict(cur.fetchone())
            cur.execute("""
                SELECT DATE(start_time) as date,
                       SUM(effective_duration) as duration,
                       SUM(pages_read) as pages
                FROM reading_sessions
                WHERE DATE(start_time) BETWEEN ? AND ? AND is_active=0
                GROUP BY DATE(start_time) ORDER BY date
            """, (start_date, end_date))
            daily = [dict(row) for row in cur.fetchall()]
            cur.execute("""
                SELECT strftime('%H', start_time) as hour,
                       SUM(effective_duration) as duration
                FROM reading_sessions
                WHERE DATE(start_time) BETWEEN ? AND ? AND is_active=0
                GROUP BY strftime('%H', start_time) ORDER BY hour
            """, (start_date, end_date))
            hourly = [dict(row) for row in cur.fetchall()]
            return {
                'total_seconds': stats['total_seconds'],
                'total_minutes': stats['total_seconds'] // 60,
                'total_hours': stats['total_seconds'] // 3600,
                'total_pages': stats['total_pages'],
                'total_words': stats['total_words'],
                'books_read': stats['books_read'],
                'daily_data': daily,
                'hourly_data': hourly,
            }

    def get_book_progress(self, book_id: int) -> Dict[str, Any]:
        with self.conn.connect() as c:
            cur = c.cursor()
            cur.execute("""
                SELECT COALESCE(SUM(effective_duration),0) as total_seconds,
                       COALESCE(SUM(pages_read),0) as total_pages,
                       COALESCE(SUM(words_read),0) as total_words,
                       COUNT(*) as sessions_count
                FROM reading_sessions WHERE book_id=? AND is_active=0
            """, (book_id,))
            stats = dict(cur.fetchone())
            cur.execute("SELECT MIN(start_time) as first_read FROM reading_sessions WHERE book_id=?", (book_id,))
            first_read = cur.fetchone()['first_read']
            cur.execute("SELECT MAX(end_time) as last_read FROM reading_sessions WHERE book_id=?", (book_id,))
            last_read = cur.fetchone()['last_read']
            days_to_complete = None
            if first_read and last_read:
                first = datetime.fromisoformat(first_read)
                last = datetime.fromisoformat(last_read)
                days_to_complete = (last.date() - first.date()).days + 1
            return {
                'total_minutes': stats['total_seconds'] // 60,
                'total_hours': stats['total_seconds'] // 3600,
                'total_pages': stats['total_pages'],
                'total_words': stats['total_words'],
                'sessions_count': stats['sessions_count'],
                'first_read': first_read,
                'last_read': last_read,
                'days_to_complete': days_to_complete,
            }


class GoalQueries:
    def __init__(self, conn: DatabaseConnection):
        self.conn = conn

    def add(self, goal: ReadingGoal) -> int:
        with self.conn.connect() as c:
            cur = c.cursor()
            cur.execute("""
                INSERT INTO reading_goals
                (goal_type, target_value, start_date, end_date, description, created_at, is_active)
                VALUES (?,?,?,?,?,?,?)
            """, (goal.goal_type, goal.target_value, goal.start_date,
                  goal.end_date, goal.description, goal.created_at, goal.is_active))
            c.commit()
            return cur.lastrowid

    def get_active(self) -> List[ReadingGoal]:
        with self.conn.connect() as c:
            cur = c.cursor()
            cur.execute("SELECT * FROM reading_goals WHERE is_active=1 ORDER BY created_at DESC")
            return [ReadingGoal(
                id=row['id'], goal_type=row['goal_type'],
                target_value=row['target_value'], start_date=row['start_date'],
                end_date=row['end_date'], description=row['description'],
                created_at=row['created_at'], is_active=row['is_active'],
            ) for row in cur.fetchall()]

    def complete(self, goal_id: int):
        with self.conn.connect() as c:
            c.cursor().execute("UPDATE reading_goals SET is_active=0 WHERE id=?", (goal_id,))
            c.commit()

    def export_to_csv(self, start_date: str, end_date: str, output_path: str):
        with self.conn.connect() as c:
            cur = c.cursor()
            cur.execute("""
                SELECT rs.id as session_id, b.title, b.author, b.file_format,
                       rs.start_time, rs.end_time, rs.duration_seconds,
                       rs.effective_duration, rs.pages_read, rs.words_read
                FROM reading_sessions rs
                JOIN books b ON rs.book_id=b.id
                WHERE DATE(rs.start_time) BETWEEN ? AND ? AND rs.is_active=0
                ORDER BY rs.start_time
            """, (start_date, end_date))
            rows = cur.fetchall()
            with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['Session ID', '书名', '作者', '格式', '开始时间', '结束时间',
                                 '总时长(秒)', '有效时长(秒)', '阅读页数', '阅读字数'])
                for row in rows:
                    writer.writerow([row['session_id'], row['title'], row['author'],
                                     row['file_format'], row['start_time'], row['end_time'],
                                     row['duration_seconds'], row['effective_duration'],
                                     row['pages_read'], row['words_read']])
