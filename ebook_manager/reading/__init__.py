from .database import ReadingDatabase, ReadingPosition, ReadingSession, ReadingGoal
from .models_ext import ReadingPosition as Position, ReadingSession as Session, ReadingGoal as Goal

__all__ = [
    'ReadingDatabase',
    'ReadingPosition',
    'ReadingSession',
    'ReadingGoal',
    'Position',
    'Session',
    'Goal',
]


def __getattr__(name):
    lazy = {
        'EPUBParser': '.epub_parser',
        'PDFTracker': '.pdf_tracker',
        'MOBITracker': '.mobi_tracker',
        'ActivityMonitor': '.monitors.activity_monitor',
        'ReadingVisualizer': '.visualization',
        'GoalManager': '.goal_manager',
        'ReadingTracker': '.tracker',
        'SessionManager': '.session_manager',
        'PositionManager': '.position_manager',
        'SpeedCalculator': '.speed_calculator',
        'SystemIdleDetector': '.monitors.idle_detector',
        'WindowFocusMonitor': '.monitors.focus_monitor',
    }
    if name in lazy:
        import importlib
        mod = importlib.import_module(lazy[name], __package__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
