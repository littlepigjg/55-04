from datetime import datetime
from typing import List, Dict
import numpy as np
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from .base import ChartBase


class HeatmapChart(ChartBase):
    def plot_hourly_heatmap(self, hourly_data: List[Dict], title: str = "阅读高峰时段分布") -> str:
        fig, ax = self._setup_figure((14, 5))

        hours = list(range(24))
        hour_names = ['%02d:00' % h for h in hours]
        minutes_by_hour = [0] * 24

        for item in hourly_data:
            hour = int(item.get('hour', 0))
            if 0 <= hour < 24:
                minutes_by_hour[hour] += item.get('duration', 0) // 60

        max_minutes = max(minutes_by_hour) if minutes_by_hour else 1

        colors = plt.cm.Blues(np.array(minutes_by_hour) / max_minutes if max_minutes > 0 else np.zeros(24))
        bars = ax.bar(hours, minutes_by_hour, color=colors, width=0.8, edgecolor='white')

        for i, (bar, minute) in enumerate(zip(bars, minutes_by_hour)):
            if minute > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(5, max_minutes * 0.02),
                        '%dmin' % minute, ha='center', va='bottom', fontsize=8)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('时段', fontsize=12)
        ax.set_ylabel('阅读时长（分钟）', fontsize=12)
        ax.set_xticks(hours)
        ax.set_xticklabels(hour_names, rotation=45, ha='right')

        peak_hour = int(np.argmax(minutes_by_hour)) if minutes_by_hour else 0
        peak_minutes = minutes_by_hour[peak_hour] if minutes_by_hour else 0
        ax.axvline(x=peak_hour, color=self.colors[3], linestyle='--', alpha=0.7,
                   label='高峰时段 %02d:00 (%d分钟)' % (peak_hour, peak_minutes))
        ax.legend()

        return self._save_and_close(fig, 'hourly_heatmap.png')


class SpeedChart(ChartBase):
    def plot_reading_speed_curve(self, speed_data: List[Dict], title: str = "阅读速度变化曲线") -> str:
        fig, ax = self._setup_figure((14, 6))

        dates = []
        speeds = []

        for item in speed_data:
            date_str = item.get('date', '')
            if date_str:
                dates.append(datetime.strptime(date_str, '%Y-%m-%d'))
                speeds.append(item.get('speed', 0))

        if not dates:
            self._no_data_text(ax)
            return self._save_and_close(fig, 'reading_speed.png')

        ax.plot(dates, speeds, color=self.colors[0], marker='o',
                linewidth=2, markersize=8, label='阅读速度')

        if len(speeds) >= 3:
            z = np.polyfit(range(len(dates)), speeds, 1)
            p = np.poly1d(z)
            ax.plot(dates, p(range(len(dates))), color=self.colors[3],
                    linestyle='--', linewidth=2, alpha=0.8,
                    label='趋势线 (斜率: %.1f)' % z[0])

        for date, speed in zip(dates, speeds):
            if speed > 0:
                ax.annotate('%.0f' % speed, (date, speed),
                            textcoords="offset points", xytext=(0, 10),
                            ha='center', fontsize=9)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('阅读速度（字/分钟）', fontsize=12)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.legend()
        ax.figure.autofmt_xdate(rotation=45, ha='right')

        return self._save_and_close(fig, 'reading_speed.png')
