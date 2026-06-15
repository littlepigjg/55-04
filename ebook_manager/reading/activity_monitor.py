import threading
import time
import win32clipboard
import win32con
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, List
from dataclasses import dataclass, field
from collections import deque
import logging


@dataclass
class ActivityEvent:
    event_type: str
    timestamp: str
    details: Dict = field(default_factory=dict)


@dataclass
class ActivityState:
    is_active: bool = False
    last_activity_time: Optional[datetime] = None
    session_start_time: Optional[datetime] = None
    total_effective_seconds: int = 0
    pause_count: int = 0
    total_pause_seconds: int = 0
    last_pause_start: Optional[datetime] = None


class ActivityMonitor:
    def __init__(self, 
                 inactivity_threshold: int = 60,
                 poll_interval: float = 1.0,
                 activity_callback: Optional[Callable[[ActivityEvent], None]] = None,
                 state_callback: Optional[Callable[[ActivityState], None]] = None):
        self.inactivity_threshold = inactivity_threshold
        self.poll_interval = poll_interval
        self.activity_callback = activity_callback
        self.state_callback = state_callback
        
        self.state = ActivityState()
        self._events: deque = deque(maxlen=1000)
        self._clipboard_history: List[str] = []
        
        self._keyboard_listener = None
        self._mouse_listener = None
        self._monitor_thread = None
        self._clipboard_thread = None
        self._stop_event = threading.Event()
        
        self._last_clipboard_text = ""
        self._key_press_count = 0
        self._mouse_click_count = 0
        self._mouse_move_count = 0
        self._scroll_count = 0

    def _on_key_press(self, key):
        if not self.state.is_active:
            self._resume_activity()
        
        self.state.last_activity_time = datetime.now()
        self._key_press_count += 1
        
        try:
            key_str = str(key)
        except Exception:
            key_str = "unknown"
        
        event = ActivityEvent(
            event_type="key_press",
            timestamp=datetime.now().isoformat(),
            details={"key": key_str, "count": self._key_press_count}
        )
        
        self._events.append(event)
        if self.activity_callback:
            self.activity_callback(event)
        
        return True

    def _on_click(self, x, y, button, pressed):
        if pressed:
            if not self.state.is_active:
                self._resume_activity()
            
            self.state.last_activity_time = datetime.now()
            self._mouse_click_count += 1
            
            event = ActivityEvent(
                event_type="mouse_click",
                timestamp=datetime.now().isoformat(),
                details={
                    "x": x, "y": y, 
                    "button": str(button),
                    "count": self._mouse_click_count
                }
            )
            
            self._events.append(event)
            if self.activity_callback:
                self.activity_callback(event)
        
        return True

    def _on_move(self, x, y):
        if self.state.is_active:
            self.state.last_activity_time = datetime.now()
            self._mouse_move_count += 1
            
            if self._mouse_move_count % 100 == 0:
                event = ActivityEvent(
                    event_type="mouse_move",
                    timestamp=datetime.now().isoformat(),
                    details={"x": x, "y": y, "count": self._mouse_move_count}
                )
                self._events.append(event)
                if self.activity_callback:
                    self.activity_callback(event)
        
        return True

    def _on_scroll(self, x, y, dx, dy):
        if not self.state.is_active:
            self._resume_activity()
        
        self.state.last_activity_time = datetime.now()
        self._scroll_count += 1
        
        if self._scroll_count % 5 == 0:
            event = ActivityEvent(
                event_type="scroll",
                timestamp=datetime.now().isoformat(),
                details={
                    "x": x, "y": y,
                    "dx": dx, "dy": dy,
                    "count": self._scroll_count
                }
            )
            self._events.append(event)
            if self.activity_callback:
                self.activity_callback(event)
        
        return True

    def _monitor_clipboard(self):
        while not self._stop_event.is_set():
            try:
                win32clipboard.OpenClipboard()
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                        text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                        if text and text != self._last_clipboard_text:
                            self._on_clipboard_change(text)
                finally:
                    win32clipboard.CloseClipboard()
            except Exception:
                pass
            
            time.sleep(self.poll_interval)

    def _on_clipboard_change(self, text: str):
        self._last_clipboard_text = text
        
        if len(text) > 100:
            self._clipboard_history.append(text)
            if len(self._clipboard_history) > 10:
                self._clipboard_history.pop(0)
            
            if not self.state.is_active:
                self._resume_activity()
            
            self.state.last_activity_time = datetime.now()
            
            event = ActivityEvent(
                event_type="clipboard_large_text",
                timestamp=datetime.now().isoformat(),
                details={
                    "length": len(text),
                    "preview": text[:100] + "..." if len(text) > 100 else text
                }
            )
            self._events.append(event)
            if self.activity_callback:
                self.activity_callback(event)

    def _monitor_loop(self):
        while not self._stop_event.is_set():
            try:
                now = datetime.now()
                
                if self.state.is_active and self.state.last_activity_time:
                    inactive_seconds = (now - self.state.last_activity_time).total_seconds()
                    
                    if inactive_seconds > self.inactivity_threshold:
                        self._pause_activity()
                
                if self.state.is_active and self.state.session_start_time:
                    elapsed = (now - self.state.session_start_time).total_seconds()
                    total_pause = self.state.total_pause_seconds
                    
                    if self.state.last_pause_start:
                        current_pause = (now - self.state.last_pause_start).total_seconds()
                        total_pause += current_pause
                    
                    self.state.total_effective_seconds = int(elapsed - total_pause)
                
                if self.state_callback:
                    self.state_callback(ActivityState(**self.state.__dict__))
                
            except Exception as e:
                logging.error(f"Error in monitor loop: {e}")
            
            self._stop_event.wait(self.poll_interval)

    def _pause_activity(self):
        if self.state.is_active:
            self.state.is_active = False
            self.state.last_pause_start = datetime.now()
            self.state.pause_count += 1
            
            event = ActivityEvent(
                event_type="pause",
                timestamp=datetime.now().isoformat(),
                details={"reason": "inactivity", "pause_count": self.state.pause_count}
            )
            self._events.append(event)
            if self.activity_callback:
                self.activity_callback(event)

    def _resume_activity(self):
        if not self.state.is_active:
            if self.state.last_pause_start:
                pause_duration = (datetime.now() - self.state.last_pause_start).total_seconds()
                self.state.total_pause_seconds += int(pause_duration)
                self.state.last_pause_start = None
            
            self.state.is_active = True
            
            event = ActivityEvent(
                event_type="resume",
                timestamp=datetime.now().isoformat(),
                details={}
            )
            self._events.append(event)
            if self.activity_callback:
                self.activity_callback(event)

    def start(self):
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        
        self._stop_event.clear()
        
        try:
            from pynput import keyboard, mouse
            
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press
            )
            self._mouse_listener = mouse.Listener(
                on_click=self._on_click,
                on_move=self._on_move,
                on_scroll=self._on_scroll
            )
            
            self._keyboard_listener.daemon = True
            self._mouse_listener.daemon = True
            self._keyboard_listener.start()
            self._mouse_listener.start()
        except ImportError:
            logging.warning("pynput not installed, falling back to clipboard monitoring only")
        
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        self._clipboard_thread = threading.Thread(target=self._monitor_clipboard, daemon=True)
        self._clipboard_thread.start()
        
        self.state.is_active = True
        self.state.session_start_time = datetime.now()
        self.state.last_activity_time = datetime.now()
        
        event = ActivityEvent(
            event_type="session_start",
            timestamp=datetime.now().isoformat(),
            details={"monitoring": "keyboard, mouse, clipboard"}
        )
        self._events.append(event)
        if self.activity_callback:
            self.activity_callback(event)

    def stop(self) -> Dict:
        self._stop_event.set()
        
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()
        
        for thread in [self._monitor_thread, self._clipboard_thread]:
            if thread and thread.is_alive():
                thread.join(timeout=2.0)
        
        session_end = datetime.now()
        
        if self.state.session_start_time:
            total_duration = int((session_end - self.state.session_start_time).total_seconds())
        else:
            total_duration = 0
        
        event = ActivityEvent(
            event_type="session_end",
            timestamp=session_end.isoformat(),
            details={
                "total_duration": total_duration,
                "effective_duration": self.state.total_effective_seconds,
                "pause_count": self.state.pause_count,
                "total_pause_seconds": self.state.total_pause_seconds,
                "key_presses": self._key_press_count,
                "mouse_clicks": self._mouse_click_count,
                "mouse_moves": self._mouse_move_count,
                "scrolls": self._scroll_count
            }
        )
        self._events.append(event)
        if self.activity_callback:
            self.activity_callback(event)
        
        return {
            "start_time": self.state.session_start_time.isoformat() if self.state.session_start_time else None,
            "end_time": session_end.isoformat(),
            "total_duration_seconds": total_duration,
            "effective_duration_seconds": self.state.total_effective_seconds,
            "pause_count": self.state.pause_count,
            "total_pause_seconds": self.state.total_pause_seconds,
            "key_presses": self._key_press_count,
            "mouse_clicks": self._mouse_click_count,
            "mouse_moves": self._mouse_move_count,
            "scrolls": self._scroll_count,
            "clipboard_captures": len(self._clipboard_history)
        }

    def get_current_state(self) -> ActivityState:
        return ActivityState(**self.state.__dict__)

    def get_recent_events(self, count: int = 10) -> List[ActivityEvent]:
        return list(self._events)[-count:]

    def get_clipboard_history(self) -> List[str]:
        return list(self._clipboard_history)

    def get_statistics(self) -> Dict:
        return {
            "key_presses": self._key_press_count,
            "mouse_clicks": self._mouse_click_count,
            "mouse_moves": self._mouse_move_count,
            "scrolls": self._scroll_count,
            "clipboard_captures": len(self._clipboard_history),
            "pause_count": self.state.pause_count,
            "total_pause_seconds": self.state.total_pause_seconds,
            "effective_seconds": self.state.total_effective_seconds
        }

    def manual_pause(self):
        self._pause_activity()

    def manual_resume(self):
        self._resume_activity()
        self.state.last_activity_time = datetime.now()

    def reset(self):
        self.state = ActivityState()
        self._key_press_count = 0
        self._mouse_click_count = 0
        self._mouse_move_count = 0
        self._scroll_count = 0
        self._clipboard_history.clear()
