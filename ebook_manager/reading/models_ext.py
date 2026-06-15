from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


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
    mobi_record_index: Optional[int] = None
    mobi_byte_position: Optional[int] = None
    mobi_content_hash: Optional[str] = None


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
