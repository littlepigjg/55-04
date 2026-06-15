from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class SpeedRecord:
    date: str
    speed: float


class SpeedCalculator:
    def __init__(self):
        self._history: List[SpeedRecord] = []

    def record(self, words_read: int, effective_seconds: int) -> Optional[float]:
        if effective_seconds <= 0 or words_read <= 0:
            return None
        speed = (words_read / effective_seconds) * 60
        self._history.append(SpeedRecord(
            date=datetime.now().strftime('%Y-%m-%d'),
            speed=speed,
        ))
        return speed

    def get_history(self) -> List[Dict]:
        return [
            {'date': r.date, 'speed': r.speed}
            for r in self._history
        ]

    def get_average(self) -> float:
        if not self._history:
            return 0.0
        return sum(r.speed for r in self._history) / len(self._history)

    def get_latest(self) -> Optional[float]:
        return self._history[-1].speed if self._history else None

    def clear(self):
        self._history.clear()
