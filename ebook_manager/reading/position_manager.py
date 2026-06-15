from typing import Optional, Dict, Any
import logging

from .database import ReadingDatabase
from .models_ext import ReadingPosition


class PositionManager:
    def __init__(self, db: ReadingDatabase):
        self.db = db

    def save(self, position: ReadingPosition) -> int:
        pos_id = self.db.save_position(position)
        if position.percentage is not None and position.percentage >= 0.95:
            self.db.update_book_status(position.book_id, 'completed')
        return pos_id

    def load(self, book_id: int) -> Optional[ReadingPosition]:
        return self.db.get_position(book_id)

    def build_position(self, book_id: int, file_path: str,
                       file_format: str, **kwargs) -> ReadingPosition:
        return ReadingPosition(
            book_id=book_id,
            file_path=file_path,
            file_format=file_format,
            chapter=kwargs.get('chapter'),
            chapter_index=kwargs.get('chapter_index'),
            paragraph_id=kwargs.get('paragraph_id'),
            paragraph_index=kwargs.get('paragraph_index'),
            page_number=kwargs.get('page_number'),
            page_x=kwargs.get('page_x'),
            page_y=kwargs.get('page_y'),
            percentage=kwargs.get('percentage'),
            word_count=kwargs.get('word_count', 0),
        )

    def calculate_pages_read(self, start: Optional[ReadingPosition],
                             end: Optional[ReadingPosition],
                             book_id: Optional[int] = None) -> int:
        if not start or not end:
            return 0
        if end.page_number is not None and start.page_number is not None:
            return max(0, end.page_number - start.page_number)
        if end.percentage is not None and start.percentage is not None and book_id:
            total_pages = 0
            with self.db._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT total_pages FROM books WHERE id = ?", (book_id,))
                row = cursor.fetchone()
                if row:
                    total_pages = row['total_pages'] or 0
            delta = end.percentage - start.percentage
            return max(0, int(delta * total_pages))
        return 0

    def calculate_words_read(self, start: Optional[ReadingPosition],
                             end: Optional[ReadingPosition]) -> int:
        if not start or not end:
            return 0
        start_words = start.word_count or 0
        end_words = end.word_count or 0
        return max(0, end_words - start_words)

    @staticmethod
    def position_to_dict(position: Optional[ReadingPosition]) -> Dict:
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
            'last_updated': position.last_updated,
        }
