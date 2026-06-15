from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging

from .database import ReadingDatabase, ReadingPosition
from .models_ext import ReadingPosition as Position, ReadingSession, ReadingGoal
from .epub_parser import EPUBParser
from .pdf_tracker import PDFTracker
from .mobi_tracker import MOBITracker
from .monitors.activity_monitor import ActivityMonitor, ActivityEvent, ActivityState
from .visualization import ReadingVisualizer
from .goal_manager import GoalManager
from .session_manager import SessionManager
from .position_manager import PositionManager
from .speed_calculator import SpeedCalculator


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

        self._session_mgr = SessionManager(self.db)
        self._position_mgr = PositionManager(self.db)
        self._speed_calc = SpeedCalculator()

        self._current_book_path: Optional[str] = None
        self._current_format: Optional[str] = None

        self._epub_parser: Optional[EPUBParser] = None
        self._pdf_tracker: Optional[PDFTracker] = None
        self._mobi_tracker: Optional[MOBITracker] = None

        self._activity_monitor = ActivityMonitor(
            idle_threshold=180,
            heartbeat_interval=2.0,
            focus_loss_grace=10,
            activity_callback=self._on_activity_event,
        )

        self._callbacks: Dict[str, List] = {
            'position_changed': [],
            'session_started': [],
            'session_ended': [],
        }

    def register_callback(self, event: str, callback):
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _notify(self, event: str, *args, **kwargs):
        for cb in self._callbacks.get(event, []):
            try:
                cb(*args, **kwargs)
            except Exception as e:
                logging.error(f"Callback error for {event}: {e}")

    def _on_activity_event(self, event: ActivityEvent):
        session_id = self._session_mgr.get_session_id()
        if session_id:
            self._activity_monitor.enqueue_write(
                self.db.add_activity_event,
                session_id, event.event_type, event.details,
            )

    def start_reading(self, book_path: str, title: str = "", author: str = "") -> int:
        book_path = str(Path(book_path).resolve())
        self._current_book_path = book_path
        ext = Path(book_path).suffix.lower().lstrip('.')
        self._current_format = ext

        book_id = self.db.add_book(
            file_path=book_path, title=title, author=author,
            file_format=ext,
            total_pages=self._get_total_pages(book_path, ext),
            total_words=self._get_total_words(book_path, ext),
            total_chapters=self._get_total_chapters(book_path, ext),
        )

        session_id = self._session_mgr.start(book_id)
        self._init_format_parser(book_path, ext)
        self._activity_monitor.start()
        self._notify('session_started', book_id, session_id)
        return session_id

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
                with EPUBParser(book_path) as p:
                    return p.get_total_chapters() * 10
            elif ext == 'pdf':
                with PDFTracker(book_path) as t:
                    return t.get_total_pages()
            elif ext == 'mobi':
                with MOBITracker(book_path) as t:
                    return t.get_estimated_pages()
        except Exception:
            pass
        return 0

    def _get_total_words(self, book_path: str, ext: str) -> int:
        try:
            if ext == 'epub':
                with EPUBParser(book_path) as p:
                    p.load_all_chapters()
                    return p.get_total_words()
            elif ext == 'pdf':
                with PDFTracker(book_path) as t:
                    return t.get_total_words()
            elif ext == 'mobi':
                with MOBITracker(book_path) as t:
                    return t.get_estimated_word_count()
        except Exception:
            pass
        return 0

    def _get_total_chapters(self, book_path: str, ext: str) -> int:
        try:
            if ext == 'epub':
                with EPUBParser(book_path) as p:
                    return p.get_total_chapters()
            elif ext == 'mobi':
                with MOBITracker(book_path) as t:
                    return t.get_total_chapters()
        except Exception:
            pass
        return 0

    def update_position(self, position_data: Dict[str, Any]) -> ReadingPosition:
        book_id = self._session_mgr.get_book_id()
        if not book_id:
            raise RuntimeError("No active reading session")
        position = self._position_mgr.build_position(
            book_id=book_id,
            file_path=self._current_book_path,
            file_format=self._current_format,
            **position_data,
        )
        self._position_mgr.save(position)
        session_id = self._session_mgr.get_session_id()
        if session_id:
            self._activity_monitor.enqueue_write(
                self.db.add_record,
                session_id, book_id, "position_update",
                PositionManager.position_to_dict(position),
            )
        self._notify('position_changed', position)
        return position

    def update_position_epub(self, chapter_index: int, paragraph_index: int) -> ReadingPosition:
        if not self._epub_parser:
            raise RuntimeError("EPUB parser not initialized")
        pos = self._epub_parser.get_current_position(chapter_index, paragraph_index)
        if not pos:
            raise ValueError(f"Invalid position: chapter={chapter_index}, paragraph={paragraph_index}")
        return self.update_position({
            'chapter': pos.chapter_title, 'chapter_index': pos.chapter_index,
            'paragraph_id': pos.paragraph_id, 'paragraph_index': pos.paragraph_index,
            'percentage': pos.percentage, 'word_count': pos.word_position,
        })

    def update_position_pdf(self, page_number: int, x: float = 0, y: float = 0) -> ReadingPosition:
        if not self._pdf_tracker:
            raise RuntimeError("PDF tracker not initialized")
        percentage = self._pdf_tracker.get_percentage_from_page(page_number)
        page_info = self._pdf_tracker.get_page_info(page_number)
        return self.update_position({
            'page_number': page_number, 'page_x': x, 'page_y': y,
            'percentage': percentage,
            'word_count': page_info.word_count if page_info else 0,
        })

    def update_position_mobi(self, page_number: int) -> ReadingPosition:
        if not self._mobi_tracker:
            raise RuntimeError("MOBI tracker not initialized")
        pos = self._mobi_tracker.get_position_from_page(page_number)
        anchor = pos.anchor
        return self.update_position({
            'page_number': pos.page_number,
            'chapter_index': pos.chapter_index,
            'percentage': pos.percentage,
            'word_count': int(pos.percentage * self._mobi_tracker.get_estimated_word_count()),
            'mobi_record_index': pos.record_index,
            'mobi_byte_position': pos.byte_position,
            'mobi_content_hash': anchor.content_hash if anchor else None,
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
        elif self._current_format == 'mobi' and self._mobi_tracker:
            pos = self._mobi_tracker.get_position_from_percentage(percentage)
            return self.update_position_mobi(pos.page_number)
        return self.update_position({'percentage': percentage})

    def get_current_position(self) -> Optional[ReadingPosition]:
        book_id = self._session_mgr.get_book_id()
        if not book_id:
            return None
        return self.db.get_position(book_id)

    def end_reading(self) -> Dict[str, Any]:
        if not self._session_mgr.is_active():
            return {}

        self._position_mgr.stop()

        activity_stats = self._activity_monitor.stop()
        book_id = self._session_mgr.get_book_id()

        end_position = self.db.get_position(book_id) if book_id else None
        start_position = self._session_mgr.get_start_position()

        pages_read = self._position_mgr.calculate_pages_read(
            start_position, end_position, book_id)
        words_read = self._position_mgr.calculate_words_read(
            start_position, end_position)

        effective_duration = activity_stats.get('effective_duration_seconds', 0)

        result = self._session_mgr.end(
            effective_duration=effective_duration,
            pages_read=pages_read,
            words_read=words_read,
        )

        if result:
            speed = self._speed_calc.record(words_read, effective_duration)
            result['reading_speed_wpm'] = speed or 0
            result['activity_stats'] = activity_stats

        self._cleanup_parsers()
        self._notify('session_ended', result or {})
        self.goal_manager._notify_progress_update()
        return result or {}

    def _cleanup_parsers(self):
        for parser in [self._epub_parser, self._pdf_tracker, self._mobi_tracker]:
            if parser:
                try:
                    parser.__exit__(None, None, None)
                except Exception:
                    pass
        self._epub_parser = None
        self._pdf_tracker = None
        self._mobi_tracker = None

    def get_statistics(self, period: str = 'week') -> Dict[str, Any]:
        now = datetime.now()
        if period == 'week':
            start = (now - timedelta(days=now.weekday())).strftime('%Y-%m-%d')
        elif period == 'month':
            start = now.replace(day=1).strftime('%Y-%m-%d')
        else:
            start = (now - timedelta(days=30)).strftime('%Y-%m-%d')
        return self.db.get_reading_statistics(start, now.strftime('%Y-%m-%d'))

    def generate_charts(self, period: str = 'month') -> Dict[str, str]:
        stats = self.get_statistics(period)
        goals = self.goal_manager.get_goals_for_ui()
        now = datetime.now()
        start_date = stats.get('daily_data', [{}])[0].get('date', now.strftime('%Y-%m-%d')) if stats.get('daily_data') else now.strftime('%Y-%m-%d')
        books_in_range = self.db.get_books_in_range(start_date, now.strftime('%Y-%m-%d'))
        books_data = []
        for book in books_in_range:
            position = self.db.get_position(book['id'])
            progress = position.percentage if position else 0.0
            bp = self.db.get_book_progress(book['id'])
            books_data.append({
                'title': book.get('title', '未知'), 'progress': progress,
                'days_to_complete': bp.get('days_to_complete', 0),
                'total_minutes': bp.get('total_minutes', 0),
            })
        return self.visualizer.generate_dashboard(
            stats=stats, goals=goals, books=books_data,
            speed_data=self._speed_calc.get_history(),
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
        bid = book_id or self._session_mgr.get_book_id()
        if not bid:
            return {}
        position = self.db.get_position(bid)
        progress = self.db.get_book_progress(bid)
        result = {
            'position': PositionManager.position_to_dict(position),
            'progress': progress,
        }
        if bid == self._session_mgr.get_book_id():
            result['activity_state'] = self._activity_monitor.get_current_state().__dict__
        return result

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
