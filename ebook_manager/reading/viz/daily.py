from datetime import datetime
from typing import List, Dict
import numpy as np
import matplotlib.dates as mdates

from .base import ChartBase


class DailyChart(ChartBase):
    def plot_daily_reading_minutes(self, daily_data: List[Dict], title: str = "每日阅读时长") -> str:
        fig, ax = self._setup_figure((14, 6))

        dates = []
        minutes = []
        for item in daily_data:
            date_str = item.get('date', '')
            if date_str:
                dates.append(datetime.strptime(date_str, '%Y-%m-%d'))
                minutes.append(item.get('duration', 0) // 60)

        if not dates:
            self._no_data_text(ax)
            return self._save_and_close(fig, 'daily_minutes.png')

        bars = ax.bar(dates, minutes, color=self.colors[0], alpha=0.8, width=0.6)

        for bar, minute in zip(bars, minutes):
            if minute > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                        '%d分钟' % minute, ha='center', va='bottom', fontsize=9)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('阅读时长（分钟）', fontsize=12)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 10)))
        ax.figure.autofmt_xdate(rotation=45, ha='right')

        avg_minutes = np.mean(minutes) if minutes else 0
        ax.axhline(y=avg_minutes, color=self.colors[2], linestyle='--',
                   label='平均值: %.0f分钟' % avg_minutes, alpha=0.8)
        ax.legend()

        return self._save_and_close(fig, 'daily_minutes.png')

    def plot_daily_pages_trend(self, stats: Dict, title: str = "每日阅读页数趋势") -> str:
        fig, ax = self._setup_figure((14, 6))

        daily_data = stats.get('daily_data', [])
        dates = []
        pages = []

        for item in daily_data:
            date_str = item.get('date', '')
            if date_str:
                dates.append(datetime.strptime(date_str, '%Y-%m-%d'))
                pages.append(item.get('pages', 0))

        if not dates:
            self._no_data_text(ax)
            return self._save_and_close(fig, 'daily_pages.png')

        ax.fill_between(dates, pages, alpha=0.3, color=self.colors[1])
        ax.plot(dates, pages, color=self.colors[1], marker='o',
                linewidth=2, markersize=6, label='阅读页数')

        avg_pages = np.mean(pages) if pages else 0
        ax.axhline(y=avg_pages, color=self.colors[2], linestyle='--',
                   label='平均每日: %.1f页' % avg_pages, alpha=0.8)

        for i, (date, page) in enumerate(zip(dates, pages)):
            if page > 0 and (i == 0 or i == len(dates) - 1 or page == max(pages)):
                ax.annotate('%d页' % page, (date, page),
                            textcoords="offset points", xytext=(0, 10),
                            ha='center', fontsize=9)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('阅读页数', fontsize=12)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.legend()
        ax.figure.autofmt_xdate(rotation=45, ha='right')

        return self._save_and_close(fig, 'daily_pages.png')
