import ctypes
import ctypes.wintypes
from typing import Optional, Callable


class WindowFocusMonitor:
    _user32 = ctypes.windll.User32

    @staticmethod
    def get_foreground_window() -> int:
        return WindowFocusMonitor._user32.GetForegroundWindow()

    @staticmethod
    def get_window_text(hwnd: int) -> str:
        length = 256
        buf = ctypes.create_unicode_buffer(length)
        WindowFocusMonitor._user32.GetWindowTextW(hwnd, buf, length)
        return buf.value or ""

    @staticmethod
    def get_window_pid(hwnd: int) -> int:
        pid = ctypes.wintypes.DWORD()
        WindowFocusMonitor._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    @staticmethod
    def is_our_window_active(our_pid: Optional[int] = None) -> bool:
        if our_pid is None:
            import os
            our_pid = os.getpid()
        fg = WindowFocusMonitor.get_foreground_window()
        if fg == 0:
            return False
        return WindowFocusMonitor.get_window_pid(fg) == our_pid

    @staticmethod
    def get_foreground_info() -> dict:
        hwnd = WindowFocusMonitor.get_foreground_window()
        return {
            'hwnd': hwnd,
            'title': WindowFocusMonitor.get_window_text(hwnd),
            'pid': WindowFocusMonitor.get_window_pid(hwnd),
        }
