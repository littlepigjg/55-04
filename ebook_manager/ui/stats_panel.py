from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTabWidget, QComboBox, QDateEdit, QFileDialog,
    QMessageBox, QScrollArea, QGridLayout, QFrame, QDialog,
    QSpinBox, QLineEdit, QFormLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QDate, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from ..reading.tracker import ReadingTracker
from ..reading.exporter import DataExporter
from ..models import BookMeta


class StatCard(QFrame):
    def __init__(self, title: str, value: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            StatCard {
                background: white;
                border-radius: 12px;
                border: 1px solid #e8e8e8;
            }
            StatCard:hover {
                border-color: #4a9eff;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666; font-size: 13px;")
        layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setStyleSheet("color: #1a1a1a; font-size: 28px; font-weight: bold;")
        layout.addWidget(value_label)
        
        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setStyleSheet("color: #999; font-size: 12px;")
            layout.addWidget(sub_label)


class GoalProgressWidget(QWidget):
    def __init__(self, goal_data: Dict, parent=None):
        super().__init__(parent)
        self.goal_data = goal_data
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        header = QHBoxLayout()
        
        desc_label = QLabel(goal_data.get('description', ''))
        desc_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(desc_label)
        
        trend = goal_data.get('trend', 'stable')
        trend_text = {'ahead': '✓ 超前', 'behind': '⚠ 落后', 'stable': '→ 正常'}[trend]
        trend_color = {'ahead': '#52c41a', 'behind': '#faad14', 'stable': '#4a9eff'}[trend]
        trend_label = QLabel(trend_text)
        trend_label.setStyleSheet(f"color: {trend_color}; font-size: 12px; padding: 2px 8px; "
                                   f"background: {trend_color}22; border-radius: 4px;")
        header.addWidget(trend_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addLayout(header)
        
        progress_bar = QProgressBar()
        progress_bar.setMaximum(100)
        progress_bar.setValue(int(goal_data.get('percentage', 0)))
        progress_bar.setTextVisible(False)
        progress_bar.setFixedHeight(12)
        progress_bar.setStyleSheet("""
            QProgressBar {
                background: #f0f0f0;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background: #4a9eff;
                border-radius: 6px;
            }
        """)
        layout.addWidget(progress_bar)
        
        footer = QHBoxLayout()
        
        progress_text = f"{goal_data.get('current', 0)}/{goal_data.get('target', 0)}"
        progress_label = QLabel(progress_text)
        progress_label.setStyleSheet("color: #333; font-size: 13px;")
        footer.addWidget(progress_label)
        
        percentage = goal_data.get('percentage', 0)
        percent_label = QLabel(f"{percentage:.1f}%")
        percent_label.setStyleSheet("color: #4a9eff; font-weight: bold; font-size: 13px;")
        footer.addWidget(percent_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addLayout(footer)
        
        days_remaining = goal_data.get('days_remaining', 0)
        daily_needed = goal_data.get('estimated_daily', 0)
        if days_remaining > 0 and daily_needed > 0 and not goal_data.get('is_completed', False):
            info = QLabel(f"剩余 {days_remaining} 天，每日需完成约 {daily_needed:.1f}")
            info.setStyleSheet("color: #999; font-size: 11px;")
            layout.addWidget(info)
        
        self.setStyleSheet("""
            GoalProgressWidget {
                background: white;
                border-radius: 8px;
                border: 1px solid #e8e8e8;
            }
        """)


class GoalCreateDialog(QDialog):
    goal_created = pyqtSignal(dict)

    def __init__(self, templates: List[Dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("创建阅读目标")
        self.setMinimumWidth(400)
        
        self.templates = templates
        
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.template_combo = QComboBox()
        for t in templates:
            self.template_combo.addItem(t['name'], t)
        self.template_combo.currentIndexChanged.connect(self._on_template_changed)
        form.addRow("目标类型:", self.template_combo)
        
        self.target_spin = QSpinBox()
        self.target_spin.setRange(1, 10000)
        self.target_spin.setValue(5)
        form.addRow("目标数值:", self.target_spin)
        
        self.period_combo = QComboBox()
        self.period_combo.addItems(['每日', '每周', '每月', '每年', '自定义'])
        form.addRow("周期:", self.period_combo)
        
        self.description_edit = QLineEdit()
        form.addRow("描述:", self.description_edit)
        
        date_layout = QHBoxLayout()
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate().addDays(30))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("至"))
        date_layout.addWidget(self.end_date)
        form.addRow("日期范围:", date_layout)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self._on_template_changed(0)

    def _on_template_changed(self, index: int):
        template = self.template_combo.currentData()
        if template:
            self.target_spin.setValue(template['default_target'])
            
            period_map = {'daily': 0, 'weekly': 1, 'monthly': 2, 'yearly': 3, 'custom': 4}
            period_index = period_map.get(template['default_period'], 2)
            self.period_combo.setCurrentIndex(period_index)
            
            desc = template['description_template'].format(target=template['default_target'])
            self.description_edit.setText(desc)
            
            now = QDate.currentDate()
            if template['default_period'] == 'daily':
                self.end_date.setDate(now)
            elif template['default_period'] == 'weekly':
                self.end_date.setDate(now.addDays(6 - now.dayOfWeek() + 1))
            elif template['default_period'] == 'monthly':
                self.end_date.setDate(now.addMonths(1).addDays(-1))
            elif template['default_period'] == 'yearly':
                self.end_date.setDate(QDate(now.year(), 12, 31))

    def _on_accept(self):
        template = self.template_combo.currentData()
        period_map = {0: 'daily', 1: 'weekly', 2: 'monthly', 3: 'yearly', 4: 'custom'}
        
        goal_data = {
            'goal_type': template['goal_type'],
            'target_value': self.target_spin.value(),
            'period': period_map[self.period_combo.currentIndex()],
            'description': self.description_edit.text() or template['description_template'].format(
                target=self.target_spin.value()
            ),
            'start_date': self.start_date.date().toString('yyyy-MM-dd'),
            'end_date': self.end_date.date().toString('yyyy-MM-dd')
        }
        
        self.accept()
        self.goal_created.emit(goal_data)


class ReadingStatsPanel(QWidget):
    def __init__(self, tracker: ReadingTracker, parent=None):
        super().__init__(parent)
        self.tracker = tracker
        self.exporter = DataExporter(tracker.db)
        
        self._init_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_data)
        self._refresh_timer.start(5000)
        
        self.refresh_data()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        
        header = QHBoxLayout()
        title = QLabel("📊 阅读统计")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        self.period_combo = QComboBox()
        self.period_combo.addItems(['本周', '本月', '近30天', '全部'])
        self.period_combo.currentIndexChanged.connect(self.refresh_data)
        header.addWidget(self.period_combo)
        
        export_btn = QPushButton("📥 导出数据")
        export_btn.clicked.connect(self._on_export)
        header.addWidget(export_btn)
        
        main_layout.addLayout(header)
        
        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(12)
        main_layout.addLayout(self.stats_grid)
        
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background: white;
                padding: 8px 16px;
                margin-right: 4px;
                border-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #4a9eff;
                color: white;
            }
        """)
        
        tabs.addTab(self._create_charts_tab(), "📈 数据图表")
        tabs.addTab(self._create_goals_tab(), "🎯 阅读目标")
        tabs.addTab(self._create_books_tab(), "📚 书籍进度")
        
        main_layout.addWidget(tabs)

    def _create_charts_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        content = QWidget()
        self.charts_layout = QVBoxLayout(content)
        self.charts_layout.setSpacing(16)
        
        self.chart_labels = {}
        for chart_name in ['daily_minutes', 'weekly_stats', 'monthly_stats', 
                          'hourly_heatmap', 'daily_pages', 'reading_speed']:
            label = QLabel("加载中...")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumHeight(200)
            label.setStyleSheet("""
                QLabel {
                    background: white;
                    border-radius: 8px;
                    border: 1px solid #e8e8e8;
                    padding: 16px;
                }
            """)
            self.chart_labels[chart_name] = label
            self.charts_layout.addWidget(label)
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return widget

    def _create_goals_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        header = QHBoxLayout()
        goals_title = QLabel("阅读目标")
        goals_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(goals_title)
        header.addStretch()
        
        add_goal_btn = QPushButton("+ 新建目标")
        add_goal_btn.setStyleSheet("""
            QPushButton {
                background: #4a9eff;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #3a8eef; }
        """)
        add_goal_btn.clicked.connect(self._on_add_goal)
        header.addWidget(add_goal_btn)
        
        layout.addLayout(header)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        content = QWidget()
        self.goals_layout = QVBoxLayout(content)
        self.goals_layout.setSpacing(12)
        self.goals_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return widget

    def _create_books_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        header = QHBoxLayout()
        books_title = QLabel("书籍阅读进度")
        books_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(books_title)
        header.addStretch()
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh_books)
        header.addWidget(refresh_btn)
        
        layout.addLayout(header)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        self.books_content = QWidget()
        self.books_layout = QVBoxLayout(self.books_content)
        self.books_layout.setSpacing(12)
        self.books_layout.addStretch()
        
        scroll.setWidget(self.books_content)
        layout.addWidget(scroll)
        
        return widget

    def refresh_data(self):
        self._refresh_stats_cards()
        self._refresh_charts()
        self._refresh_goals()
        self._refresh_books()

    def _refresh_stats_cards(self):
        for i in reversed(range(self.stats_grid.count())):
            self.stats_grid.itemAt(i).widget().setParent(None)
        
        period = self._get_period()
        stats = self.tracker.get_statistics(period)
        
        cards = [
            ("总阅读时长", f"{stats['total_hours']}h {stats['total_minutes'] % 60}m", "累计有效阅读时间"),
            ("阅读书籍", f"{stats['books_read']} 本", "本周期内阅读的书籍"),
            ("阅读页数", f"{stats['total_pages']} 页", "累计阅读页数"),
            ("阅读字数", f"{stats['total_words']:,} 字", "累计阅读字数"),
        ]
        
        for i, (title, value, subtitle) in enumerate(cards):
            card = StatCard(title, value, subtitle)
            self.stats_grid.addWidget(card, i // 2, i % 2)

    def _refresh_charts(self):
        try:
            period = self._get_period()
            charts = self.tracker.generate_charts(period)
            
            for chart_name, chart_path in charts.items():
                if chart_name in self.chart_labels:
                    pixmap = QPixmap(chart_path)
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaledToWidth(
                            self.chart_labels[chart_name].width() - 32,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self.chart_labels[chart_name].setPixmap(scaled_pixmap)
                        self.chart_labels[chart_name].setText("")
        except Exception as e:
            pass

    def _refresh_goals(self):
        for i in reversed(range(self.goals_layout.count() - 1)):
            item = self.goals_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        
        goals = self.tracker.goal_manager.get_goals_for_ui()
        
        if not goals:
            empty_label = QLabel("暂无阅读目标，点击右上角\"新建目标\"开始设定")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet("color: #999; padding: 40px;")
            self.goals_layout.insertWidget(0, empty_label)
        else:
            for goal_data in goals:
                widget = GoalProgressWidget(goal_data)
                self.goals_layout.insertWidget(self.goals_layout.count() - 1, widget)

    def _refresh_books(self):
        for i in reversed(range(self.books_layout.count() - 1)):
            item = self.books_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        
        now = datetime.now()
        start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = now.strftime('%Y-%m-%d')
        
        books = self.tracker.db.get_books_in_range(start_date, end_date)
        
        if not books:
            empty_label = QLabel("暂无阅读记录")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet("color: #999; padding: 40px;")
            self.books_layout.insertWidget(0, empty_label)
            return
        
        for book in books:
            book_id = book['id']
            position = self.tracker.db.get_position(book_id)
            book_progress = self.tracker.db.get_book_progress(book_id)
            
            progress = position.percentage if position else 0.0
            progress_widget = self._create_book_progress_widget(
                book.get('title', '未知书籍'),
                book.get('author', ''),
                progress,
                book_progress
            )
            self.books_layout.insertWidget(self.books_layout.count() - 1, progress_widget)

    def _create_book_progress_widget(self, title: str, author: str, 
                                     progress: float, book_progress: Dict) -> QWidget:
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 8px;
                border: 1px solid #e8e8e8;
            }
        """)
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(title_label)
        
        if progress >= 0.95:
            status_label = QLabel("✓ 已完成")
            status_label.setStyleSheet("color: #52c41a; font-size: 12px;")
        elif progress > 0:
            status_label = QLabel("📖 阅读中")
            status_label.setStyleSheet("color: #4a9eff; font-size: 12px;")
        else:
            status_label = QLabel("⏳ 未开始")
            status_label.setStyleSheet("color: #999; font-size: 12px;")
        header.addWidget(status_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addLayout(header)
        
        if author:
            author_label = QLabel(f"作者: {author}")
            author_label.setStyleSheet("color: #666; font-size: 12px;")
            layout.addWidget(author_label)
        
        progress_bar = QProgressBar()
        progress_bar.setMaximum(100)
        progress_bar.setValue(int(progress * 100))
        progress_bar.setTextVisible(False)
        progress_bar.setFixedHeight(8)
        progress_bar.setStyleSheet("""
            QProgressBar {
                background: #f0f0f0;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: #52c41a;
                border-radius: 4px;
            }
        """)
        layout.addWidget(progress_bar)
        
        footer = QHBoxLayout()
        
        progress_text = f"进度: {progress * 100:.1f}%"
        footer.addWidget(QLabel(progress_text))
        
        total_minutes = book_progress.get('total_minutes', 0)
        if total_minutes > 0:
            hours = total_minutes // 60
            mins = total_minutes % 60
            time_text = f"用时: {hours}h{mins}m"
            footer.addWidget(QLabel(time_text))
        
        days = book_progress.get('days_to_complete')
        if days:
            days_text = f"周期: {days}天"
            footer.addWidget(QLabel(days_text))
        
        footer.addStretch()
        layout.addLayout(footer)
        
        return widget

    def _get_period(self) -> str:
        index = self.period_combo.currentIndex()
        return ['week', 'month', 'month', 'all'][index]

    def _on_export(self):
        now = datetime.now()
        default_name = f"阅读记录_{now.strftime('%Y%m%d')}.csv"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出阅读记录", 
            str(Path.home() / default_name),
            "CSV文件 (*.csv);;JSON文件 (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            if file_path.endswith('.json'):
                self.exporter.export_to_json(file_path)
            else:
                self.exporter.export_to_csv(file_path, include_details=True)
            
            QMessageBox.information(self, "导出成功", f"数据已导出到:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出失败: {str(e)}")

    def _on_add_goal(self):
        templates = self.tracker.goal_manager.get_goal_templates()
        dialog = GoalCreateDialog(templates, self)
        
        def create_goal(goal_data):
            try:
                goal_id = self.tracker.goal_manager.create_goal(
                    goal_type=goal_data['goal_type'],
                    target_value=goal_data['target_value'],
                    period=goal_data['period'],
                    description=goal_data['description'],
                    custom_start=goal_data['start_date'],
                    custom_end=goal_data['end_date']
                )
                QMessageBox.information(self, "创建成功", f"目标已创建！\nID: {goal_id}")
                self._refresh_goals()
            except Exception as e:
                QMessageBox.critical(self, "创建失败", f"创建目标失败: {str(e)}")
        
        dialog.goal_created.connect(create_goal)
        dialog.exec()

    def set_current_book(self, book: Optional[BookMeta]):
        pass
