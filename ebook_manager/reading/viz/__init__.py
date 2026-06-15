from pathlib import Path
from typing import Dict, List, Optional

try:
    from .base import ChartBase, COLOR_PALETTE
    from .daily import DailyChart
    from .period import PeriodChart
    from .analysis import HeatmapChart, SpeedChart
    from .progress import ProgressChart
    _HAS_MATPLOTLIB = True

    class ReadingVisualizer(ChartBase, DailyChart, PeriodChart, HeatmapChart, SpeedChart, ProgressChart):
        def __init__(self, output_dir: Optional[str] = None):
            if output_dir is None:
                output_dir = Path.home() / ".ebook_reader_tracker" / "charts"
            super().__init__(Path(output_dir), COLOR_PALETTE)

        def generate_dashboard(self, stats: Dict, goals: List[Dict], books: List[Dict],
                               speed_data: Optional[List[Dict]] = None) -> Dict[str, str]:
            charts = {}

            charts['daily_minutes'] = self.plot_daily_reading_minutes(
                stats.get('daily_data', []),
                '每日阅读时长统计'
            )

            charts['weekly_stats'] = self.plot_weekly_reading_statistics(
                stats,
                '本周阅读概览'
            )

            charts['monthly_stats'] = self.plot_monthly_reading_statistics(
                stats,
                '本月阅读统计'
            )

            charts['hourly_heatmap'] = self.plot_hourly_heatmap(
                stats.get('hourly_data', []),
                '阅读高峰时段分布'
            )

            if speed_data:
                charts['reading_speed'] = self.plot_reading_speed_curve(
                    speed_data,
                    '阅读速度变化曲线'
                )

            charts['books_completion'] = self.plot_books_completion(
                books,
                '书籍完成进度'
            )

            charts['daily_pages'] = self.plot_daily_pages_trend(
                stats,
                '每日阅读页数趋势'
            )

            charts['goal_progress'] = self.plot_goal_progress(
                goals,
                '阅读目标完成情况'
            )

            return charts

except ImportError:
    _HAS_MATPLOTLIB = False

    class ReadingVisualizer:
        def __init__(self, output_dir: Optional[str] = None):
            pass

        def generate_dashboard(self, stats: Dict, goals: List[Dict], books: List[Dict],
                               speed_data: Optional[List[Dict]] = None) -> Dict[str, str]:
            return {}
