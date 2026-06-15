from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging

from .database import ReadingDatabase, ReadingPosition
from .epub_parser import EPUBParser
from .pdf_tracker import PDFTracker
from .mobi_tracker import MOBITracker
from .activity_monitor import ActivityMonitor, ActivityEvent
from .visualization import ReadingVisualizer
from .goal_manager import GoalManager


class ReadingTracker:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init(*args, **kwargs)
        return cls._instance

    def _init(self, db_path: Optional[str] = None):
        self.db = ReadingDatabase(db_path)
        self.visualizer = ReadingVisualizer()
        self.goal_manager = GoalManager(self.db)
        
        self._current_book_id: Optional[int] = None
        self._current_book_path: Optional[str] = None
        self._current_session_id: Optional[int] = None
        self._current_format: Optional[str] = None
        
        self._epub_parser: Optional[EPUBParser] = None
        self._pdf_tracker: Optional[PDFTracker] = None
        self._mobi_tracker: Optional[MOBITracker] = None
        
        self._session_start_position: Optional[ReadingPosition] = None
        self._reading_speed_history: List[Dict] = []
        
        self._activity_monitor = ActivityMonitor(
            inactivity_threshold=60,
            poll_interval=1.0,
            activity_callback=self._on_activity_event,
            state_callback=self._on_activity_state_change
        )
        
        self._callbacks: Dict[str, List] = {
            'position_changed': [],
            'session_started': [],
            'session_ended': [],
            'activity_detected': [],
        }

    def register_callback(self, event: str, callback):
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _notify(self, event: str, *args, **kwargs):
        if event in self._callbacks:
            for callback in self._callbacks[event]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logging.error(f"Callback error for {event}: {e}")

    def _on_activity_event(self, event: ActivityEvent):
        if self._current_session_id:
            self.db.add_activity_event(
                session_id=self._current_session_id,
                event_type=event.event_type,
                details=event.details
            )
        self._notify('activity_detected', event)

    def _on_activity_state_change(self, state):
        pass

    def start_reading(self, book_path: str, title: str = "", author: str = "") -> int:
        book_path = str(Path(book_path).resolve())
        self._current_book_path = book_path
        
        ext = Path(book_path).suffix.lower().lstrip('.')
        self._current_format = ext
        
        book_id = self.db.add_book(
            file_path=book_path,
            title=title,
            author=author,
            file_format=ext,
            total_pages=self._get_total_pages(book_path, ext),
            total_words=self._get_total_words(book_path, ext),
            total_chapters=self._get_total_chapters(book_path, ext)
        )
        
        self._current_book_id = book_id
        
        existing_session = self.db.get_active_session(book_id)
        if existing_session:
            self.db.end_session(existing_session)
        
        self._session_start_position = self.db.get_position(book_id)
        self._current_session_id = self.db.start_session(book_id)
        
        self._init_format_parser(book_path, ext)
        
        self._activity_monitor.start()
        
        self.db.add_record(
            session_id=self._current_session_id,
            book_id=book_id,
            event_type="session_start",
            position_data=self._position_to_dict(self._session_start_position)
        )
        
        self.db.update_book_status(book_id, 'reading')
        self._notify('session_started', book_id, self._current_session_id)
        
        return self._current_session_id

    def _init_format_parser(self, book_path: str, ext: str):
        try:
            if ext == 'epub':
                self._epub_parser = EPUBParser(book_path)
                self._epub_parser.__enter__()
                self._epub_parser.load_all_chapters()
            elif ext == 'pdf':
                self._pdf_tracker = PDFTracker(book_path)
                self._pdf_tracker.__enter__()
            elif ext == 'mobi':
                self._mobi_tracker = MOBITracker(book_path)
                self._mobi_tracker.__enter__()
        except Exception as e:
            logging.error(f"Error initializing parser for {ext}: {e}")

    def _get_total_pages(self, book_path: str, ext: str) -> int:
        try:
            if ext == 'epub':
                with EPUBParser(book_path) as parser:
                    return parser.get_total_chapters() * 10
            elif ext == 'pdf':
                with PDFTracker(book_path) as tracker:
                    return tracker.get_total_pages()
            elif ext == 'mobi':
                with MOBITracker(book_path) as tracker:
                    return tracker.get_estimated_pages()
        except Exception:
            pass
        return 0

    def _get_total_words(self, book_path: str, ext: str) -> int:
        try:
            if ext == 'epub':
                with EPUBParser(book_path) as parser:
                    parser.load_all_chapters()
                    return parser.get_total_words()
            elif ext == 'pdf':
                with PDFTracker(book_path) as tracker:
                    return tracker.get_total_words()
            elif ext == 'mobi':
                with MOBITracker(book_path) as tracker:
                    return tracker.get_estimated_word_count()
        except Exception:
            pass
        return 0

    def _get_total_chapters(self, book_path: str, ext: str) -> int:
        try:
            if ext == 'epub':
                with EPUBParser(book_path) as parser:
                    return parser.get_total_chapters()
            elif ext == 'mobi':
                with MOBITracker(book_path) as tracker:
                    return tracker.get_total_chapters()
        except Exception:
            pass
        return 0

    def update_position(self, position_data: Dict[str, Any]) -> ReadingPosition:
        if not self._current_book_id or not self._current_session_id:
            raise RuntimeError("No active reading session")
        
        position = ReadingPosition(
            book_id=self._current_book_id,
            file_path=self._current_book_path,
            file_format=self._current_format,
            chapter=position_data.get('chapter'),
            chapter_index=position_data.get('chapter_index'),
            paragraph_id=position_data.get('paragraph_id'),
            paragraph_index=position_data.get('paragraph_index'),
            page_number=position_data.get('page_number'),
            page_x=position_data.get('page_x'),
            page_y=position_data.get('page_y'),
            percentage=position_data.get('percentage'),
            word_count=position_data.get('word_count', 0)
        )
        
        pos_id = self.db.save_position(position)
        
        self.db.add_record(
            session_id=self._current_session_id,
            book_id=self._current_book_id,
            event_type="position_update",
            position_data=self._position_to_dict(position)
        )
        
        if position.percentage is not None and position.percentage >= 0.95:
            self.db.update_book_status(self._current_book_id, 'completed')
        
        self._notify('position_changed', position)
        
        return position

    def update_position_epub(self, chapter_index: int, paragraph_index: int) -> ReadingPosition:
        if not self._epub_parser:
            raise RuntimeError("EPUB parser not initialized")
        
        pos = self._epub_parser.get_current_position(chapter_index, paragraph_index)
        if not pos:
            raise ValueError(f"Invalid position: chapter={chapter_index}, paragraph={paragraph_index}")
        
        return self.update_position({
            'chapter': pos.chapter_title,
            'chapter_index': pos.chapter_index,
            'paragraph_id': pos.paragraph_id,
            'paragraph_index': pos.paragraph_index,
            'percentage': pos.percentage,
            'word_count': pos.word_position
        })

    def update_position_pdf(self, page_number: int, x: float = 0, y: float = 0) -> ReadingPosition:
        if not self._pdf_tracker:
            raise RuntimeError("PDF tracker not initialized")
        
        percentage = self._pdf_tracker.get_percentage_from_page(page_number)
        page_info = self._pdf_tracker.get_page_info(page_number)
        
        return self.update_position({
            'page_number': page_number,
            'page_x': x,
            'page_y': y,
            'percentage': percentage,
            'word_count': page_info.word_count if page_info else 0
        })

    def update_position_mobi(self, percentage: float) -> ReadingPosition:
        if not self._mobi_tracker:
            raise RuntimeError("MOBI tracker not initialized")
        
        pos = self._mobi_tracker.get_position_from_percentage(percentage)
        
        return self.update_position({
            'percentage': percentage,
            'page_number': pos.page_number,
            'chapter_index': pos.chapter_index,
            'word_count': int(percentage * self._mobi_tracker.get_estimated_word_count())
        })

    def update_position_by_percentage(self, percentage: float) -> ReadingPosition:
        if not self._current_format:
            raise RuntimeError("No active book")
        
        if self._current_format == 'epub' and self._epub_parser:
            pos = self._epub_parser.get_position_from_percentage(percentage)
            if pos:
                return self.update_position_epub(pos.chapter_index, pos.paragraph_index)
        elif self._current_format == 'pdf' and self._pdf_tracker:
            page_info = self._pdf_tracker.get_page_from_percentage(percentage)
            if page_info:
                return self.update_position_pdf(page_info.page_number)
        elif self._current_format == 'mobi':
            return self.update_position_mobi(percentage)
        
        return self.update_position({'percentage': percentage})

    def get_current_position(self) -> Optional[ReadingPosition]:
        if not self._current_book_id:
            return None
        return self.db.get_position(self._current_book_id)

    def end_reading(self) -> Dict[str, Any]:
        if not self._current_session_id:
            return {}
        
        activity_stats = self._activity_monitor.stop()
        
        end_position = self.db.get_position(self._current_book_id)
        
        pages_read = self._calculate_pages_read(self._session_start_position, end_position)
        words_read = self._calculate_words_read(self._session_start_position, end_position)
        
        effective_duration = activity_stats.get('effective_duration_seconds', 0)
        
        session = self.db.end_session(
            session_id=self._current_session_id,
            effective_duration=effective_duration,
            pages_read=pages_read,
            words_read=words_read
        )
        
        if words_read > 0 and effective_duration > 0:
            speed = (words_read / effective_duration) * 60
            self._reading_speed_history.append({
                'date': datetime.now().strftime('%Y-%m-%d'),
                'speed': speed
            })
        
        self._cleanup_parsers()
        
        result = {
            'session_id': self._current_session_id,
            'book_id': self._current_book_id,
            'start_time': session.start_time if session else None,
            'end_time': session.end_time if session else None,
            'total_duration': session.duration_seconds if session else 0,
            'effective_duration': effective_duration,
            'pages_read': pages_read,
            'words_read': words_read,
            'reading_speed_wpm': (words_read / effective_duration * 60) if effective_duration > 0 else 0,
            'activity_stats': activity_stats
        }
        
        self._notify('session_ended', result)
        
        self._current_book_id = None
        self._current_book_path = None
        self._current_session_id = None
        self._session_start_position = None
        
        self.goal_manager._notify_progress_update()
        
        return result

    def _calculate_pages_read(self, start: Optional[ReadingPosition], 
                              end: Optional[ReadingPosition]) -> int:
        if not start or not end:
            return 0
        
        if end.page_number is not None and start.page_number is not None:
            return max(0, end.page_number - start.page_number)
        
        if end.percentage is not None and start.percentage is not None:
            total_pages = 0
            if self._current_book_id:
                with self.db._connect() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT total_pages FROM books WHERE id = ?", 
                                  (self._current_book_id,))
                    row = cursor.fetchone()
                    if row:
                        total_pages = row['total_pages'] or 0
            
            delta = end.percentage - start.percentage
            return max(0, int(delta * total_pages))
        
        return 0

    def _calculate_words_read(self, start: Optional[ReadingPosition],
                              end: Optional[ReadingPosition]) -> int:
        if not start or not end:
            return 0
        
        start_words = start.word_count or 0
        end_words = end.word_count or 0
        
        return max(0, end_words - start_words)

    def _cleanup_parsers(self):
        if self._epub_parser:
            try:
                self._epub_parser.__exit__(None, None, None)
            except Exception:
                pass
            self._epub_parser = None
        
        if self._pdf_tracker:
            try:
                self._pdf_tracker.__exit__(None, None, None)
            except Exception:
                pass
            self._pdf_tracker = None
        
        if self._mobi_tracker:
            try:
                self._mobi_tracker.__exit__(None, None, None)
            except Exception:
                pass
            self._mobi_tracker = None

    def get_statistics(self, period: str = 'week') -> Dict[str, Any]:
        now = datetime.now()
        
        if period == 'week':
            start = (now - timedelta(days=now.weekday())).strftime('%Y-%m-%d')
        elif period == 'month':
            start = now.replace(day=1).strftime('%Y-%m-%d')
        else:
            start = (now - timedelta(days=30)).strftime('%Y-%m-%d')
        
        end = now.strftime('%Y-%m-%d')
        
        return self.db.get_reading_statistics(start, end)

    def generate_charts(self, period: str = 'month') -> Dict[str, str]:
        stats = self.get_statistics(period)
        goals = self.goal_manager.get_goals_for_ui()
        
        books_in_range = self.db.get_books_in_range(
            stats.get('daily_data', [{}])[0].get('date', datetime.now().strftime('%Y-%m-%d')) 
                if stats.get('daily_data') else datetime.now().strftime('%Y-%m-%d'),
            datetime.now().strftime('%Y-%m-%d')
        )
        
        books_data = []
        for book in books_in_range:
            book_id = book['id']
            position = self.db.get_position(book_id)
            progress = position.percentage if position else 0.0
            book_progress = self.db.get_book_progress(book_id)
            
            books_data.append({
                'title': book.get('title', '未知'),
                'progress': progress,
                'days_to_complete': book_progress.get('days_to_complete', 0),
                'total_minutes': book_progress.get('total_minutes', 0)
            })
        
        return self.visualizer.generate_dashboard(
            stats=stats,
            goals=goals,
            books=books_data,
            speed_data=self._reading_speed_history
        )

    def export_data(self, output_path: str, 
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> str:
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        self.db.export_to_csv(start_date, end_date, output_path)
        return output_path

    def get_book_progress(self, book_id: Optional[int] = None) -> Dict[str, Any]:
        bid = book_id or self._current_book_id
        if not bid:
            return {}
        
        position = self.db.get_position(bid)
        progress = self.db.get_book_progress(bid)
        
        result = {
            'position': self._position_to_dict(position),
            'progress': progress
        }
        
        if bid == self._current_book_id:
            result['activity_state'] = self._activity_monitor.get_current_state().__dict__
        
        return result

    def _position_to_dict(self, position: Optional[ReadingPosition]) -> Dict:
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

    def pause_reading(self):
        self._activity_monitor.manual_pause()

    def resume_reading(self):
        self._activity_monitor.manual_resume()

    def get_activity_state(self):
        return self._activity_monitor.get_current_state()

    def get_goal_manager(self) -> GoalManager:
        return self.goal_manager

    def get_epub_parser(self) -> Optional[EPUBParser]:
        return self._epub_parser

    def get_pdf_tracker(self) -> Optional[PDFTracker]:
        return self._pdf_tracker

    def get_mobi_tracker(self) -> Optional[MOBITracker]:
        return self._mobi_tracker
