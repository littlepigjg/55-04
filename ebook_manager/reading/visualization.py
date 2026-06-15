import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import numpy as np
from pathlib import Path


rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
rcParams['axes.unicode_minus'] = False


class ReadingVisualizer:
    def __init__(self, output_dir: Optional[str] = None):
        if output_dir is None:
            output_dir = Path.home() / ".ebook_reader_tracker" / "charts"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.color_palette = [
            '#4a9eff', '#52c41a', '#faad14', '#f5222d', 
            '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16'
        ]

    def _setup_figure(self, size: Tuple[int, int] = (12, 6)) -> Tuple[plt.Figure, plt.Axes]:
        fig, ax = plt.subplots(figsize=size, dpi=100)
        fig.patch.set_facecolor('#fafbfc')
        ax.set_facecolor('#ffffff')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        return fig, ax

    def _save_and_close(self, fig: plt.Figure, filename: str) -> str:
        filepath = self.output_dir / filename
        fig.tight_layout()
        fig.savefig(filepath, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close(fig)
        return str(filepath)

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
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', transform=ax.transAxes, fontsize=16, color='#999')
            return self._save_and_close(fig, 'daily_minutes.png')
        
        bars = ax.bar(dates, minutes, color=self.color_palette[0], alpha=0.8, width=0.6)
        
        for bar, minute in zip(bars, minutes):
            if minute > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                       f'{minute}分钟', ha='center', va='bottom', fontsize=9)
        
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('阅读时长（分钟）', fontsize=12)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 10)))
        plt.xticks(rotation=45, ha='right')
        
        avg_minutes = np.mean(minutes) if minutes else 0
        ax.axhline(y=avg_minutes, color=self.color_palette[2], linestyle='--', 
                  label=f'平均值: {avg_minutes:.0f}分钟', alpha=0.8)
        ax.legend()
        
        return self._save_and_close(fig, 'daily_minutes.png')

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
        
        bars = ax1.bar(weekdays, week_data, color=self.color_palette[:7], alpha=0.8)
        for bar, minute in zip(bars, week_data):
            if minute > 0:
                ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 3,
                        f'{minute}min', ha='center', va='bottom', fontsize=9)
        
        ax1.set_title('本周每日阅读时长', fontsize=14, fontweight='bold', pad=15)
        ax1.set_ylabel('分钟', fontsize=11)
        ax1.grid(axis='y', alpha=0.3, linestyle='--')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        
        labels = ['阅读', '其他']
        sizes = [stats.get('total_minutes', 0), max(0, 7 * 24 * 60 - stats.get('total_minutes', 0))]
        colors = [self.color_palette[0], '#e8e8e8']
        explode = (0.05, 0)
        
        wedges, texts, autotexts = ax2.pie(sizes, explode=explode, labels=labels, colors=colors,
                                           autopct='%1.1f%%', startangle=90)
        ax2.set_title('本周时间分配', fontsize=14, fontweight='bold', pad=15)
        
        total_minutes = stats.get('total_minutes', 0)
        total_hours = total_minutes // 60
        remaining_minutes = total_minutes % 60
        fig.suptitle(f'{title} - 总计 {total_hours}小时{remaining_minutes}分钟', 
                     fontsize=16, fontweight='bold', y=0.98)
        
        return self._save_and_close(fig, 'weekly_statistics.png')

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
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', transform=ax.transAxes, fontsize=16, color='#999')
            return self._save_and_close(fig, 'monthly_statistics.png')
        
        ax2 = ax.twinx()
        
        bars = ax.bar(dates, minutes, color=self.color_palette[0], alpha=0.7, label='阅读时长(分钟)', width=0.6)
        line = ax2.plot(dates, pages, color=self.color_palette[1], marker='o', 
                       linewidth=2, markersize=6, label='阅读页数')
        
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('阅读时长（分钟）', fontsize=12, color=self.color_palette[0])
        ax2.set_ylabel('阅读页数', fontsize=12, color=self.color_palette[1])
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 15)))
        plt.xticks(rotation=45, ha='right')
        
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        return self._save_and_close(fig, 'monthly_statistics.png')

    def plot_hourly_heatmap(self, hourly_data: List[Dict], title: str = "阅读高峰时段分布") -> str:
        fig, ax = self._setup_figure((14, 5))
        
        hours = list(range(24))
        hour_names = [f'{h:02d}:00' for h in hours]
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
                       f'{minute}min', ha='center', va='bottom', fontsize=8)
        
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('时段', fontsize=12)
        ax.set_ylabel('阅读时长（分钟）', fontsize=12)
        ax.set_xticks(hours)
        ax.set_xticklabels(hour_names, rotation=45, ha='right')
        
        peak_hour = np.argmax(minutes_by_hour) if minutes_by_hour else 0
        peak_minutes = minutes_by_hour[peak_hour] if minutes_by_hour else 0
        ax.axvline(x=peak_hour, color=self.color_palette[3], linestyle='--', alpha=0.7,
                  label=f'高峰时段 {peak_hour:02d}:00 ({peak_minutes}分钟)')
        ax.legend()
        
        return self._save_and_close(fig, 'hourly_heatmap.png')

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
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', transform=ax.transAxes, fontsize=16, color='#999')
            return self._save_and_close(fig, 'reading_speed.png')
        
        ax.plot(dates, speeds, color=self.color_palette[0], marker='o', 
                linewidth=2, markersize=8, label='阅读速度')
        
        if len(speeds) >= 3:
            z = np.polyfit(range(len(dates)), speeds, 1)
            p = np.poly1d(z)
            ax.plot(dates, p(range(len(dates))), color=self.color_palette[3], 
                   linestyle='--', linewidth=2, alpha=0.8,
                   label=f'趋势线 (斜率: {z[0]:.1f})')
        
        for i, (date, speed) in enumerate(zip(dates, speeds)):
            if speed > 0:
                ax.annotate(f'{speed:.0f}', (date, speed),
                           textcoords="offset points", xytext=(0, 10),
                           ha='center', fontsize=9)
        
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('阅读速度（字/分钟）', fontsize=12)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.legend()
        plt.xticks(rotation=45, ha='right')
        
        return self._save_and_close(fig, 'reading_speed.png')

    def plot_books_completion(self, books_data: List[Dict], title: str = "书籍完成进度") -> str:
        fig, ax = self._setup_figure((12, max(6, len(books_data) * 0.8)))
        
        if not books_data:
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', transform=ax.transAxes, fontsize=16, color='#999')
            return self._save_and_close(fig, 'books_completion.png')
        
        books_data_sorted = sorted(books_data, key=lambda x: x.get('progress', 0), reverse=True)
        titles = [item.get('title', '未知')[:20] for item in books_data_sorted]
        progresses = [item.get('progress', 0) * 100 for item in books_data_sorted]
        days = [item.get('days_to_complete', 0) for item in books_data_sorted]
        
        y_pos = np.arange(len(titles))
        
        bars = ax.barh(y_pos, progresses, color=self.color_palette[0], alpha=0.8, height=0.6)
        
        for i, (bar, progress, day) in enumerate(zip(bars, progresses, days)):
            day_text = f' (用时{day}天)' if day > 0 else ''
            ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                   f'{progress:.1f}%{day_text}', va='center', fontsize=10)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(titles, fontsize=10)
        ax.invert_yaxis()
        ax.set_xlim(0, 110)
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('完成进度（%）', fontsize=12)
        
        return self._save_and_close(fig, 'books_completion.png')

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
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', transform=ax.transAxes, fontsize=16, color='#999')
            return self._save_and_close(fig, 'daily_pages.png')
        
        ax.fill_between(dates, pages, alpha=0.3, color=self.color_palette[1])
        ax.plot(dates, pages, color=self.color_palette[1], marker='o', 
                linewidth=2, markersize=6, label='阅读页数')
        
        avg_pages = np.mean(pages) if pages else 0
        ax.axhline(y=avg_pages, color=self.color_palette[2], linestyle='--',
                  label=f'平均每日: {avg_pages:.1f}页', alpha=0.8)
        
        for i, (date, page) in enumerate(zip(dates, pages)):
            if page > 0 and (i == 0 or i == len(dates) - 1 or page == max(pages)):
                ax.annotate(f'{page}页', (date, page),
                           textcoords="offset points", xytext=(0, 10),
                           ha='center', fontsize=9)
        
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('阅读页数', fontsize=12)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.legend()
        plt.xticks(rotation=45, ha='right')
        
        return self._save_and_close(fig, 'daily_pages.png')

    def plot_goal_progress(self, goals_data: List[Dict], title: str = "阅读目标完成情况") -> str:
        fig, ax = self._setup_figure((14, max(5, len(goals_data) * 1.2)))
        
        if not goals_data:
            ax.text(0.5, 0.5, '暂无目标', ha='center', va='center', transform=ax.transAxes, fontsize=16, color='#999')
            return self._save_and_close(fig, 'goal_progress.png')
        
        y_pos = np.arange(len(goals_data))
        bar_height = 0.4
        
        for i, goal in enumerate(goals_data):
            target = goal.get('target', 1)
            current = goal.get('current', 0)
            progress = min(current / target, 1.0) if target > 0 else 0
            
            ax.barh(y_pos[i] + bar_height/2, 100, height=bar_height, 
                   color='#e8e8e8', alpha=0.5)
            
            color = self.color_palette[1] if progress >= 1 else self.color_palette[0]
            ax.barh(y_pos[i] + bar_height/2, progress * 100, height=bar_height,
                   color=color, alpha=0.9)
            
            desc = goal.get('description', f'目标{i+1}')
            status = '✓ 已完成' if progress >= 1 else f'{current}/{target}'
            ax.text(2, y_pos[i] + bar_height/2, f'{desc}', va='center', fontsize=11, fontweight='bold')
            ax.text(102, y_pos[i] + bar_height/2, f'{progress*100:.1f}% ({status})', 
                   va='center', fontsize=10, color='#333')
        
        ax.set_yticks(y_pos + bar_height/2)
        ax.set_yticklabels(['' for _ in goals_data])
        ax.invert_yaxis()
        ax.set_xlim(0, 115)
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('完成进度（%）', fontsize=12)
        
        return self._save_and_close(fig, 'goal_progress.png')

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
