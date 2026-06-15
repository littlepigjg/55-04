from .database import ReadingDatabase, ReadingPosition, ReadingSession, ReadingGoal

__all__ = [
    'ReadingDatabase',
    'ReadingPosition',
    'ReadingSession',
    'ReadingGoal',
]


def __getattr__(name):
    if name == 'EPUBParser':
        from .epub_parser import EPUBParser
        return EPUBParser
    elif name == 'PDFTracker':
        from .pdf_tracker import PDFTracker
        return PDFTracker
    elif name == 'MOBITracker':
        from .mobi_tracker import MOBITracker
        return MOBITracker
    elif name == 'ActivityMonitor':
        from .activity_monitor import ActivityMonitor
        return ActivityMonitor
    elif name == 'ReadingVisualizer':
        from .visualization import ReadingVisualizer
        return ReadingVisualizer
    elif name == 'GoalManager':
        from .goal_manager import GoalManager
        return GoalManager
    elif name == 'ReadingTracker':
        from .tracker import ReadingTracker
        return ReadingTracker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
