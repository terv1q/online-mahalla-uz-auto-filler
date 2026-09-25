import json

from ..core.logs import logger
from .config import TARGET_BOSHQA
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class MembersState:
    """
    Сколько строк «Бошқа» уже заведено в каждом кадастре и какие строки Excel
    израсходованы. Файл family_members_state.json: повторный запуск не перепроверяет
    кадастры, где уже набрано 30 «Бошқа», и не берёт одних и тех же людей.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self.cadasters: Dict[str, dict] = {}
        self.used: List[str] = []
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.cadasters = data.get("cadasters", {}) or {}
                self.used = data.get("used_rows", []) or []
            except Exception as exc:
                logger.warning(f"Состояние членов семьи повреждено ({exc}) — начну заново")
        logger.info(f"Члены семьи: кадастров в состоянии {len(self.cadasters)}, "
                    f"использовано строк таблицы {len(self.used)}")

    @property
    def used_set(self) -> set:
        return set(self.used)

    def info(self, key: str) -> dict:
        return self.cadasters.get(key, {})

    def count(self, key: str) -> int:
        return int(self.info(key).get("boshqa", 0) or 0)

    def is_done(self, key: str, target: int = TARGET_BOSHQA) -> bool:
        return self.count(key) >= target

    def set_count(self, key: str, count: int, **info) -> None:
        entry = self.cadasters.get(key, {})
        entry.update(info)
        entry["boshqa"] = int(count)
        entry["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cadasters[key] = entry
        self._flush()

    def mark_row_used(self, row_code: str) -> None:
        if row_code and row_code not in self.used:
            self.used.append(row_code)
            self._flush()

    def reset(self, key: Optional[str] = None) -> None:
        if key:
            self.cadasters.pop(key, None)
        else:
            self.cadasters = {}
            self.used = []
        self._flush()

    def _flush(self) -> None:
        try:
            self.path.write_text(json.dumps(
                {"cadasters": self.cadasters, "used_rows": self.used},
                ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"Состояние членов семьи не записано: {exc}")
