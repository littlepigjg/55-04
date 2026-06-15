from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
import re

if TYPE_CHECKING:
    from .database import ReadingGoal


class GoalType(str, Enum):
    BOOKS_FINISHED = "books_finished"
    READING_MINUTES = "reading_minutes"
    PAGES_READ = "pages_read"
    WORDS_READ = "words_read"
    CHAPTERS_READ = "chapters_read"
    STREAK_DAYS = "streak_days"


class GoalPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


@dataclass
class GoalProgress:
    goal_id: int
    goal_type: str
    description: str
    target_value: int
    current_value: int
    percentage: float
    is_completed: bool
    remaining: int
    start_date: str
    end_date: str
    days_remaining: int
    estimated_daily_needed: float
    trend: str = "stable"


@dataclass
class GoalTemplate:
    name: str
    goal_type: str
    default_target: int
    default_period: str
    description_template: str


GOAL_TEMPLATES: List[GoalTemplate] = [
    GoalTemplate(
        name="本月读完N本书",
        goal_type=GoalType.BOOKS_FINISHED,
        default_target=5,
        default_period=GoalPeriod.MONTHLY,
        description_template="本月读完 {target} 本书"
    ),
    GoalTemplate(
        name="每周阅读N分钟",
        goal_type=GoalType.READING_MINUTES,
        default_target=300,
        default_period=GoalPeriod.WEEKLY,
        description_template="每周阅读 {target} 分钟"
    ),
    GoalTemplate(
        name="每日阅读N页",
        goal_type=GoalType.PAGES_READ,
        default_target=30,
        default_period=GoalPeriod.DAILY,
        description_template="每日阅读 {target} 页"
    ),
    GoalTemplate(
        name="本月阅读N分钟",
        goal_type=GoalType.READING_MINUTES,
        default_target=1500,
        default_period=GoalPeriod.MONTHLY,
        description_template="本月累计阅读 {target} 分钟"
    ),
    GoalTemplate(
        name="连续阅读N天",
        goal_type=GoalType.STREAK_DAYS,
        default_target=30,
        default_period=GoalPeriod.CUSTOM,
        description_template="连续阅读 {target} 天"
    ),
    GoalTemplate(
        name="读完N章节",
        goal_type=GoalType.CHAPTERS_READ,
        default_target=20,
        default_period=GoalPeriod.MONTHLY,
        description_template="本月阅读 {target} 章节"
    ),
]


class GoalManager:
    def __init__(self, db):
        self.db = db
        self._progress_callbacks: List[Callable] = []

    def _get_period_date_range(self, period: str, 
                               custom_start: Optional[str] = None,
                               custom_end: Optional[str] = None) -> tuple[str, str]:
        now = datetime.now()
        
        if period == GoalPeriod.DAILY:
            start = now.strftime('%Y-%m-%d')
            end = start
        elif period == GoalPeriod.WEEKLY:
            start = (now - timedelta(days=now.weekday())).strftime('%Y-%m-%d')
            end = (now + timedelta(days=6 - now.weekday())).strftime('%Y-%m-%d')
        elif period == GoalPeriod.MONTHLY:
            start = now.replace(day=1).strftime('%Y-%m-%d')
            next_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1)
            end = (next_month - timedelta(days=1)).strftime('%Y-%m-%d')
        elif period == GoalPeriod.YEARLY:
            start = now.replace(month=1, day=1).strftime('%Y-%m-%d')
            end = now.replace(month=12, day=31).strftime('%Y-%m-%d')
        else:
            start = custom_start or now.strftime('%Y-%m-%d')
            end = custom_end or start
        
        return start, end

    def create_goal(self, 
                    goal_type: str,
                    target_value: int,
                    period: str,
                    description: Optional[str] = None,
                    custom_start: Optional[str] = None,
                    custom_end: Optional[str] = None) -> int:
        start_date, end_date = self._get_period_date_range(period, custom_start, custom_end)
        
        if description is None:
            type_names = {
                GoalType.BOOKS_FINISHED: "读完",
                GoalType.READING_MINUTES: "阅读",
                GoalType.PAGES_READ: "阅读",
                GoalType.WORDS_READ: "阅读",
                GoalType.CHAPTERS_READ: "阅读",
                GoalType.STREAK_DAYS: "连续阅读",
            }
            unit_names = {
                GoalType.BOOKS_FINISHED: "本书",
                GoalType.READING_MINUTES: "分钟",
                GoalType.PAGES_READ: "页",
                GoalType.WORDS_READ: "字",
                GoalType.CHAPTERS_READ: "章节",
                GoalType.STREAK_DAYS: "天",
            }
            type_name = type_names.get(goal_type, "阅读")
            unit = unit_names.get(goal_type, "")
            description = f"{self._period_to_chinese(period)}{type_name}{target_value}{unit}"
        
        try:
            from .database import ReadingGoal
            goal = ReadingGoal(
                goal_type=goal_type,
                target_value=target_value,
                start_date=start_date,
                end_date=end_date,
                description=description
            )
            goal_id = self.db.add_goal(goal)
        except ImportError:
            goal_dict = {
                'goal_type': goal_type,
                'target_value': target_value,
                'start_date': start_date,
                'end_date': end_date,
                'description': description,
                'created_at': datetime.now().isoformat(),
                'is_active': 1
            }
            goal_id = self.db.add_goal(type('ReadingGoal', (), goal_dict)())
        self._notify_progress_update()
        return goal_id

    def _period_to_chinese(self, period: str) -> str:
        mapping = {
            GoalPeriod.DAILY: "每日",
            GoalPeriod.WEEKLY: "每周",
            GoalPeriod.MONTHLY: "本月",
            GoalPeriod.YEARLY: "本年",
            GoalPeriod.CUSTOM: "",
        }
        return mapping.get(period, "")

    def _calculate_books_finished(self, start_date: str, end_date: str) -> int:
        books = self.db.get_books_in_range(start_date, end_date)
        count = 0
        for book in books:
            if book.get('status') == 'completed':
                count += 1
            elif book.get('total_pages', 0) > 0 and book.get('total_pages', 0) > 0:
                progress = self._get_book_progress(book['id'])
                if progress >= 0.95:
                    count += 1
        return count

    def _get_book_progress(self, book_id: int) -> float:
        position = self.db.get_position(book_id)
        if position and position.percentage is not None:
            return position.percentage
        return 0.0

    def _calculate_reading_minutes(self, start_date: str, end_date: str) -> int:
        stats = self.db.get_reading_statistics(start_date, end_date)
        return stats.get('total_minutes', 0)

    def _calculate_pages_read(self, start_date: str, end_date: str) -> int:
        stats = self.db.get_reading_statistics(start_date, end_date)
        return stats.get('total_pages', 0)

    def _calculate_words_read(self, start_date: str, end_date: str) -> int:
        stats = self.db.get_reading_statistics(start_date, end_date)
        return stats.get('total_words', 0)

    def _calculate_chapters_read(self, start_date: str, end_date: str) -> int:
        books = self.db.get_books_in_range(start_date, end_date)
        total_chapters = 0
        for book in books:
            position = self.db.get_position(book['id'])
            if position and position.chapter_index is not None:
                total_chapters += position.chapter_index + 1
        return total_chapters

    def _calculate_streak_days(self, start_date: str, end_date: str) -> int:
        stats = self.db.get_reading_statistics(start_date, end_date)
        daily_data = stats.get('daily_data', [])
        
        if not daily_data:
            return 0
        
        read_dates = set()
        for item in daily_data:
            if item.get('duration', 0) >= 60:
                read_dates.add(item.get('date'))
        
        today = datetime.now().date()
        streak = 0
        check_date = today
        
        while True:
            date_str = check_date.strftime('%Y-%m-%d')
            if date_str in read_dates:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break
        
        return streak

    def _calculate_current_value(self, goal_type: str, start_date: str, end_date: str) -> int:
        calculators = {
            GoalType.BOOKS_FINISHED: self._calculate_books_finished,
            GoalType.READING_MINUTES: self._calculate_reading_minutes,
            GoalType.PAGES_READ: self._calculate_pages_read,
            GoalType.WORDS_READ: self._calculate_words_read,
            GoalType.CHAPTERS_READ: self._calculate_chapters_read,
            GoalType.STREAK_DAYS: self._calculate_streak_days,
        }
        
        calculator = calculators.get(goal_type)
        if calculator:
            return calculator(start_date, end_date)
        return 0

    def get_goal_progress(self, goal_id: int) -> Optional[GoalProgress]:
        goals = self.db.get_active_goals()
        goal = next((g for g in goals if g.id == goal_id), None)
        
        if not goal:
            return None
        
        current_value = self._calculate_current_value(
            goal.goal_type, goal.start_date, goal.end_date
        )
        
        percentage = (current_value / goal.target_value * 100) if goal.target_value > 0 else 0
        is_completed = current_value >= goal.target_value
        remaining = max(0, goal.target_value - current_value)
        
        end_date = datetime.strptime(goal.end_date, '%Y-%m-%d').date()
        today = datetime.now().date()
        days_remaining = max(0, (end_date - today).days + 1)
        
        if days_remaining > 0 and not is_completed:
            estimated_daily_needed = remaining / days_remaining
        else:
            estimated_daily_needed = 0
        
        trend = self._calculate_trend(goal)
        
        return GoalProgress(
            goal_id=goal.id,
            goal_type=goal.goal_type,
            description=goal.description,
            target_value=goal.target_value,
            current_value=current_value,
            percentage=min(percentage, 100),
            is_completed=is_completed,
            remaining=remaining,
            start_date=goal.start_date,
            end_date=goal.end_date,
            days_remaining=days_remaining,
            estimated_daily_needed=estimated_daily_needed,
            trend=trend
        )

    def _calculate_trend(self, goal) -> str:
        start = datetime.strptime(goal.start_date, '%Y-%m-%d').date()
        end = datetime.strptime(goal.end_date, '%Y-%m-%d').date()
        today = datetime.now().date()
        
        total_days = max(1, (end - start).days + 1)
        elapsed_days = max(1, (today - start).days + 1)
        
        expected_progress = elapsed_days / total_days
        current_value = self._calculate_current_value(goal.goal_type, goal.start_date, goal.end_date)
        actual_progress = current_value / goal.target_value if goal.target_value > 0 else 0
        
        diff = actual_progress - expected_progress
        
        if diff > 0.1:
            return "ahead"
        elif diff < -0.1:
            return "behind"
        else:
            return "stable"

    def get_all_goals_progress(self) -> List[GoalProgress]:
        goals = self.db.get_active_goals()
        return [
            progress for progress in 
            (self.get_goal_progress(goal.id) for goal in goals)
            if progress is not None
        ]

    def get_goals_for_ui(self) -> List[Dict]:
        progresses = self.get_all_goals_progress()
        return [
            {
                'id': p.goal_id,
                'description': p.description,
                'target': p.target_value,
                'current': p.current_value,
                'percentage': p.percentage,
                'is_completed': p.is_completed,
                'remaining': p.remaining,
                'days_remaining': p.days_remaining,
                'estimated_daily': p.estimated_daily_needed,
                'trend': p.trend,
                'type': p.goal_type,
                'start_date': p.start_date,
                'end_date': p.end_date
            }
            for p in progresses
        ]

    def complete_goal(self, goal_id: int):
        self.db.complete_goal(goal_id)
        self._notify_progress_update()

    def get_goal_templates(self) -> List[Dict]:
        return [
            {
                'name': t.name,
                'goal_type': t.goal_type,
                'default_target': t.default_target,
                'default_period': t.default_period,
                'description_template': t.description_template
            }
            for t in GOAL_TEMPLATES
        ]

    def register_progress_callback(self, callback: Callable):
        self._progress_callbacks.append(callback)

    def _notify_progress_update(self):
        for callback in self._progress_callbacks:
            try:
                callback()
            except Exception:
                pass

    def get_goal_summary(self) -> Dict:
        progresses = self.get_all_goals_progress()
        
        total = len(progresses)
        completed = sum(1 for p in progresses if p.is_completed)
        total_percentage = sum(p.percentage for p in progresses) / total if total > 0 else 0
        
        return {
            'total_goals': total,
            'completed_goals': completed,
            'in_progress_goals': total - completed,
            'average_progress': total_percentage,
            'goals': self.get_goals_for_ui()
        }
