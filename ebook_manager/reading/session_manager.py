from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging

from .database import ReadingDatabase
from .models_ext import ReadingPosition, ReadingSession


@dataclass
class SessionInfo:
    session_id: int
    book_id: int
    start_time: str
    start_position: Optional[ReadingPosition] = None


class SessionManager:
    def __init__(self, db: ReadingDatabase):
        self.db = db
        self._current_session: Optional[SessionInfo] = None
        self._current_book_id: Optional[int] = None

    def start(self, book_id: int) -> int:
        existing = self.db.get_active_session(book_id)
        if existing:
            self.db.end_session(existing)

        session_id = self.db.start_session(book_id)
        start_pos = self.db.get_position(book_id)

        self._current_session = SessionInfo(
            session_id=session_id,
            book_id=book_id,
            start_time=datetime.now().isoformat(),
            start_position=start_pos,
        )
        self._current_book_id = book_id

        self.db.add_record(
            session_id=session_id,
            book_id=book_id,
            event_type="session_start",
            position_data=self._position_to_dict(start_pos),
        )
        self.db.update_book_status(book_id, 'reading')

        return session_id

    def end(self, effective_duration: int = 0,
            pages_read: int = 0, words_read: int = 0) -> Optional[Dict[str, Any]]:
        if not self._current_session:
            return None

        session_id = self._current_session.session_id
        book_id = self._current_session.book_id

        session = self.db.end_session(
            session_id=session_id,
            effective_duration=effective_duration,
            pages_read=pages_read,
            words_read=words_read,
        )

        result = {
            'session_id': session_id,
            'book_id': book_id,
            'start_time': session.start_time if session else None,
            'end_time': session.end_time if session else None,
            'total_duration': session.duration_seconds if session else 0,
            'effective_duration': effective_duration,
            'pages_read': pages_read,
            'words_read': words_read,
        }

        self._current_session = None
        self._current_book_id = None
        return result

    def is_active(self) -> bool:
        return self._current_session is not None

    def get_session_id(self) -> Optional[int]:
        return self._current_session.session_id if self._current_session else None

    def get_book_id(self) -> Optional[int]:
        return self._current_book_id

    def get_start_position(self) -> Optional[ReadingPosition]:
        if self._current_session:
            return self._current_session.start_position
        return None

    def record_event(self, event_type: str, position_data: Optional[Dict] = None):
        if self._current_session:
            self.db.add_record(
                session_id=self._current_session.session_id,
                book_id=self._current_session.book_id,
                event_type=event_type,
                position_data=position_data,
            )

    def record_activity_event(self, event_type: str, details: Optional[Dict] = None):
        if self._current_session:
            self.db.add_activity_event(
                session_id=self._current_session.session_id,
                event_type=event_type,
                details=details,
            )

    @staticmethod
    def _position_to_dict(position: Optional[ReadingPosition]) -> Dict:
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
            'percentage': position.percentage,
            'word_count': position.word_count,
        }
