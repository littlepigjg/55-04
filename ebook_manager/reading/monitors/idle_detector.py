import ctypes
import ctypes.wintypes
from typing import Optional


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint),
        ('dwTime', ctypes.c_uint),
    ]


class SystemIdleDetector:
    def __init__(self):
        self._user32 = ctypes.windll.User32
        self._kernel32 = ctypes.windll.Kernel32

    def get_idle_seconds(self) -> int:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if self._user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = self._kernel32.GetTickCount() - lii.dwTime
            return max(0, millis // 1000)
        return 0

    def is_idle(self, threshold_seconds: int = 60) -> bool:
        return self.get_idle_seconds() >= threshold_seconds

    def get_tick_count(self) -> int:
        return self._kernel32.GetTickCount()
