from .connection import DatabaseConnection
from .queries import (
    BookQueries, PositionQueries, SessionQueries,
    StatisticsQueries, GoalQueries,
)
from ..models_ext import ReadingPosition, ReadingSession, ReadingGoal


class ReadingDatabase:
    _instance = None

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    def __new__(cls, db_path=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._db_initialized = False
        if not cls._instance._db_initialized:
            cls._instance._init(db_path)
            cls._instance._db_initialized = True
        return cls._instance

    def _init(self, db_path=None):
        self._conn = DatabaseConnection(db_path)
        self.books = BookQueries(self._conn)
        self.positions = PositionQueries(self._conn)
        self.sessions = SessionQueries(self._conn)
        self.statistics = StatisticsQueries(self._conn)
        self.goals = GoalQueries(self._conn)

    def _connect(self):
        return self._conn.connect()

    def add_book(self, *args, **kwargs):
        return self.books.add_book(*args, **kwargs)

    def update_book_status(self, *args, **kwargs):
        self.books.update_status(*args, **kwargs)

    def save_position(self, position):
        return self.positions.save(position)

    def get_position(self, book_id):
        return self.positions.get(book_id)

    def start_session(self, book_id):
        return self.sessions.start(book_id)

    def end_session(self, session_id, **kwargs):
        return self.sessions.end(session_id, **kwargs)

    def get_active_session(self, book_id):
        return self.sessions.get_active(book_id)

    def add_record(self, *args, **kwargs):
        self.sessions.add_record(*args, **kwargs)

    def add_activity_event(self, *args, **kwargs):
        self.sessions.add_activity_event(*args, **kwargs)

    def add_goal(self, goal):
        return self.goals.add(goal)

    def get_active_goals(self):
        return self.goals.get_active()

    def complete_goal(self, goal_id):
        self.goals.complete(goal_id)

    def get_reading_statistics(self, *args, **kwargs):
        return self.statistics.get_reading_statistics(*args, **kwargs)

    def get_book_progress(self, book_id):
        return self.statistics.get_book_progress(book_id)

    def get_books_in_range(self, *args, **kwargs):
        return self.books.get_books_in_range(*args, **kwargs)

    def export_to_csv(self, *args, **kwargs):
        self.goals.export_to_csv(*args, **kwargs)
