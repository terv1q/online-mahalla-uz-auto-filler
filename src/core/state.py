import json

from .logs import (
    actions,
    logger,
)
from .utils import normalize_code
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class Progress:
    """
    Что уже обработано. Файл читается всегда, иначе повторный запуск затирал бы
    историю и начинал обработанные строки заново. --retry-ignored заставляет
    обработать их снова.
    """

    def __init__(self, path: str, resume: bool = True):
        self.path = Path(path)
        self.done: Dict[str, str] = {}
        if self.path.exists():
            try:
                self.done = json.loads(self.path.read_text(encoding="utf-8"))
                logger.info(f"Прогресс: ранее обработано {len(self.done)}"
                            + ("" if resume else " (читаю файл и без --resume)"))
            except Exception as exc:
                logger.warning(f"Файл прогресса повреждён ({exc})")

    def is_done(self, code: str) -> bool:
        return code in self.done

    def info(self, code: str) -> str:
        return self.done.get(code, "")

    def mark(self, code: str, status: str) -> None:
        self.done[code] = status
        try:
            self.path.write_text(json.dumps(self.done, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"Прогресс не записан: {exc}")


class IgnoreList:
    """
    Кадастры, которые скрипт уже начинал обрабатывать (в т.ч. успешно).
    При следующем запуске такие строки пропускаются, чтобы не начинать заново.
    Хранит код → причину; файл переписывается целиком при каждом изменении.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self.reasons: Dict[str, str] = {}
        if self.path.exists():
            try:
                for line in self.path.read_text(encoding="utf-8").splitlines():
                    raw, _, reason = line.partition("#")
                    code = normalize_code(raw)
                    if code:
                        self.reasons[code] = reason.strip() or "ранее обработан"
            except Exception as exc:
                logger.warning(f"ignore-лист не прочитан: {exc}")
        logger.info(f"Игнор-лист: {len(self.reasons)} кадастров")

    @property
    def codes(self) -> set:
        return set(self.reasons)

    def __contains__(self, code: str) -> bool:
        return code in self.reasons

    def reason(self, code: str) -> str:
        return self.reasons.get(code, "")

    def add(self, code: str, reason: str = "") -> bool:
        """Добавляет/обновляет запись. True — если запись новая."""
        if not code:
            return False
        code = normalize_code(code)
        note = (reason or "ранее обработан").strip()
        fresh = code not in self.reasons
        if self.reasons.get(code) == note:
            return False
        self.reasons[code] = note
        self._flush()
        actions.info(f"IGNORE {'+' if fresh else '~'} {code} — {note}")
        return fresh

    def _flush(self) -> None:
        try:
            with self.path.open("w", encoding="utf-8") as handle:
                for code, note in self.reasons.items():
                    handle.write(f"{code}  # {note}\n")
        except Exception as exc:
            logger.warning(f"ignore-лист не записан: {exc}")


class CadasterRegistry:
    """
    Все кадастры, уже заведённые на сайте: с обхода страниц улиц и с наших
    сохранений. Пишутся в общий файл — в том числе те, которых нет в таблице
    Excel, чтобы была история на будущее. Код → примечание, повторов нет.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self.known: Dict[str, str] = {}
        if self.path.exists():
            try:
                for line in self.path.read_text(encoding="utf-8").splitlines():
                    raw, _, note = line.partition("#")
                    code = normalize_code(raw)
                    if code:
                        self.known.setdefault(code, note.strip())
                logger.info(f"Реестр кадастров: уже записано {len(self.known)}")
            except Exception as exc:
                logger.warning(f"Реестр кадастров не прочитан ({exc})")

    def add(self, code: str, source: str, street: str = "") -> bool:
        code = normalize_code(code or "")
        if not code or code in self.known:
            return False
        note = datetime.now().strftime("%Y-%m-%d")
        if street:
            note += f" | {street}"
        if source:
            note += f" | {source}"
        self.known[code] = note
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(f"{code}  # {note}\n")
        except Exception as exc:
            logger.warning(f"Реестр кадастров не записан: {exc}")
        return True

    def add_many(self, codes: List[str], source: str, street: str = "") -> int:
        return sum(1 for code in codes if self.add(code, source, street))


class StreetScanState:
    """
    Состояние обхода улиц: какие улицы уже проверялись и какие кадастры на них
    найдены. Файл family_streets_state.json — при следующем запуске
    проверенные улицы не обходятся заново.
    """

    def __init__(self, path: str, found_file: str = ""):
        self.path = Path(path)
        self.found_file = found_file
        self.data: Dict[str, dict] = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(f"Состояние улиц повреждено ({exc}) — начну заново")
                self.data = {}
        logger.info(f"Состояние улиц: проверено ранее {len(self.data)}")

    def is_checked(self, url: str) -> bool:
        return url in self.data

    def info(self, url: str) -> dict:
        return self.data.get(url, {})

    def save(self, url: str, info: dict) -> None:
        self.data[url] = info
        try:
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
        except Exception as exc:
            logger.warning(f"Состояние улиц не записано: {exc}")

    def append_found(self, url: str, cadasters: List[str], street_label: str) -> None:
        """Все найденные кадастры (не только из таблицы) — в отдельный файл."""
        if not cadasters:
            return
        try:
            with Path(self.found_file).open("a", encoding="utf-8") as handle:
                handle.write(f"# {url} | {street_label}\n")
                for code in cadasters:
                    handle.write(f"{code}\n")
        except Exception as exc:
            logger.warning(f"Файл найденных кадастров не записан: {exc}")
