import argparse
import time

from ..core.browser import BrowserAutomator
from ..core.logs import (
    actions,
    brief,
    logger,
    timed,
)
from ..core.selectors import (
    ERROR_SHEETS,
    ERROR_TITLES,
    ERR_ACTIVE,
    ERR_DEAD,
    ERR_EXISTS,
    NETWORK_FAIL_KEYS,
    SHEET_ERRORS,
    SHEET_OK,
    SHEET_SKIPPED,
    STREETS_FROM,
)
from ..core.settings import (
    BASE_URL,
    SURVEY_URL,
)
from ..core.state import (
    CadasterRegistry,
    IgnoreList,
    Progress,
    StreetMap,
    StreetScanState,
)
from ..core.timing import (
    CARD_ATTEMPTS,
    RETRY_PAUSE,
)
from ..core.utils import (
    match_street_unit,
    parse_streets_file,
    street_key,
    street_url,
    url_params,
)
from .config import (
    ACTIONS_LOG_FILE,
    CADASTERS_FILE,
    IGNORE_FILE,
    PROFILE,
    PROGRESS_FILE,
    STREET_ALIASES,
    STREET_MAP_FILE,
    STREETS_FILE_FROM,
    STREETS_FOUND_FILE,
    STREETS_STATE_FILE,
)
from .model import (
    ExcelReader,
    ExcelRow,
    ReportWriter,
)
from datetime import datetime, timedelta
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from typing import Dict, List, Optional, Tuple


class NewkadastrAutomation:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.automator = BrowserAutomator(PROFILE, args.debug_select)
        self.report = ReportWriter(args.report)
        self.progress = Progress(PROGRESS_FILE, args.resume)
        self.ignore = IgnoreList(IGNORE_FILE)
        self.streets = StreetScanState(STREETS_STATE_FILE, STREETS_FOUND_FILE)
        self.street_map = StreetMap(STREET_MAP_FILE)
        self.cadasters = CadasterRegistry(CADASTERS_FILE)
        self.excel_index: Dict[str, ExcelRow] = {}
        self.excel_rows: List[ExcelRow] = []
        self.run_rows: List[ExcelRow] = []
        self.resolved: Dict[str, dict] = {}
        self.street_source = ""
        self.stats = {"OK": 0, "OK_WARN": 0, "FAILED": 0, "SKIPPED": 0,
                      "IGNORED": 0, "ALREADY_DONE": 0, "NO_STREET": 0,
                      "STREET_OPEN_FAIL": 0,
                      ERR_EXISTS: 0, ERR_ACTIVE: 0, ERR_DEAD: 0,
                      "STREETS_SCANNED": 0, "STREETS_FOUND": 0}
        self.started = time.perf_counter()
        self.row_times: List[float] = []

    def build_excel_index(self) -> Dict[str, ExcelRow]:
        """
        Индекс всех кадастров таблицы (полный код и без «/0002»). Нужен, чтобы
        кадастр со страницы улицы опознать, даже если он записан короче или
        стоит в строке другой улицы.
        """
        if not self.excel_rows:
            self.excel_rows = ExcelReader(self.args.excel).read_rows(2)
        index: Dict[str, ExcelRow] = {}
        for row in self.excel_rows:
            index[row.code] = row
            index.setdefault(row.code.split("/")[0], row)
        self.excel_index = index
        logger.info(f"Индекс таблицы: кадастров {len(self.excel_rows)}")
        return index

    def apply_scan_state(self) -> None:
        """
        Переносит кадастры из уже собранного состояния улиц в ignore/progress,
        не открывая браузер. Так ранее найденные «уже заполненные» строки
        не обрабатываются повторно.
        """
        if not self.excel_index:
            self.build_excel_index()
        added = 0
        for url, info in self.streets.data.items():
            for code in info.get("cadasters", []):
                row = self.excel_index.get(code) or self.excel_index.get(code.split("/")[0])
                if not row or self.progress.is_done(row.code) or row.code in self.ignore:
                    continue
                self._register_already_entered(row)
                added += 1
        logger.info(f"Состояние улиц: в ignore/progress добавлено строк {added} "
                    f"(всего в ignore {len(self.ignore.reasons)})")

    def stream_rows(self) -> List[ExcelRow]:
        """Строки, которые пойдут в работу: ограниченные --start-row, иначе все."""
        if self.run_rows:
            return self.run_rows
        if not self.excel_rows:
            self.excel_rows = ExcelReader(self.args.excel).read_rows(2)
        return self.excel_rows

    def read_street_list(self) -> List[dict]:
        """Улицы района: сохранённая страница (--streets-file) или живая сводка."""
        if self.args.streets_file:
            units = parse_streets_file(self.args.streets_file)
            if units:
                self.street_source = f"файл {self.args.streets_file}"
                return units
            logger.warning(f"В файле улиц ничего не разобрано: {self.args.streets_file}")
        self.street_source = "страница survey_homes"
        logger.info(f"Читаю список улиц со страницы: {SURVEY_URL}")
        if not self.automator.alive():
            self.automator.restart()
        self.automator.open_url(SURVEY_URL)
        return self.automator.read_street_units()

    def resolve_streets(self) -> Dict[str, dict]:
        """
        Название улицы в таблице → улица на сайте. Сначала готовая карта из
        конфига, потом сохранённое сопоставление, и только для незнакомых улиц
        открывается страница со списком улиц и берётся ближайшее название.
        """
        rows = self.stream_rows()
        keys: List[str] = []
        for row in rows:
            if row.street_url:
                continue
            key = street_key(row.table_street)
            if key and key not in keys:
                keys.append(key)

        self.resolved = {}
        unknown: List[str] = []
        for key in keys:
            unit = self.street_map.get(key)
            if unit:
                self.resolved[key] = unit
                continue
            alias = STREET_ALIASES.get(key)
            if alias:
                unit = {"url": street_url(alias[0]), "name": alias[1],
                        "street_id": alias[0]}
                self.resolved[key] = unit
                self.street_map.put(key, unit)
                continue
            unknown.append(key)

        if unknown:
            units = self.read_street_list()
            logger.info(f"Знакомых улиц {len(keys) - len(unknown)} из {len(keys)}, "
                        f"ищу на странице: {len(unknown)}")
            for key in unknown:
                unit, ratio = match_street_unit(key, units)
                if unit is None:
                    logger.warning(f"Улица «{key}» не нашлась в списке улиц "
                                   f"(лучшее совпадение {ratio:.2f})")
                    continue
                self.resolved[key] = unit
                self.street_map.put(key, unit)
                logger.info(f"Улица «{key}» → {unit['name']} "
                            f"(id {unit['street_id']}, совпадение {ratio:.2f})")

        unmatched: List[str] = []
        for row in rows:
            if row.street_url:
                continue
            unit = self.resolved.get(street_key(row.table_street))
            if unit is None:
                name = row.table_street or "—"
                if name not in unmatched:
                    unmatched.append(name)
                continue
            row.street_url = unit["url"]

        counts: Dict[str, int] = {}
        for row in rows:
            if row.street_url:
                counts[row.street_url] = counts.get(row.street_url, 0) + 1
        logger.info(f"Улиц сопоставлено: {len(self.resolved)} — {self.street_source or 'карта'}")
        for key, unit in self.resolved.items():
            logger.info(f"   «{key}» → {unit['name']} (id {unit['street_id']}) — строк "
                        f"{counts.get(unit['url'], 0)}")
        if unmatched:
            logger.warning(f"Улицы без пары: {len(unmatched)} — " + "; ".join(unmatched[:20])
                           + (" …" if len(unmatched) > 20 else "")
                           + "; дополните STREET_ALIASES в src/household_filler/config.py"
                             " и запустите снова")
            logger.warning(f"Строк с несопоставленной улицей: "
                           f"{sum(1 for r in rows if not r.street_url)}")
        return self.resolved

    def street_units(self) -> List[dict]:
        """
        Улицы для обхода — только те, что есть в таблице, в порядке таблицы.
        К каждой подтягиваются строки Excel этой улицы: строки одной улицы идут
        подряд, поэтому страница улицы открывается один раз.
        """
        units: List[dict] = []
        by_url: Dict[str, dict] = {}
        for row in self.stream_rows():
            if not row.street_url:
                continue
            unit = by_url.get(row.street_url)
            if unit is None:
                site = self.resolved.get(street_key(row.table_street)) or {}
                unit = {"url": row.street_url,
                        "name": site.get("name") or row.street_label(),
                        "street_id": url_params(row.street_url).get("street_id", ""),
                        "rows": []}
                by_url[row.street_url] = unit
                units.append(unit)
            unit["rows"].append(row)
        logger.info(f"Улиц в работе: {len(units)}, строк: "
                    f"{sum(len(u['rows']) for u in units)}")
        return units

    def scan_streets(self) -> None:
        """
        Обходит все улицы и читает кадастры, которые уже заведены на странице
        улицы. Найденные из таблицы Excel — в ignore-лист, чтобы строки не
        обрабатывались повторно. Проверенные улицы и их кадастры сохраняются в
        streets_state_newkadastr.json и при следующем запуске не обходятся.
        """
        if not self.args.street_scan:
            logger.info("Обход улиц отключён (--no-street-scan) — беру только "
                        "ранее собранное состояние улиц")
            self.apply_scan_state()
            return

        self.build_excel_index()

        units = self.street_units()
        if not units:
            logger.warning("Список улиц пуст — обход пропущен")
            return

        self.apply_scan_state()

        start = max(1, self.args.streets_from if self.args.streets_from else
                    (STREETS_FILE_FROM if self.street_source.startswith("файл") else STREETS_FROM))
        total_all = len(units)
        units = units[start - 1:]
        logger.info("═" * 60)
        logger.info(f"Обход улиц: всего {total_all}, начиная с {start}-й — к проверке "
                    f"{len(units)}, уже проверено ранее "
                    f"{sum(1 for u in units if self.streets.is_checked(u['url']))}")

        for idx, unit in enumerate(units, 1):
            url, label, street_rows = unit["url"], unit["name"], unit["rows"]
            if self.streets.is_checked(url) and not self.args.rescan_streets:
                self.stats["STREETS_FOUND"] += len(
                    self.streets.info(url).get("cadasters", []))
                actions.info(f"УЛИЦА {idx}/{len(units)} пропущена (уже проверена): {url}")
                continue
            if self.args.cadaster and not any(
                    self.args.cadaster in r.code for r in street_rows):
                continue

            logger.info(f"[улица {idx}/{len(units)}] {label}")
            actions.info("=" * 70)
            actions.info(f"СКАН УЛИЦЫ {idx}/{len(units)}: {url} | {label}")
            started = time.perf_counter()
            with timed(f"2.{idx} Скан улицы", label):
                if not self.automator.alive():
                    self.automator.restart()
                if not self.automator.open_street_by_link(unit["street_id"], url):
                    self.stats["STREET_OPEN_FAIL"] += 1
                    logger.warning(f"Улица «{label}» не открыта — сканирование пропущено")
                    actions.info(f"УЛИЦА НЕ ОТКРЫТА {label} | {url}")
                    continue
                found = self.automator.read_street_cadasters()
            elapsed = time.perf_counter() - started

            codes = sorted({item["cadaster"] for item in found})


            index = getattr(self, "excel_index", {})
            matched: Dict[str, ExcelRow] = {}
            for code in codes:
                row = index.get(code) or index.get(code.split("/")[0])
                if row:
                    matched[row.code] = row
            already = sorted(matched)
            in_table = len(matched)

            for code in already:
                self._register_already_entered(matched[code])

            self.streets.save(url, {
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "street": label,
                "street_id": unit["street_id"],
                "homes": len(found),
                "cadasters": codes,
                "excel_matched": already,
                "excel_rows": len(street_rows),
            })
            self.streets.append_found(url, codes, label)
            added = self.cadasters.add_many(codes, "страница улицы", label)
            actions.info(f"Реестр кадастров: новых из {len(codes)} — {added}, "
                         f"нет в строках Excel этой улицы: {len(codes) - in_table}")
            self.stats["STREETS_SCANNED"] += 1
            self.stats["STREETS_FOUND"] += len(codes)
            logger.info(f"   хонадонов на странице: {len(found)}, кадастров: {len(codes)}, "
                        f"уже заполнено из таблицы: {len(already)} "
                        f"(строк Excel по улице: {len(street_rows)})")
            actions.info(f"ИТОГ СКАНА {label}: хонадонов={len(found)}, "
                         f"кадастров={len(codes)}, совпало с Excel={brief(already)} | "
                         f"{elapsed:.2f} с")
            self.automator.sleep_if_rate_limited()

        missing = [u["name"] for u in units if not u["rows"]]
        if missing:
            logger.info(f"Улиц без строк в Excel: {len(missing)} — "
                        f"кадастры всё равно прочитаны и сохранены")

    def _register_already_entered(self, row: ExcelRow) -> None:
        """Кадастр уже заведён на сайте — в ignore-лист и в отчёт."""
        title = ERROR_TITLES[ERR_EXISTS]
        if row.code in self.ignore and self.ignore.reason(row.code) == "уже есть на странице улицы":
            return
        self.stats[ERR_EXISTS] = self.stats.get(ERR_EXISTS, 0) + 1
        self.report.add(ERROR_SHEETS[ERR_EXISTS], row.street_label(), row.code, row.house,
                        "", "", row.get_formatted_phone(), "ОШИБКА САЙТА", title,
                        "кадастр найден на странице улицы", row.street_url)
        self.report.add_not_entered(row.code, row.street_label(), row.house, "", "",
                                    row.get_formatted_phone(), title)
        self.ignore.add(row.code, "уже есть на странице улицы")
        self.progress.mark(row.code, ERR_EXISTS)
        self.cadasters.add(row.code, "уже было на сайте", row.street_label())
        logger.warning(f"   + уже заполнен: {row.code} → ignore-лист")

    @staticmethod
    def group_rows_by_street(rows: List[ExcelRow]) -> List[ExcelRow]:
        """
        Идём по улицам из таблицы: строки одной улицы подряд, порядок улиц —
        как в таблице. Так страница улицы открывается один раз, а не прыгает
        туда-сюда между строками.
        """
        buckets: Dict[str, List[ExcelRow]] = {}
        order: List[str] = []
        for row in rows:
            key = row.street_url or ""
            if key not in buckets:
                buckets[key] = []
                order.append(key)
            buckets[key].append(row)
        ordered: List[ExcelRow] = []
        for key in order:
            ordered.extend(buckets[key])
        logger.info(f"Строк: {len(ordered)}, улиц из таблицы: {len(order)} — "
                    f"идём по улицам по порядку таблицы")
        multi = [key for key in order if len(buckets[key]) > 1]
        for key in multi[:20]:
            label = buckets[key][0].street_label() if key else "БЕЗ УЛИЦЫ (пропуск)"
            logger.info(f"   улица: {label} — строк {len(buckets[key])}")
        if len(multi) > 20:
            logger.info(f"   … улиц с несколькими строками всего: {len(multi)}")
        return ordered

    def run(self) -> None:
        rows = ExcelReader(self.args.excel).read_rows(self.args.start_row)
        if not rows:
            logger.error("В Excel нет данных")
            return
        self.run_rows = rows
        self.build_excel_index()

        self.automator.start()
        processed = 0
        try:
            self.automator.open_url(BASE_URL)
            self.automator.remember_main_window()
            self.automator._close_extra_windows()
            self.automator.wait_for_login()

            self.resolve_streets()
            rows = self.group_rows_by_street(rows)
            self.scan_streets()

            total = len(rows)
            for idx, row in enumerate(rows, 1):
                if self.args.limit and processed >= self.args.limit:
                    logger.info("Достигнут лимит строк")
                    return
                if self.args.cadaster and self.args.cadaster not in row.code:
                    continue
                if not row.street_url:
                    self.stats["NO_STREET"] += 1
                    logger.warning(f"↷ [{idx}/{total}] {row.code} — улица "
                                   f"«{row.table_street or '—'}» не сопоставлена, пропуск")
                    actions.info(f"ПРОПУСК {row.code}: улица «{row.table_street}» "
                                 f"нет в STREET_ALIASES и в списке улиц")
                    continue
                if self.progress.is_done(row.code) and not self.args.retry_ignored:
                    self.stats["ALREADY_DONE"] = self.stats.get("ALREADY_DONE", 0) + 1
                    logger.info(f"↷ [{idx}/{total}] {row.code} — уже обработан "
                                f"({self.progress.info(row.code)}), пропуск")
                    actions.info(f"ПРОПУСК {row.code}: progress={self.progress.info(row.code)}, "
                                 f"ignore={self.ignore.reason(row.code) or '—'}")
                    continue
                if row.code in self.ignore and not self.args.retry_ignored:
                    self.stats["IGNORED"] += 1
                    logger.info(f"↷ [{idx}/{total}] {row.code} — уже пробовали "
                                f"({self.ignore.reason(row.code)}), пропуск")
                    continue

                logger.info("─" * 60)
                logger.info(f"[{idx}/{total}] {row.code} | {row.street_label()} "
                            f"| дом {row.house or '—'}")
                actions.info("=" * 70)
                actions.info(f"СТРОКА {idx}/{total} | лист №{row.row_index} | "
                             f"{row.code} | улица {row.street_label()} | дом {row.house or '—'} "
                             f"| ЖШШИР {row.pinfl_raw} | ДР {row.birth1 or '—'} "
                             f"| ЖШШИР2 {row.pinfl2_raw or '—'} | ДР2 {row.birth2 or '—'}")

                if not row.pinfl_candidates():
                    self.stats["SKIPPED"] += 1
                    logger.warning("Нет/некорректный ЖШШИР")
                    self._handle_result("SKIPPED", "Нет/некорректный ЖШШИР", "",
                                        row, "", "")
                    continue


                self.ignore.add(row.code, "попытка обработки — результат не записан")

                row_started = time.perf_counter()
                actions.info(f"НАЧАЛО ОБРАБОТКИ СТРОКИ {row.code}")
                status, info, notices, pinfl, birth = self._process(row)
                row_elapsed = time.perf_counter() - row_started
                self.row_times.append(row_elapsed)
                processed += 1
                avg = sum(self.row_times) / len(self.row_times)
                actions.info(f"КОНЕЦ ОБРАБОТКИ СТРОКИ {row.code}: статус {status}, "
                             f"ЖШШИР {pinfl or '—'}, ДР {birth or '—'} | "
                             f"{row_elapsed:.2f} с")
                logger.info(f"⏱ Строка {row.code}: {status} за {row_elapsed:.2f} с "
                            f"(среднее {avg:.2f} с, всего {len(self.row_times)} строк, "
                            f"прошло {time.perf_counter() - self.started:.0f} с)")
                self._handle_result(status, info, notices, row, pinfl, birth)
                time.sleep(self.args.delay)
        finally:
            self._print_summary()
            self.automator.close()

    def _handle_result(self, status: str, info: str, notices: str,
                       row: ExcelRow, pinfl: str, birth: str) -> None:
        code = row.code
        street = row.street_label()
        house = row.house
        phone = row.get_formatted_phone()

        if status in ("OK", "OK_WARN"):
            self.stats[status] += 1
            self.report.add(SHEET_OK, street, code, house, pinfl, birth, phone,
                            "ЗАПОЛНЕНО" if status == "OK" else "ЗАПОЛНЕНО С ЗАМЕЧАНИЕМ",
                            info, notices, row.street_url)
            logger.info(f"✔ Готово: {code}" + (f" ({info})" if info else ""))
            self.progress.mark(code, status)
            self.cadasters.add(code, "заполнено скриптом" if status == "OK"
                               else "заполнено скриптом с замечанием", street)
            self.ignore.add(code, "заполнено" if status == "OK"
                            else f"заполнено с замечанием: {brief(info, 120)}")

        elif status == "KNOWN_ERROR":
            self.stats[info] = self.stats.get(info, 0) + 1
            title = ERROR_TITLES.get(info, info)
            self.report.add(ERROR_SHEETS.get(info, SHEET_ERRORS), street, code, house,
                            pinfl, birth, phone, "ОШИБКА САЙТА", title, notices,
                            row.street_url)
            self.report.add_not_entered(code, street, house, pinfl, birth, phone, title)
            self.ignore.add(code, title)
            self.progress.mark(code, info)
            self.cadasters.add(code, f"сайт: {title}", street)
            logger.warning(f"✖ {title} → в ignore-лист")

        elif status == "SKIPPED":
            self.stats["SKIPPED"] += 1
            self.report.add(SHEET_SKIPPED, street, code, house, pinfl, birth, phone,
                            "ПРОПУЩЕН", info, notices, row.street_url)
            self.report.add_not_entered(code, street, house, pinfl, birth, phone, info)
            self.progress.mark(code, status)
            self.ignore.add(code, f"пропущено: {brief(info, 120)}")

        else:
            self.stats["FAILED"] += 1
            self.report.add(SHEET_ERRORS, street, code, house, pinfl, birth, phone,
                            "ОШИБКА", info, notices, row.street_url)
            self.report.add_not_entered(code, street, house, pinfl, birth, phone,
                                        f"{info}. {notices}".strip(". "))
            self.ignore.add(code, f"ошибка: {brief(info, 120)}")
            logger.error(f"✖ {info}")

    def _process(self, row: ExcelRow) -> Tuple[str, str, str, str, str]:
        last = ("FAILED", "Неизвестная ошибка", "", "", "")
        for attempt in range(1, CARD_ATTEMPTS + 1):
            try:
                if not self.automator.alive():
                    self.automator.restart()
                status, info, notices, pinfl, birth = self.automator.process_row(row)
                if status in ("OK", "OK_WARN", "SKIPPED", "STREET_FAIL", "KNOWN_ERROR"):
                    return status, info, notices, pinfl, birth
                last = (status, info, notices, pinfl, birth)
                if attempt < CARD_ATTEMPTS:
                    logger.warning(f"Попытка {attempt}/{CARD_ATTEMPTS}: {info}")
                    time.sleep(RETRY_PAUSE)
            except WebDriverException as exc:
                message = str(exc).splitlines()[0]
                last = ("FAILED", f"WebDriver: {message[:140]}", "", "", "")
                logger.error(f"Попытка {attempt}/{CARD_ATTEMPTS}: {message[:140]}")
                if any(k in message for k in NETWORK_FAIL_KEYS):
                    self.automator.restart()
            except Exception as exc:
                last = ("FAILED", f"Исключение: {str(exc)[:140]}", "", "", "")
                logger.error(f"Попытка {attempt}/{CARD_ATTEMPTS}: {exc}")
        return last

    def _print_summary(self) -> None:
        s = self.stats
        logger.info("═" * 60)
        logger.info(f"Успешно: {s['OK']} | с замечанием: {s['OK_WARN']} | ошибок: {s['FAILED']}")
        logger.info(f"Уже в системе: {s[ERR_EXISTS]} | нет данных (aktiv): {s[ERR_ACTIVE]} "
                    f"| нет данных (vafot): {s[ERR_DEAD]}")
        logger.info(f"Пропущено: {s['SKIPPED']} | в ignore: {s['IGNORED']} | "
                    f"уже обработано ранее: {s['ALREADY_DONE']} "
                    f"(всего в ignore-листе: {len(self.ignore.reasons)})")
        logger.info(f"Строк без сопоставленной улицы: {s['NO_STREET']} "
                    f"(карта улиц: {STREET_MAP_FILE})")
        logger.info(f"Улиц проверено: {s['STREETS_SCANNED']} | кадастров найдено на улицах: "
                    f"{s['STREETS_FOUND']} (состояние: {STREETS_STATE_FILE})")
        if s["STREET_OPEN_FAIL"]:
            logger.warning(f"Улиц не удалось открыть кликом по ссылке: {s['STREET_OPEN_FAIL']}")
        logger.info(f"Реестр всех заведённых кадастров: {len(self.cadasters.known)} "
                    f"({CADASTERS_FILE})")
        logger.info(f"Отчёт: {self.report.path}")
        if self.row_times:
            total = sum(self.row_times)
            logger.info(f"Время работы: {time.perf_counter() - self.started:.2f} с | "
                        f"строк: {len(self.row_times)} | среднее: "
                        f"{total / len(self.row_times):.2f} с | мин: {min(self.row_times):.2f} с "
                        f"| макс: {max(self.row_times):.2f} с | сумма по строкам: {total:.2f} с")
        else:
            logger.info(f"Время работы: {time.perf_counter() - self.started:.2f} с | "
                        f"обработанных строк нет")
        logger.info(f"Подробный лог действий: {ACTIONS_LOG_FILE}")
        logger.info("═" * 60)
