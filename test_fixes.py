import sys
import time
import threading
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, '.')

from ebook_manager.reading.db.connection import DatabaseConnection
from ebook_manager.reading.db import ReadingDatabase

DatabaseConnection.reset_instance()
ReadingDatabase.reset_instance()


class TestPositionDebounce(unittest.TestCase):
    def setUp(self):
        DatabaseConnection.reset_instance()
        ReadingDatabase.reset_instance()
        self.db = ReadingDatabase(':memory:')
        from ebook_manager.reading.position_manager import PositionManager
        from ebook_manager.reading.models_ext import ReadingPosition
        self.pm = PositionManager(self.db)
        self.ReadingPosition = ReadingPosition
        self.book_id = self.db.add_book('test.mobi', 'Test', 'Author', 'mobi', 100, 50000, 10)

    def test_debounce_saves_latest_only(self):
        pos1 = self.ReadingPosition(book_id=self.book_id, file_path='test.mobi', file_format='mobi', page_number=1, percentage=0.01)
        pos2 = self.ReadingPosition(book_id=self.book_id, file_path='test.mobi', file_format='mobi', page_number=5, percentage=0.05)
        pos3 = self.ReadingPosition(book_id=self.book_id, file_path='test.mobi', file_format='mobi', page_number=10, percentage=0.10)

        self.pm.save(pos1)
        self.pm.save(pos2)
        self.pm.save(pos3)

        self.assertIsNone(self.db.get_position(self.book_id))

        time.sleep(2.0)

        saved = self.db.get_position(self.book_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.page_number, 10)
        self.assertEqual(saved.percentage, 0.10)

    def test_save_now_bypasses_debounce(self):
        pos = self.ReadingPosition(book_id=self.book_id, file_path='test.mobi', file_format='mobi', page_number=20, percentage=0.20)
        result = self.pm.save_now(pos)

        saved = self.db.get_position(self.book_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.page_number, 20)

    def test_stop_flushes_pending(self):
        pos = self.ReadingPosition(book_id=self.book_id, file_path='test.mobi', file_format='mobi', page_number=30, percentage=0.30)
        self.pm.save(pos)

        self.pm.stop()

        saved = self.db.get_position(self.book_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.page_number, 30)

    def tearDown(self):
        self.pm.stop()


class TestMOBIPageAnchorMapping(unittest.TestCase):
    def test_anchor_record_index_monotonic(self):
        from ebook_manager.reading.mobi_tracker import MOBITracker, MOBIPageAnchor
        tracker = MOBITracker.__new__(MOBITracker)
        tracker._loaded = True
        tracker._page_anchors = []
        tracker._total_pages = 5

        for i in range(5):
            tracker._page_anchors.append(MOBIPageAnchor(
                page_number=i, record_index=i + 1, record_offset=0,
                byte_position=100 * (i + 1), content_hash="hash%d" % i,
            ))

        for i in range(5):
            pos = tracker.get_position_from_page(i)
            self.assertEqual(pos.record_index, i + 1)
            self.assertEqual(pos.anchor.content_hash, "hash%d" % i)

    def test_find_page_by_record_index_binary_search(self):
        from ebook_manager.reading.mobi_tracker import MOBITracker, MOBIPageAnchor
        tracker = MOBITracker.__new__(MOBITracker)
        tracker._loaded = True
        tracker._total_pages = 5
        tracker._page_anchors = [
            MOBIPageAnchor(page_number=0, record_index=1, record_offset=0, byte_position=100, content_hash="h0"),
            MOBIPageAnchor(page_number=1, record_index=3, record_offset=0, byte_position=300, content_hash="h1"),
            MOBIPageAnchor(page_number=2, record_index=5, record_offset=0, byte_position=500, content_hash="h2"),
            MOBIPageAnchor(page_number=3, record_index=7, record_offset=0, byte_position=700, content_hash="h3"),
            MOBIPageAnchor(page_number=4, record_index=9, record_offset=0, byte_position=900, content_hash="h4"),
        ]

        self.assertEqual(tracker.find_page_by_record(1), 0)
        self.assertEqual(tracker.find_page_by_record(3), 1)
        self.assertEqual(tracker.find_page_by_record(5), 2)
        self.assertEqual(tracker.find_page_by_record(7), 3)
        self.assertEqual(tracker.find_page_by_record(9), 4)

        self.assertEqual(tracker.find_page_by_record(2), 0)
        self.assertEqual(tracker.find_page_by_record(4), 1)
        self.assertEqual(tracker.find_page_by_record(6), 2)
        self.assertEqual(tracker.find_page_by_record(8), 3)

    def test_find_page_by_hash(self):
        from ebook_manager.reading.mobi_tracker import MOBITracker, MOBIPageAnchor
        tracker = MOBITracker.__new__(MOBITracker)
        tracker._loaded = True
        tracker._total_pages = 3
        tracker._page_anchors = [
            MOBIPageAnchor(page_number=0, record_index=1, record_offset=0, byte_position=100, content_hash="abc123"),
            MOBIPageAnchor(page_number=1, record_index=2, record_offset=0, byte_position=200, content_hash="def456"),
            MOBIPageAnchor(page_number=2, record_index=3, record_offset=0, byte_position=300, content_hash="ghi789"),
        ]

        self.assertEqual(tracker.find_page_by_hash("def456"), 1)
        self.assertIsNone(tracker.find_page_by_hash("nonexistent"))

    def test_mobi_position_with_record_index_roundtrip(self):
        from ebook_manager.reading.mobi_tracker import MOBITracker, MOBIPageAnchor
        tracker = MOBITracker.__new__(MOBITracker)
        tracker._loaded = True
        tracker._total_pages = 3
        tracker._page_anchors = [
            MOBIPageAnchor(page_number=0, record_index=1, record_offset=0, byte_position=100, content_hash="aaa"),
            MOBIPageAnchor(page_number=1, record_index=3, record_offset=0, byte_position=300, content_hash="bbb"),
            MOBIPageAnchor(page_number=2, record_index=5, record_offset=0, byte_position=500, content_hash="ccc"),
        ]

        pos = tracker.get_position_from_record(3)
        self.assertEqual(pos.page_number, 1)
        self.assertEqual(pos.record_index, 3)
        self.assertEqual(pos.anchor.content_hash, "bbb")

        back = tracker.get_position_from_page(pos.page_number)
        self.assertEqual(back.record_index, 3)
        self.assertEqual(back.anchor.content_hash, "bbb")


class TestMOBIPositionPersistence(unittest.TestCase):
    def setUp(self):
        DatabaseConnection.reset_instance()
        ReadingDatabase.reset_instance()
        self.db = ReadingDatabase(':memory:')
        self.book_id = self.db.add_book('test.mobi', 'Test', 'Author', 'mobi', 100, 50000, 10)

    def test_mobi_fields_saved_and_loaded(self):
        from ebook_manager.reading.models_ext import ReadingPosition
        pos = ReadingPosition(
            book_id=self.book_id, file_path='test.mobi', file_format='mobi',
            page_number=5, percentage=0.25,
            mobi_record_index=7, mobi_byte_position=3500, mobi_content_hash='abc123def',
        )
        self.db.save_position(pos)

        loaded = self.db.get_position(self.book_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.page_number, 5)
        self.assertEqual(loaded.mobi_record_index, 7)
        self.assertEqual(loaded.mobi_byte_position, 3500)
        self.assertEqual(loaded.mobi_content_hash, 'abc123def')


class TestActivityMonitorGracePeriod(unittest.TestCase):
    def test_default_idle_threshold_180(self):
        from ebook_manager.reading.monitors.activity_monitor import ActivityMonitor
        monitor = ActivityMonitor()
        self.assertEqual(monitor.idle_threshold, 180)

    def test_default_focus_loss_grace_10(self):
        from ebook_manager.reading.monitors.activity_monitor import ActivityMonitor
        monitor = ActivityMonitor()
        self.assertEqual(monitor.focus_loss_grace, 10)

    def test_pause_requires_confirm_ticks(self):
        from ebook_manager.reading.monitors.activity_monitor import ActivityMonitor, ActivityState
        monitor = ActivityMonitor(idle_threshold=5, heartbeat_interval=0.1, focus_loss_grace=1)

        monitor.state.is_active = True
        monitor.state.is_focused = True
        monitor.state.session_start_time = datetime.now()
        monitor._pause_pending_ticks = 0
        monitor._focus_lost_since = None
        monitor._idle_since = None

        monitor._pause_activity("test")
        self.assertFalse(monitor.state.is_active)
        self.assertEqual(monitor.state.pause_count, 1)

        self.assertEqual(monitor.PAUSE_CONFIRM_TICKS, 3)

    def test_resume_grace_deducts_from_pause(self):
        from ebook_manager.reading.monitors.activity_monitor import ActivityMonitor
        monitor = ActivityMonitor(idle_threshold=5, heartbeat_interval=0.1, focus_loss_grace=10)

        monitor.state.is_active = False
        monitor.state.last_pause_start = datetime.now() - timedelta(seconds=30)
        monitor.state.total_pause_seconds = 0

        monitor._resume_activity()

        self.assertEqual(monitor.state.total_pause_seconds, 20)
        self.assertTrue(monitor.state.is_active)

    def test_short_pause_entirely_graced(self):
        from ebook_manager.reading.monitors.activity_monitor import ActivityMonitor
        monitor = ActivityMonitor(idle_threshold=5, heartbeat_interval=0.1, focus_loss_grace=10)

        monitor.state.is_active = False
        monitor.state.last_pause_start = datetime.now() - timedelta(seconds=5)
        monitor.state.total_pause_seconds = 0

        monitor._resume_activity()

        self.assertEqual(monitor.state.total_pause_seconds, 0)

    def test_drain_write_queue_limited(self):
        from ebook_manager.reading.monitors.activity_monitor import ActivityMonitor
        monitor = ActivityMonitor()

        call_count = 0
        def mock_write():
            nonlocal call_count
            call_count += 1

        for _ in range(10):
            monitor.enqueue_write(mock_write)

        monitor._drain_write_queue()
        self.assertEqual(call_count, 5)


class TestActivityMonitorIntegration(unittest.TestCase):
    def test_full_session_lifecycle(self):
        from ebook_manager.reading.monitors.activity_monitor import ActivityMonitor
        monitor = ActivityMonitor(idle_threshold=5, heartbeat_interval=0.2, focus_loss_grace=2)

        monitor.start()
        time.sleep(1.0)

        self.assertTrue(monitor.state.is_active)

        stats = monitor.get_statistics()
        self.assertGreater(stats['heartbeat_ticks'], 0)

        result = monitor.stop()
        self.assertIn('effective_duration_seconds', result)
        self.assertIn('total_duration_seconds', result)
        self.assertGreater(result['total_duration_seconds'], 0)


class TestChapterForRecordMapping(unittest.TestCase):
    def test_chapter_mapping_with_bisect(self):
        from ebook_manager.reading.mobi_tracker import MOBITracker
        tracker = MOBITracker.__new__(MOBITracker)
        tracker._chapter_records = [1, 5, 10, 15]

        self.assertEqual(tracker._find_chapter_for_record(1), 0)
        self.assertEqual(tracker._find_chapter_for_record(3), 0)
        self.assertEqual(tracker._find_chapter_for_record(5), 1)
        self.assertEqual(tracker._find_chapter_for_record(12), 2)
        self.assertEqual(tracker._find_chapter_for_record(20), 3)

    def test_empty_chapters_returns_none(self):
        from ebook_manager.reading.mobi_tracker import MOBITracker
        tracker = MOBITracker.__new__(MOBITracker)
        tracker._chapter_records = []
        self.assertIsNone(tracker._find_chapter_for_record(5))


class TestDBMigration(unittest.TestCase):
    def test_migrate_adds_mobi_columns(self):
        from ebook_manager.reading.db.connection import DatabaseConnection as DC
        DC.reset_instance()
        ReadingDatabase.reset_instance()

        conn = DC(':memory:')

        with conn.connect() as c:
            cursor = c.cursor()
            cursor.execute("PRAGMA table_info(reading_positions)")
            columns = {row[1] for row in cursor.fetchall()}

        self.assertIn('mobi_record_index', columns)
        self.assertIn('mobi_byte_position', columns)
        self.assertIn('mobi_content_hash', columns)


if __name__ == '__main__':
    unittest.main(verbosity=2)
