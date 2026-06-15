from datetime import datetime, timedelta
from typing import Dict, List
import numpy as np
import matplotlib.dates as mdates

from .base import ChartBase


class PeriodChart(ChartBase):
    def plot_weekly_reading_statistics(self, stats: Dict, title: str = "本周阅读统计") -> str:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        fig.patch.set_facecolor('#fafbfc')

        daily_data = stats.get('daily_data', [])
        weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())

        week_data = []
        for i in range(7):
            day_date = start_of_week + timedelta(days=i)
            day_str = day_date.strftime('%Y-%m-%d')
            day_minutes = 0
            for item in daily_data:
                if item.get('date') == day_str:
                    day_minutes = item.get('duration', 0) // 60
                    break
            week_data.append(day_minutes)

        bars = ax1.bar(weekdays, week_data, color=self.colors[:7], alpha=0.8)
        for bar, minute in zip(bars, week_data):
            if minute > 0:
                ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 3,
                         '%dmin' % minute, ha='center', va='bottom', fontsize=9)

        ax1.set_title('本周每日阅读时长', fontsize=14, fontweight='bold', pad=15)
        ax1.set_ylabel('分钟', fontsize=11)
        ax1.grid(axis='y', alpha=0.3, linestyle='--')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)

        labels = ['阅读', '其他']
        sizes = [stats.get('total_minutes', 0), max(0, 7 * 24 * 60 - stats.get('total_minutes', 0))]
        colors = [self.colors[0], '#e8e8e8']
        explode = (0.05, 0)

        wedges, texts, autotexts = ax2.pie(sizes, explode=explode, labels=labels, colors=colors,
                                            autopct='%1.1f%%', startangle=90)
        ax2.set_title('本周时间分配', fontsize=14, fontweight='bold', pad=15)

        total_minutes = stats.get('total_minutes', 0)
        total_hours = total_minutes // 60
        remaining_minutes = total_minutes % 60
        fig.suptitle('%s - 总计 %d小时%d分钟' % (title, total_hours, remaining_minutes),
                     fontsize=16, fontweight='bold', y=0.98)

        filepath = self.output_dir / 'weekly_statistics.png'
        fig.tight_layout()
        fig.savefig(filepath, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close(fig)
        return str(filepath)

    def plot_monthly_reading_statistics(self, stats: Dict, title: str = "本月阅读统计") -> str:
        fig, ax = self._setup_figure((14, 7))

        daily_data = stats.get('daily_data', [])
        dates = []
        minutes = []
        pages = []

        for item in daily_data:
            date_str = item.get('date', '')
            if date_str:
                dates.append(datetime.strptime(date_str, '%Y-%m-%d'))
                minutes.append(item.get('duration', 0) // 60)
                pages.append(item.get('pages', 0))

        if not dates:
            self._no_data_text(ax)
            return self._save_and_close(fig, 'monthly_statistics.png')

        ax2 = ax.twinx()

        ax.bar(dates, minutes, color=self.colors[0], alpha=0.7, label='阅读时长(分钟)', width=0.6)
        ax2.plot(dates, pages, color=self.colors[1], marker='o',
                 linewidth=2, markersize=6, label='阅读页数')

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('阅读时长（分钟）', fontsize=12, color=self.colors[0])
        ax2.set_ylabel('阅读页数', fontsize=12, color=self.colors[1])

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 15)))
        ax.figure.autofmt_xdate(rotation=45, ha='right')

        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

        return self._save_and_close(fig, 'monthly_statistics.png')
