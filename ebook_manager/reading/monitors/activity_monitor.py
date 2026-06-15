import threading
import time
import queue
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, List
from dataclasses import dataclass, field
from collections import deque
import logging
import os

from .idle_detector import SystemIdleDetector
from .focus_monitor import WindowFocusMonitor


@dataclass
class ActivityEvent:
    event_type: str
    timestamp: str
    details: Dict = field(default_factory=dict)


@dataclass
class ActivityState:
    is_active: bool = False
    is_focused: bool = False
    last_activity_time: Optional[datetime] = None
    session_start_time: Optional[datetime] = None
    total_effective_seconds: int = 0
    pause_count: int = 0
    total_pause_seconds: int = 0
    last_pause_start: Optional[datetime] = None
    system_idle_seconds: int = 0
    focus_lost_count: int = 0


class ActivityMonitor:
    def __init__(self,
                 idle_threshold: int = 60,
                 heartbeat_interval: float = 2.0,
                 focus_check_interval: float = 3.0,
                 activity_callback: Optional[Callable[[ActivityEvent], None]] = None,
                 state_callback: Optional[Callable[[ActivityState], None]] = None):
        self.idle_threshold = idle_threshold
        self.heartbeat_interval = heartbeat_interval
        self.focus_check_interval = focus_check_interval
        self.activity_callback = activity_callback
        self.state_callback = state_callback

        self.state = ActivityState()
        self._events: deque = deque(maxlen=500)
        self._idle_detector = SystemIdleDetector()
        self._our_pid = os.getpid()

        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._write_queue: queue.Queue = queue.Queue()

        self._heartbeat_count = 0
        self._focus_check_count = 0

    def _emit_event(self, event_type: str, details: Optional[Dict] = None):
        event = ActivityEvent(
            event_type=event_type,
            timestamp=datetime.now().isoformat(),
            details=details or {}
        )
        self._events.append(event)
        if self.activity_callback:
            try:
                self.activity_callback(event)
            except Exception as e:
                logging.error(f"activity_callback error: {e}")

    def _check_system_idle(self) -> int:
        try:
            return self._idle_detector.get_idle_seconds()
        except Exception:
            return 0

    def _check_window_focus(self) -> bool:
        try:
            return WindowFocusMonitor.is_our_window_active(self._our_pid)
        except Exception:
            return True

    def _heartbeat_loop(self):
        while not self._stop_event.is_set():
            try:
                self._heartbeat_count += 1
                now = datetime.now()

                idle_seconds = self._check_system_idle()
                self.state.system_idle_seconds = idle_seconds

                is_focused = self._check_window_focus()
                prev_focused = self.state.is_focused
                self.state.is_focused = is_focused

                if not is_focused and prev_focused:
                    self.state.focus_lost_count += 1
                    self._emit_event("focus_lost", {
                        "focus_lost_count": self.state.focus_lost_count
                    })

                if is_focused and not prev_focused:
                    self._emit_event("focus_gained", {
                        "idle_at_return": idle_seconds
                    })

                system_idle = idle_seconds >= self.idle_threshold
                app_unfocused = not is_focused

                if self.state.is_active:
                    if system_idle or app_unfocused:
                        self._pause_activity(
                            reason="system_idle" if system_idle else "focus_lost"
                        )
                else:
                    if not system_idle and is_focused:
                        self._resume_activity()

                if self.state.is_active and self.state.session_start_time:
                    elapsed = (now - self.state.session_start_time).total_seconds()
                    total_pause = self.state.total_pause_seconds
                    if self.state.last_pause_start:
                        current_pause = (now - self.state.last_pause_start).total_seconds()
                        total_pause += current_pause
                    self.state.total_effective_seconds = max(0, int(elapsed - total_pause))

                self._drain_write_queue()

                if self.state_callback:
                    try:
                        self.state_callback(ActivityState(**self.state.__dict__))
                    except Exception:
                        pass

            except Exception as e:
                logging.error(f"heartbeat error: {e}")

            self._stop_event.wait(self.heartbeat_interval)

    def _pause_activity(self, reason: str = "inactivity"):
        if not self.state.is_active:
            return
        self.state.is_active = False
        self.state.last_pause_start = datetime.now()
        self.state.pause_count += 1
        self._emit_event("pause", {
            "reason": reason,
            "pause_count": self.state.pause_count
        })

    def _resume_activity(self):
        if self.state.is_active:
            return
        if self.state.last_pause_start:
            pause_duration = (datetime.now() - self.state.last_pause_start).total_seconds()
            self.state.total_pause_seconds += int(pause_duration)
            self.state.last_pause_start = None
        self.state.is_active = True
        self.state.last_activity_time = datetime.now()
        self._emit_event("resume", {})

    def _drain_write_queue(self):
        while not self._write_queue.empty():
            try:
                func, args, kwargs = self._write_queue.get_nowait()
                func(*args, **kwargs)
            except Exception as e:
                logging.error(f"drain_write_queue error: {e}")

    def enqueue_write(self, func, *args, **kwargs):
        self._write_queue.put((func, args, kwargs))

    def start(self):
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return

        self._stop_event.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._heartbeat_thread.start()

        self.state.is_active = True
        self.state.is_focused = True
        self.state.session_start_time = datetime.now()
        self.state.last_activity_time = datetime.now()

        self._emit_event("session_start", {
            "monitoring": "system_idle + window_focus + heartbeat"
        })

    def stop(self) -> Dict:
        self._stop_event.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=3.0)

        self._drain_write_queue()

        session_end = datetime.now()
        if self.state.session_start_time:
            total_duration = int(
                (session_end - self.state.session_start_time).total_seconds()
            )
        else:
            total_duration = 0

        self._emit_event("session_end", {
            "total_duration": total_duration,
            "effective_duration": self.state.total_effective_seconds,
            "pause_count": self.state.pause_count,
            "total_pause_seconds": self.state.total_pause_seconds,
            "focus_lost_count": self.state.focus_lost_count,
            "heartbeat_ticks": self._heartbeat_count,
        })

        return {
            "start_time": self.state.session_start_time.isoformat() if self.state.session_start_time else None,
            "end_time": session_end.isoformat(),
            "total_duration_seconds": total_duration,
            "effective_duration_seconds": self.state.total_effective_seconds,
            "pause_count": self.state.pause_count,
            "total_pause_seconds": self.state.total_pause_seconds,
            "focus_lost_count": self.state.focus_lost_count,
            "heartbeat_ticks": self._heartbeat_count,
        }

    def get_current_state(self) -> ActivityState:
        return ActivityState(**self.state.__dict__)

    def get_recent_events(self, count: int = 10) -> List[ActivityEvent]:
        return list(self._events)[-count:]

    def get_statistics(self) -> Dict:
        return {
            "pause_count": self.state.pause_count,
            "total_pause_seconds": self.state.total_pause_seconds,
            "effective_seconds": self.state.total_effective_seconds,
            "system_idle_seconds": self.state.system_idle_seconds,
            "is_focused": self.state.is_focused,
            "focus_lost_count": self.state.focus_lost_count,
            "heartbeat_ticks": self._heartbeat_count,
        }

    def manual_pause(self):
        self._pause_activity(reason="manual")

    def manual_resume(self):
        self._resume_activity()

    def reset(self):
        self.state = ActivityState()
        self._heartbeat_count = 0
        self._focus_check_count = 0
        self._events.clear()
