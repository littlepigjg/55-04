from typing import List, Dict
import numpy as np

from .base import ChartBase


class ProgressChart(ChartBase):
    def plot_books_completion(self, books_data: List[Dict], title: str = "书籍完成进度") -> str:
        fig, ax = self._setup_figure((12, max(6, len(books_data) * 0.8)))

        if not books_data:
            self._no_data_text(ax)
            return self._save_and_close(fig, 'books_completion.png')

        books_data_sorted = sorted(books_data, key=lambda x: x.get('progress', 0), reverse=True)
        titles = [item.get('title', '未知')[:20] for item in books_data_sorted]
        progresses = [item.get('progress', 0) * 100 for item in books_data_sorted]
        days = [item.get('days_to_complete', 0) for item in books_data_sorted]

        y_pos = np.arange(len(titles))

        bars = ax.barh(y_pos, progresses, color=self.colors[0], alpha=0.8, height=0.6)

        for bar, progress, day in zip(bars, progresses, days):
            day_text = ' (用时%d天)' % day if day > 0 else ''
            ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                    '%.1f%%%s' % (progress, day_text), va='center', fontsize=10)

        ax.set_yticks(y_pos)
        ax.set_yticklabels(titles, fontsize=10)
        ax.invert_yaxis()
        ax.set_xlim(0, 110)
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('完成进度（%）', fontsize=12)

        return self._save_and_close(fig, 'books_completion.png')

    def plot_goal_progress(self, goals_data: List[Dict], title: str = "阅读目标完成情况") -> str:
        fig, ax = self._setup_figure((14, max(5, len(goals_data) * 1.2)))

        if not goals_data:
            self._no_data_text(ax)
            return self._save_and_close(fig, 'goal_progress.png')

        y_pos = np.arange(len(goals_data))
        bar_height = 0.4

        for i, goal in enumerate(goals_data):
            target = goal.get('target', 1)
            current = goal.get('current', 0)
            progress = min(current / target, 1.0) if target > 0 else 0

            ax.barh(y_pos[i] + bar_height / 2, 100, height=bar_height,
                    color='#e8e8e8', alpha=0.5)

            color = self.colors[1] if progress >= 1 else self.colors[0]
            ax.barh(y_pos[i] + bar_height / 2, progress * 100, height=bar_height,
                    color=color, alpha=0.9)

            desc = goal.get('description', '目标%d' % (i + 1))
            status = '✓ 已完成' if progress >= 1 else '%d/%d' % (current, target)
            ax.text(2, y_pos[i] + bar_height / 2, desc, va='center', fontsize=11, fontweight='bold')
            ax.text(102, y_pos[i] + bar_height / 2, '%.1f%% (%s)' % (progress * 100, status),
                    va='center', fontsize=10, color='#333')

        ax.set_yticks(y_pos + bar_height / 2)
        ax.set_yticklabels(['' for _ in goals_data])
        ax.invert_yaxis()
        ax.set_xlim(0, 115)
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('完成进度（%）', fontsize=12)

        return self._save_and_close(fig, 'goal_progress.png')
