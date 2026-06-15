import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any
import sqlite3


class DataExporter:
    def __init__(self, db):
        self.db = db

    def export_to_csv(self, output_path: str,
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None,
                      include_details: bool = True) -> str:
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        output_path = str(Path(output_path))
        
        with self.db._connect() as conn:
            conn.row_factory = sqlite3.Row
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
            sessions = cursor.fetchall()
            
            with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    '会话ID', '书名', '作者', '格式', '开始时间', '结束时间',
                    '总时长(秒)', '有效时长(秒)', '总时长(分钟)', '有效时长(分钟)',
                    '阅读页数', '阅读字数', '阅读速度(字/分钟)'
                ])
                
                for row in sessions:
                    duration_min = row['duration_seconds'] / 60 if row['duration_seconds'] else 0
                    effective_min = row['effective_duration'] / 60 if row['effective_duration'] else 0
                    speed = (row['words_read'] / effective_min) if effective_min > 0 else 0
                    
                    writer.writerow([
                        row['session_id'],
                        row['title'],
                        row['author'],
                        row['file_format'],
                        row['start_time'],
                        row['end_time'],
                        row['duration_seconds'],
                        row['effective_duration'],
                        f"{duration_min:.1f}",
                        f"{effective_min:.1f}",
                        row['pages_read'],
                        row['words_read'],
                        f"{speed:.0f}"
                    ])
            
            if include_details:
                detail_path = str(Path(output_path).with_name(
                    Path(output_path).stem + '_details.csv'
                ))
                self._export_details_csv(cursor, detail_path, start_date, end_date)
                
                position_path = str(Path(output_path).with_name(
                    Path(output_path).stem + '_positions.csv'
                ))
                self._export_positions_csv(cursor, position_path, start_date, end_date)
        
        return output_path

    def _export_details_csv(self, cursor, output_path: str, 
                           start_date: str, end_date: str):
        cursor.execute("""
            SELECT 
                rr.id,
                b.title,
                rr.timestamp,
                rr.event_type,
                rr.position_data
            FROM reading_records rr
            JOIN books b ON rr.book_id = b.id
            WHERE DATE(rr.timestamp) BETWEEN ? AND ?
            ORDER BY rr.timestamp
        """, (start_date, end_date))
        records = cursor.fetchall()
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([
                '记录ID', '书名', '时间', '事件类型', '位置数据'
            ])
            
            for row in records:
                pos_data = row['position_data'] or ''
                try:
                    if pos_data:
                        data = json.loads(pos_data)
                        pos_data = json.dumps(data, ensure_ascii=False)
                except Exception:
                    pass
                
                writer.writerow([
                    row['id'],
                    row['title'],
                    row['timestamp'],
                    row['event_type'],
                    pos_data
                ])

    def _export_positions_csv(self, cursor, output_path: str,
                             start_date: str, end_date: str):
        cursor.execute("""
            SELECT 
                rp.id,
                b.title,
                b.file_format,
                rp.chapter,
                rp.chapter_index,
                rp.paragraph_id,
                rp.paragraph_index,
                rp.page_number,
                rp.page_x,
                rp.page_y,
                rp.percentage,
                rp.word_count,
                rp.last_updated
            FROM reading_positions rp
            JOIN books b ON rp.book_id = b.id
            WHERE DATE(rp.last_updated) BETWEEN ? AND ?
            ORDER BY rp.last_updated
        """, (start_date, end_date))
        positions = cursor.fetchall()
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([
                '位置ID', '书名', '格式', '章节', '章节索引', '段落ID',
                '段落索引', '页码', 'X坐标', 'Y坐标', '进度百分比',
                '累计字数', '更新时间'
            ])
            
            for row in positions:
                writer.writerow([
                    row['id'],
                    row['title'],
                    row['file_format'],
                    row['chapter'] or '',
                    row['chapter_index'] or '',
                    row['paragraph_id'] or '',
                    row['paragraph_index'] or '',
                    row['page_number'] or '',
                    row['page_x'] or '',
                    row['page_y'] or '',
                    f"{row['percentage'] * 100:.2f}%" if row['percentage'] is not None else '',
                    row['word_count'] or '',
                    row['last_updated']
                ])

    def export_to_json(self, output_path: str,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> str:
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        stats = self.db.get_reading_statistics(start_date, end_date)
        books = self.db.get_books_in_range(start_date, end_date)
        
        books_data = []
        for book in books:
            book_id = book['id']
            position = self.db.get_position(book_id)
            book_progress = self.db.get_book_progress(book_id)
            
            books_data.append({
                'book_info': dict(book),
                'current_position': self._position_to_dict(position),
                'reading_progress': book_progress
            })
        
        export_data = {
            'export_time': datetime.now().isoformat(),
            'date_range': {
                'start': start_date,
                'end': end_date
            },
            'summary': {
                'total_hours': stats.get('total_hours', 0),
                'total_minutes': stats.get('total_minutes', 0),
                'total_pages': stats.get('total_pages', 0),
                'total_words': stats.get('total_words', 0),
                'books_read': stats.get('books_read', 0)
            },
            'daily_statistics': stats.get('daily_data', []),
            'hourly_statistics': stats.get('hourly_data', []),
            'books': books_data
        }
        
        output_path = str(Path(output_path))
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return output_path

    def export_book_progress(self, book_id: int, output_path: str) -> str:
        position = self.db.get_position(book_id)
        progress = self.db.get_book_progress(book_id)
        
        with self.db._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
            book = cursor.fetchone()
            
            cursor.execute("""
                SELECT * FROM reading_sessions 
                WHERE book_id = ? AND is_active = 0
                ORDER BY start_time
            """, (book_id,))
            sessions = [dict(row) for row in cursor.fetchall()]
        
        export_data = {
            'book': dict(book) if book else {},
            'current_position': self._position_to_dict(position),
            'total_progress': progress,
            'sessions': sessions
        }
        
        output_path = str(Path(output_path))
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return output_path

    def _position_to_dict(self, position) -> Dict:
        if not position:
            return {}
        return {
            'book_id': position.book_id,
            'file_path': position.file_path,
            'file_format': position.file_format,
            'chapter': position.chapter,
            'chapter_index': position.chapter_index,
            'paragraph_id': position.paragraph_id,
            'paragraph_index': position.paragraph_index,
            'page_number': position.page_number,
            'page_x': position.page_x,
            'page_y': position.page_y,
            'percentage': position.percentage,
            'word_count': position.word_count,
            'last_updated': position.last_updated
        }

    def get_export_summary(self, start_date: str, end_date: str) -> Dict[str, Any]:
        stats = self.db.get_reading_statistics(start_date, end_date)
        books = self.db.get_books_in_range(start_date, end_date)
        
        return {
            'date_range': {'start': start_date, 'end': end_date},
            'total_sessions': self._count_sessions(start_date, end_date),
            'total_records': self._count_records(start_date, end_date),
            'books_count': len(books),
            'summary': {
                'total_hours': stats.get('total_hours', 0),
                'total_minutes': stats.get('total_minutes', 0),
                'total_pages': stats.get('total_pages', 0),
                'total_words': stats.get('total_words', 0)
            }
        }

    def _count_sessions(self, start_date: str, end_date: str) -> int:
        with self.db._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count FROM reading_sessions
                WHERE DATE(start_time) BETWEEN ? AND ? AND is_active = 0
            """, (start_date, end_date))
            return cursor.fetchone()[0]

    def _count_records(self, start_date: str, end_date: str) -> int:
        with self.db._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count FROM reading_records
                WHERE DATE(timestamp) BETWEEN ? AND ?
            """, (start_date, end_date))
            return cursor.fetchone()[0]
