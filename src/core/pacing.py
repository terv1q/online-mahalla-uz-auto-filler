import time

from typing import Dict, List, Optional, Tuple


PACE_FAST_LEVEL = 3.0


PACE_MAX_FACTOR = 3.0


PACE_SAMPLES = 20


PACE_CACHE_TTL = 2.0


class Pacer:
    """
    Подстройка ожиданий под скорость сайта.

    Замеряем, как быстро открываются страницы и модалка. Пока сайт отвечает
    быстро — коэффициент 1.0, ожидания базовые (прогон идёт на максимуме
    скорости). Если сайт начинает тормозить, коэффициент растёт (до
    PACE_MAX_FACTOR), и ожидания удлиняются, чтобы не сыпать ошибками.
    Уменьшение коэффициента плавное: быстрый сайт сразу не «наказываем».
    """

    def __init__(self) -> None:
        self.samples: List[float] = []
        self.factor = 1.0
        self._checked = 0.0

    def observe(self, seconds: float) -> None:
        """Замер отклика сайта (сек)."""
        if seconds <= 0:
            return
        self.samples.append(seconds)
        if len(self.samples) > PACE_SAMPLES:
            del self.samples[:-PACE_SAMPLES]

    def _median(self) -> float:
        if not self.samples:
            return 0.0
        ordered = sorted(self.samples)
        return ordered[len(ordered) // 2]

    def refresh(self, now: Optional[float] = None) -> float:
        """Пересчитать коэффициент (не чаще PACE_CACHE_TTL)."""
        now = time.time() if now is None else now
        if now - self._checked < PACE_CACHE_TTL:
            return self.factor
        self._checked = now
        median = self._median()
        if median <= PACE_FAST_LEVEL:
            self.factor = 1.0
            return self.factor
        want = min(median / PACE_FAST_LEVEL, PACE_MAX_FACTOR)

        self.factor = want if want > self.factor else max(want, 1.0)
        return self.factor

    def scale(self, timeout: float) -> float:
        """Базовое ожидание с поправкой на текущую скорость сайта."""
        return max(timeout, timeout * self.refresh())
