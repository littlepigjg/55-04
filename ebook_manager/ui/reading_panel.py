from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QSlider, QSpinBox, QFormLayout, QGroupBox,
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from ..reading.tracker import ReadingTracker
from ..reading.database import ReadingPosition
from ..models import BookMeta


class ReadingControlPanel(QWidget):
    session_started = pyqtSignal(int)
    session_ended = pyqtSignal(dict)
    position_updated = pyqtSignal(object)

    def __init__(self, tracker: ReadingTracker, parent=None):
        super().__init__(parent)
        self.tracker = tracker
        self._current_book: Optional[BookMeta] = None
        self._is_tracking: bool = False
        
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_reading_state)
        self._update_timer.start(1000)
        
        self._init_ui()
        self._update_ui_state()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        
        title = QLabel("📖 阅读追踪")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        main_layout.addWidget(title)
        
        main_layout.addWidget(self._create_book_info_card())
        main_layout.addWidget(self._create_tracking_controls())
        main_layout.addWidget(self._create_position_controls())
        main_layout.addWidget(self._create_progress_card())
        main_layout.addWidget(self._create_activity_card())
        
        main_layout.addStretch()

    def _create_book_info_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 12px;
                border: 1px solid #e8e8e8;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        self.book_title_label = QLabel("请选择一本书开始阅读")
        self.book_title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        self.book_title_label.setWordWrap(True)
        layout.addWidget(self.book_title_label)
        
        self.book_author_label = QLabel("")
        self.book_author_label.setStyleSheet("font-size: 13px; color: #666;")
        layout.addWidget(self.book_author_label)
        
        self.book_format_label = QLabel("")
        self.book_format_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #4a9eff;
                background: #4a9eff22;
                padding: 2px 8px;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.book_format_label)
        
        return card

    def _create_tracking_controls(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 12px;
                border: 1px solid #e8e8e8;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        btn_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶ 开始阅读")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: #52c41a;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background: #49b017; }
            QPushButton:disabled { background: #ccc; }
        """)
        self.start_btn.clicked.connect(self._on_start_tracking)
        btn_layout.addWidget(self.start_btn, 2)
        
        self.pause_btn = QPushButton("⏸ 暂停")
        self.pause_btn.setMinimumHeight(40)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background: #faad14;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background: #d48806; }
            QPushButton:disabled { background: #ccc; }
        """)
        self.pause_btn.clicked.connect(self._on_pause_tracking)
        btn_layout.addWidget(self.pause_btn, 1)
        
        self.stop_btn = QPushButton("■ 结束")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #f5222d;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background: #d32029; }
            QPushButton:disabled { background: #ccc; }
        """)
        self.stop_btn.clicked.connect(self._on_stop_tracking)
        btn_layout.addWidget(self.stop_btn, 1)
        
        layout.addLayout(btn_layout)
        
        self.session_time_label = QLabel("⏱ 阅读时长: 00:00:00")
        self.session_time_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")
        self.session_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.session_time_label)
        
        self.status_label = QLabel("状态: 未开始")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 13px; color: #999;")
        layout.addWidget(self.status_label)
        
        return card

    def _create_position_controls(self) -> QGroupBox:
        group = QGroupBox("阅读位置")
        group.setStyleSheet("""
            QGroupBox {
                background: white;
                border: 1px solid #e8e8e8;
                border-radius: 12px;
                margin-top: 8px;
                padding-top: 16px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("进度:"))
        
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.setValue(0)
        self.progress_slider.setEnabled(False)
        self.progress_slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self.progress_slider, 1)
        
        self.progress_value_label = QLabel("0.0%")
        self.progress_value_label.setMinimumWidth(60)
        self.progress_value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        slider_layout.addWidget(self.progress_value_label)
        
        layout.addLayout(slider_layout)
        
        self.position_form = QFormLayout()
        self.position_form.setSpacing(8)
        
        self.chapter_label = QLabel("-")
        self.position_form.addRow("章节:", self.chapter_label)
        
        self.paragraph_label = QLabel("-")
        self.position_form.addRow("段落:", self.paragraph_label)
        
        self.page_label = QLabel("-")
        self.position_form.addRow("页码:", self.page_label)
        
        self.coords_label = QLabel("-")
        self.position_form.addRow("坐标:", self.coords_label)
        
        self.word_label = QLabel("-")
        self.position_form.addRow("字数:", self.word_label)
        
        layout.addLayout(self.position_form)
        
        update_layout = QHBoxLayout()
        
        self.chapter_spin = QSpinBox()
        self.chapter_spin.setRange(0, 10000)
        self.chapter_spin.setPrefix("章: ")
        self.chapter_spin.setEnabled(False)
        update_layout.addWidget(self.chapter_spin)
        
        self.paragraph_spin = QSpinBox()
        self.paragraph_spin.setRange(0, 10000)
        self.paragraph_spin.setPrefix("段: ")
        self.paragraph_spin.setEnabled(False)
        update_layout.addWidget(self.paragraph_spin)
        
        self.page_spin = QSpinBox()
        self.page_spin.setRange(0, 10000)
        self.page_spin.setPrefix("页: ")
        self.page_spin.setEnabled(False)
        update_layout.addWidget(self.page_spin)
        
        update_btn = QPushButton("更新位置")
        update_btn.setEnabled(False)
        update_btn.clicked.connect(self._on_update_position)
        update_layout.addWidget(update_btn)
        self.update_position_btn = update_btn
        
        layout.addLayout(update_layout)
        
        return group

    def _create_progress_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 12px;
                border: 1px solid #e8e8e8;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        header = QHBoxLayout()
        header.addWidget(QLabel("阅读进度"))
        header.addStretch()
        self.total_progress_label = QLabel("0.0%")
        self.total_progress_label.setStyleSheet("font-weight: bold; color: #4a9eff;")
        header.addWidget(self.total_progress_label)
        layout.addLayout(header)
        
        self.total_progress_bar = QProgressBar()
        self.total_progress_bar.setRange(0, 100)
        self.total_progress_bar.setValue(0)
        self.total_progress_bar.setTextVisible(False)
        self.total_progress_bar.setFixedHeight(10)
        self.total_progress_bar.setStyleSheet("""
            QProgressBar {
                background: #f0f0f0;
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background: linear-gradient(90deg, #4a9eff, #13c2c2);
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.total_progress_bar)
        
        stats_layout = QHBoxLayout()
        
        self.avg_speed_label = QLabel("速度: -\n字/分钟")
        self.avg_speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avg_speed_label.setStyleSheet("font-size: 12px; color: #666;")
        stats_layout.addWidget(self.avg_speed_label)
        
        self.session_pages_label = QLabel("本次阅读:\n0 页")
        self.session_pages_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.session_pages_label.setStyleSheet("font-size: 12px; color: #666;")
        stats_layout.addWidget(self.session_pages_label)
        
        self.remain_time_label = QLabel("预计剩余:\n-")
        self.remain_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.remain_time_label.setStyleSheet("font-size: 12px; color: #666;")
        stats_layout.addWidget(self.remain_time_label)
        
        layout.addLayout(stats_layout)
        
        return card

    def _create_activity_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 12px;
                border: 1px solid #e8e8e8;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        header = QHBoxLayout()
        header.addWidget(QLabel("活动监控"))
        header.addStretch()
        self.activity_status_label = QLabel("●")
        self.activity_status_label.setStyleSheet("color: #ccc; font-size: 20px;")
        header.addWidget(self.activity_status_label)
        layout.addLayout(header)
        
        activity_stats = QHBoxLayout()
        
        self.key_presses_label = QLabel("⌨ 0")
        activity_stats.addWidget(self.key_presses_label)
        
        self.clicks_label = QLabel("🖱 0")
        activity_stats.addWidget(self.clicks_label)
        
        self.scrolls_label = QLabel("📜 0")
        activity_stats.addWidget(self.scrolls_label)
        
        self.pauses_label = QLabel("⏸ 0")
        activity_stats.addWidget(self.pauses_label)
        
        layout.addLayout(activity_stats)
        
        return card

    def set_book(self, book: Optional[BookMeta]):
        self._current_book = book
        
        if book:
            self.book_title_label.setText(book.title or "未知书籍")
            self.book_author_label.setText(f"作者: {book.author}" if book.author else "")
            format_text = book.file_format.upper() if book.file_format else "未知"
            self.book_format_label.setText(format_text)
            
            position = self.tracker.db.get_position(
                self.tracker.db.add_book(
                    file_path=book.file_path,
                    title=book.title,
                    author=book.author,
                    file_format=book.file_format
                )
            )
            if position and position.percentage is not None:
                self._update_position_display(position)
        else:
            self.book_title_label.setText("请选择一本书开始阅读")
            self.book_author_label.setText("")
            self.book_format_label.setText("")
        
        self._update_ui_state()

    def _update_ui_state(self):
        has_book = self._current_book is not None
        
        self.start_btn.setEnabled(has_book and not self._is_tracking)
        self.pause_btn.setEnabled(self._is_tracking)
        self.stop_btn.setEnabled(self._is_tracking)
        
        self.progress_slider.setEnabled(self._is_tracking)
        self.update_position_btn.setEnabled(self._is_tracking)
        
        fmt = (self._current_book.file_format or "").lower() if self._current_book else ""
        is_epub = fmt == 'epub'
        is_pdf = fmt == 'pdf'
        
        self.chapter_spin.setEnabled(self._is_tracking and (is_epub or fmt == 'mobi'))
        self.paragraph_spin.setEnabled(self._is_tracking and is_epub)
        self.page_spin.setEnabled(self._is_tracking and is_pdf)
        
        if not self._is_tracking:
            self.status_label.setText("状态: 未开始")
            self.status_label.setStyleSheet("font-size: 13px; color: #999;")

    def _on_start_tracking(self):
        if not self._current_book:
            QMessageBox.warning(self, "提示", "请先选择一本书")
            return
        
        try:
            session_id = self.tracker.start_reading(
                self._current_book.file_path,
                self._current_book.title,
                self._current_book.author
            )
            
            self._is_tracking = True
            self._session_start_time = datetime.now()
            self._update_ui_state()
            
            self.status_label.setText("状态: 阅读中")
            self.status_label.setStyleSheet("font-size: 13px; color: #52c41a; font-weight: bold;")
            
            self.session_started.emit(session_id)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动阅读追踪失败: {str(e)}")

    def _on_pause_tracking(self):
        if not self._is_tracking:
            return
        
        state = self.tracker.get_activity_state()
        if state.is_active:
            self.tracker.pause_reading()
            self.pause_btn.setText("▶ 继续")
            self.status_label.setText("状态: 已暂停")
            self.status_label.setStyleSheet("font-size: 13px; color: #faad14; font-weight: bold;")
            self.activity_status_label.setStyleSheet("color: #faad14; font-size: 20px;")
        else:
            self.tracker.resume_reading()
            self.pause_btn.setText("⏸ 暂停")
            self.status_label.setText("状态: 阅读中")
            self.status_label.setStyleSheet("font-size: 13px; color: #52c41a; font-weight: bold;")
            self.activity_status_label.setStyleSheet("color: #52c41a; font-size: 20px;")

    def _on_stop_tracking(self):
        if not self._is_tracking:
            return
        
        reply = QMessageBox.question(
            self, "确认", "确定要结束本次阅读吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                result = self.tracker.end_reading()
                self._is_tracking = False
                self._update_ui_state()
                
                self.status_label.setText("状态: 已结束")
                self.status_label.setStyleSheet("font-size: 13px; color: #999;")
                
                self.activity_status_label.setStyleSheet("color: #ccc; font-size: 20px;")
                self.pause_btn.setText("⏸ 暂停")
                
                self._show_session_summary(result)
                
                self.session_ended.emit(result)
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"结束阅读追踪失败: {str(e)}")

    def _show_session_summary(self, result: Dict[str, Any]):
        duration = result.get('effective_duration', 0)
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        pages = result.get('pages_read', 0)
        words = result.get('words_read', 0)
        speed = result.get('reading_speed_wpm', 0)
        
        msg = f"""本次阅读统计:
        
📖 阅读时长: {time_str}
📄 阅读页数: {pages} 页
📝 阅读字数: {words:,} 字
⚡ 阅读速度: {speed:.0f} 字/分钟

        """
        
        QMessageBox.information(self, "阅读完成", msg)

    def _on_slider_changed(self, value: int):
        percentage = value / 1000.0
        self.progress_value_label.setText(f"{percentage * 100:.1f}%")
        
        if self._is_tracking and self._current_book:
            try:
                position = self.tracker.update_position_by_percentage(percentage)
                self._update_position_display(position)
            except Exception:
                pass

    def _on_update_position(self):
        if not self._is_tracking or not self._current_book:
            return
        
        fmt = (self._current_book.file_format or "").lower()
        
        try:
            if fmt == 'epub':
                chapter = self.chapter_spin.value()
                paragraph = self.paragraph_spin.value()
                position = self.tracker.update_position_epub(chapter, paragraph)
            elif fmt == 'pdf':
                page = self.page_spin.value()
                position = self.tracker.update_position_pdf(page)
            elif fmt == 'mobi':
                percentage = self.progress_slider.value() / 1000.0
                position = self.tracker.update_position_mobi(percentage)
            else:
                percentage = self.progress_slider.value() / 1000.0
                position = self.tracker.update_position_by_percentage(percentage)
            
            self._update_position_display(position)
            self.position_updated.emit(position)
            
        except Exception as e:
            QMessageBox.warning(self, "更新失败", f"更新位置失败: {str(e)}")

    def _update_position_display(self, position: ReadingPosition):
        if position.chapter is not None:
            chapter_text = f"{position.chapter}"
            if position.chapter_index is not None:
                chapter_text += f" (第{position.chapter_index + 1}章)"
            self.chapter_label.setText(chapter_text)
        else:
            self.chapter_label.setText("-")
        
        if position.paragraph_id is not None:
            para_text = position.paragraph_id
            if position.paragraph_index is not None:
                para_text += f" (第{position.paragraph_index + 1}段)"
            self.paragraph_label.setText(para_text)
        else:
            self.paragraph_label.setText("-")
        
        if position.page_number is not None:
            self.page_label.setText(f"第 {position.page_number + 1} 页")
            self.page_spin.setValue(position.page_number)
        else:
            self.page_label.setText("-")
        
        if position.page_x is not None and position.page_y is not None:
            self.coords_label.setText(f"({position.page_x:.0f}, {position.page_y:.0f})")
        else:
            self.coords_label.setText("-")
        
        if position.word_count is not None:
            self.word_label.setText(f"{position.word_count:,} 字")
        else:
            self.word_label.setText("-")
        
        if position.percentage is not None:
            progress_val = int(position.percentage * 1000)
            if self.progress_slider.value() != progress_val:
                self.progress_slider.blockSignals(True)
                self.progress_slider.setValue(progress_val)
                self.progress_slider.blockSignals(False)
            self.progress_value_label.setText(f"{position.percentage * 100:.1f}%")
            self.total_progress_bar.setValue(int(position.percentage * 100))
            self.total_progress_label.setText(f"{position.percentage * 100:.1f}%")

    def _update_reading_state(self):
        if not self._is_tracking:
            return
        
        state = self.tracker.get_activity_state()
        
        if state.is_active:
            self.activity_status_label.setStyleSheet("color: #52c41a; font-size: 20px;")
            if self.pause_btn.text() == "▶ 继续":
                self.pause_btn.setText("⏸ 暂停")
                self.status_label.setText("状态: 阅读中")
                self.status_label.setStyleSheet("font-size: 13px; color: #52c41a; font-weight: bold;")
        else:
            self.activity_status_label.setStyleSheet("color: #faad14; font-size: 20px;")
        
        if state.session_start_time:
            elapsed = state.total_effective_seconds
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            self.session_time_label.setText(f"⏱ 阅读时长: {hours:02d}:{minutes:02d}:{seconds:02d}")
        
        stats = self.tracker._activity_monitor.get_statistics()
        self.key_presses_label.setText(f"⌨ {stats['key_presses']}")
        self.clicks_label.setText(f"🖱 {stats['mouse_clicks']}")
        self.scrolls_label.setText(f"📜 {stats['scrolls']}")
        self.pauses_label.setText(f"⏸ {stats['pause_count']}")
        
        if self._current_book:
            book_progress = self.tracker.get_book_progress()
            position = book_progress.get('position', {})
            words = position.get('word_count', 0)
            elapsed = state.total_effective_seconds
            
            if elapsed > 0 and words > 0:
                speed = (words / elapsed) * 60
                self.avg_speed_label.setText(f"速度: {speed:.0f}\n字/分钟")
                
                total_words = self._get_total_words()
                if total_words > 0 and words < total_words:
                    remaining_words = total_words - words
                    remaining_minutes = remaining_words / speed if speed > 0 else 0
                    hours = int(remaining_minutes // 60)
                    mins = int(remaining_minutes % 60)
                    self.remain_time_label.setText(f"预计剩余:\n{hours}h{mins}m")
        
        if self._current_book and self._session_start_time:
            position = self.tracker.get_current_position()
            if position:
                elapsed = (datetime.now() - self._session_start_time).total_seconds()
                start_pos = getattr(self.tracker, '_session_start_position', None)
                start_words = start_pos.word_count if start_pos else 0
                session_words = (position.word_count or 0) - start_words
                self.session_pages_label.setText(f"本次阅读:\n{self.tracker._calculate_pages_read(start_pos, position)} 页")

    def _get_total_words(self) -> int:
        if not self._current_book:
            return 0
        
        with self.tracker.db._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT total_words FROM books WHERE file_path = ?",
                (self._current_book.file_path,)
            )
            row = cursor.fetchone()
            return row['total_words'] if row and row['total_words'] else 0

    def is_tracking(self) -> bool:
        return self._is_tracking
