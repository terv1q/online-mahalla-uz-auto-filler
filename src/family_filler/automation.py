import argparse
import re
import time

from ..core.browser import BrowserAutomator
from ..core.js import JS_TOAST_STATE
from ..core.logs import (
    actions,
    brief,
    logger,
    timed,
)
from ..core.pacing import Pacer
from ..core.selectors import (
    SHEET_ERRORS,
    SHEET_OK,
    UNKNOWN_STREET_MARKERS,
)
from ..core.settings import BASE_URL
from ..core.state import (
    CadasterRegistry,
    Progress,
)
from ..core.timing import (
    AFTER_TAB_OPEN,
    FORM_READY_TIMEOUT,
    NOTICE_SETTLE_QUICK,
    OPTION_WAIT_AFTER_TYPE,
    OPTION_WAIT_TIMEOUT,
    POLL_INTERVAL,
    SAVE_NOTICE_TIMEOUT,
    SEARCH_RESULT_TIMEOUT,
    SELECT_ATTEMPTS,
    STREET_READY_TIMEOUT,
)
from ..core.utils import (
    digits_only,
    norm_doc_code,
    norm_text,
    parse_streets_file,
    url_params,
)
from .config import (
    ACTIONS_LOG_FILE,
    AFTER_ERROR_PAUSE,
    AFTER_FIELD_PAUSE,
    AFTER_MODAL_CLOSE,
    AFTER_SAVE_PAUSE,
    CADASTERS_FILE,
    CADASTER_TIMEOUT,
    DOC_NUMBER_NAMES,
    DOC_SERIES_NAMES,
    DOC_TYPE_NAMES,
    EDUCATION_NAMES,
    EDUCATION_VALUE,
    FULL_RESET_AFTER_FAILURES,
    MEMBERS_STATE_FILE,
    MEMBER_BIRTH_NAMES,
    MEMBER_FAIL_LIMIT,
    MEMBER_FILL_ATTEMPTS,
    MODAL_CRITICAL_PROBLEMS,
    PROFILE,
    MEMBER_PAUSE,
    PHONE_NAMES,
    PINFL_NAMES,
    PROGRESS_FILE,
    RATE_LIMIT_DEFAULT_WAIT,
    RATE_LIMIT_EXTRA,
    RATE_LIMIT_MAX_WAIT,
    RATE_LIMIT_PREFIX,
    RELATION_NAMES,
    RELATION_VALUE,
    ROW_SKIP_MARKERS,
    ROW_SKIP_PREFIX,
    SAVE_NOTICE_QUICK_TIMEOUT,
    STREETS_FILE_FROM,
    SURVEY_URL,
    TAB_FALLBACKS,
    TAB_TEXT,
    TOAST_POLL_INTERVAL,
    TOAST_SETTLE,
    TOAST_WAIT_TIMEOUT,
)
from .js import (
    JS_CLICK_MEMBER_SAVE,
    JS_EMPTY_REQUIRED,
    JS_FIELDSET_SELECT_STATE,
    JS_MEMBERS_ROWS,
    JS_MODAL_CLOSE,
    JS_MODAL_FIELDS,
    JS_MODAL_SAVE_CLICK,
    JS_MODAL_VISIBLE,
    JS_OPEN_TAB,
    JS_SEARCH_MEMBER_CLICK,
    JS_SET_FIELDSET_SELECT_VALUE,
    JS_TABLE_LINKS_FILTERED,
)
from .members import MembersState
from .model import (
    ExcelReader,
    ExcelRow,
    ReportWriter,
)
from html import unescape
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse


class FamilyAutomation:
    """Обход улиц → кадастры → «Хонадон аъзолари» → 30 членов семьи «Бошқа»."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.automator = BrowserAutomator(PROFILE, args.debug_select)
        self.report = ReportWriter(args.report)
        self.progress = Progress(PROGRESS_FILE, args.resume)
        self.members = MembersState(MEMBERS_STATE_FILE)
        self.cadasters = CadasterRegistry(CADASTERS_FILE)
        self.rows: List[ExcelRow] = []
        self.row_cursor = 0
        self.used_rows = self.members.used_set
        self.option_maps: Dict[str, Dict[str, str]] = {}
        self.pacer = Pacer()
        self.stats = {"MEMBERS": 0, "MEMBER_FAIL": 0, "CADASTERS": 0,
                      "CADASTERS_DONE": 0, "CADASTERS_SKIP": 0,
                      "STREETS": 0, "FAILED": 0, "ROWS_SKIPPED": 0}
        self.started = time.perf_counter()
        self.cadaster_times: List[float] = []

    def _scale(self, timeout: float) -> float:
        """Ожидание с поправкой на скорость сайта (см. Pacer)."""
        return self.pacer.scale(timeout)


    def load_rows(self) -> List[ExcelRow]:
        self.rows = ExcelReader(self.args.excel).read_rows(self.args.start_row)
        if self.args.limit_rows:
            self.rows = self.rows[:self.args.limit_rows]
            logger.info(f"Строк таблицы ограничено до {len(self.rows)} (--limit-rows)")
        return self.rows

    def next_row(self) -> Optional[ExcelRow]:
        """
        Следующая строка таблицы для нового члена семьи: идём по порядку и не
        берём уже израсходованных людей. Если строки кончились — начинаем круг
        заново (люди повторяются, иначе 30 «Бошқа» не набрать).
        """
        if not self.rows:
            self.load_rows()
        if not self.rows:
            return None
        total = len(self.rows)
        for offset in range(total):
            row = self.rows[(self.row_cursor + offset) % total]
            if row.code not in self.used_rows:
                self.row_cursor = (self.row_cursor + offset + 1) % total
                return row
        row = self.rows[self.row_cursor % total]
        self.row_cursor = (self.row_cursor + 1) % total
        logger.info(f"Строки таблицы кончились — беру повторно: {row.label()}")
        return row


    def table_rows_with_links(self, needle: str) -> List[dict]:
        """
        Строки таблицы, в которых есть ссылка с подстрокой href. Основной путь —
        прокрутка и сбор через a.link; если таких ссылок нет, берём запасной
        разбор строк по любой ссылке (класс ссылки на других страницах иной).
        """
        rows = self.automator._collect_table_rows()
        matched = [r for r in rows if needle in (r.get("href") or "")]
        if matched:
            return matched
        logger.warning(f"Ссылок с «{needle}» через a.link не нашлось — запасной разбор")
        try:
            fallback = self.automator.js(JS_TABLE_LINKS_FILTERED, needle) or []
        except Exception as exc:
            logger.warning(f"Запасной разбор не удался: {str(exc).splitlines()[0][:100]}")
            fallback = []
        return fallback

    def read_streets_from_page(self) -> List[dict]:
        """Улицы со страницы survey_homes (если файла улиц нет)."""
        units: List[dict] = []
        seen = set()
        for item in self.table_rows_with_links("survey_homes_street"):
            href = item.get("href") or ""
            if "survey_homes_street" not in href:
                continue
            url = urljoin(BASE_URL, unescape(href))
            street_id = url_params(url).get("street_id", "")
            if street_id in ("", "0") or street_id in seen:
                continue
            name = " | ".join(x for x in (item.get("cells") or []) if x)[:100] \
                or (item.get("text") or "")
            if any(marker in name.lower() for marker in UNKNOWN_STREET_MARKERS):
                logger.info(f"Улица пропущена («номаълум»): {name}")
                continue
            seen.add(street_id)
            units.append({"url": url, "name": name or f"street_id={street_id}",
                          "street_id": street_id})
        return units

    def street_units(self) -> List[dict]:
        units = parse_streets_file(self.args.streets_file) if self.args.streets_file else []
        source = f"файл {self.args.streets_file}"
        if not units:
            units = self.read_streets_from_page()
            source = "страница survey_homes"
        start = max(1, self.args.streets_from or STREETS_FILE_FROM)
        total = len(units)
        units = units[start - 1:]
        logger.info(f"Улицы: источник {source}, всего {total}, начиная с {start}-й — "
                    f"к обходу {len(units)}")
        return units

    def read_street_links(self) -> List[dict]:
        """Кликабельные кадастры страницы улицы: {cadaster, url, home_id}."""
        found: List[dict] = []
        seen = set()
        for item in self.table_rows_with_links("/forms/survey_homes"):
            href = item.get("href") or ""
            if "/forms/survey_homes" not in href:
                continue
            url = urljoin(BASE_URL, unescape(href))
            home_id = (urlparse(url).path.rstrip("/").split("/") or [""])[-1]
            cells = item.get("cells") or []
            code = ""
            for cell in cells:
                code = self.automator._cadaster_in_text(cell)
                if code:
                    break
            if not code:
                code = self.automator._cadaster_in_text(item.get("text", ""))
            key = home_id or code or url
            if key in seen:
                continue
            seen.add(key)
            found.append({"cadaster": code, "url": url, "home_id": home_id,
                          "text": " | ".join(cells[:5])[:120]})
        return found


    def open_members_tab(self) -> bool:
        for needle in (TAB_TEXT, *TAB_FALLBACKS):
            try:
                clicked = self.automator.js(JS_OPEN_TAB, needle)
            except Exception as exc:
                logger.warning(f"Вкладка: {str(exc).splitlines()[0][:100]}")
                clicked = None
            if clicked:
                logger.info(f"Вкладка открыта: {clicked}")
                time.sleep(AFTER_TAB_OPEN)
                self.automator.wait_page_settled(timeout=self._scale(FORM_READY_TIMEOUT))
                return True
        return False

    def members_count(self) -> int:
        """Сколько строк с «Қариндошлиги» = «Бошқа» уже заведено в кадастре."""
        try:
            rows = self.automator.js(JS_MEMBERS_ROWS) or []
        except Exception as exc:
            logger.warning(f"Чтение таблицы членов семьи: {str(exc).splitlines()[0][:100]}")
            return 0
        count = 0
        for cells in rows:
            for cell in cells:
                if norm_text(cell).strip(" .,") == "бошқа":
                    count += 1
                    break
        actions.info(f"Строк таблицы во вкладке: {len(rows)}, из них «Бошқа»: {count}")
        return count


    def modal(self, timeout: Optional[int] = None):
        timeout = self._scale(FORM_READY_TIMEOUT if timeout is None else timeout)
        started = time.perf_counter()
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.automator.js(JS_MODAL_VISIBLE):
                    self.pacer.observe(time.perf_counter() - started)
                    break
            except Exception:
                pass
            time.sleep(POLL_INTERVAL)
        else:
            return None
        for selector in ("div.vm--modal", "div.modal.show", "div.modal"):
            for element in self.automator.driver.find_elements(By.CSS_SELECTOR, selector):
                try:
                    if not element.is_displayed():
                        continue
                    if not element.find_elements(By.CSS_SELECTOR, "fieldset[data-name]"):
                        continue
                    return element
                except StaleElementReferenceException:
                    continue
                except Exception:
                    continue
        return None

    def _modal_fieldsets(self, modal) -> Dict[str, object]:
        out: Dict[str, object] = {}
        for fs in modal.find_elements(By.CSS_SELECTOR, "fieldset[data-name]"):
            name = (fs.get_attribute("data-name") or "").strip()
            if name:
                out.setdefault(name, fs)
        return out

    def _modal_fieldset(self, modal, names, label_needles=()):
        fieldsets = self._modal_fieldsets(modal)
        for name in names:
            if name in fieldsets:
                return fieldsets[name]
        if label_needles:
            for name, fs in fieldsets.items():
                try:
                    box = fs.find_element(
                        By.XPATH, "ancestor::div[contains(@class,'col-md') or "
                                  "contains(@class,'col-12')][1]")
                    text = norm_text(box.text or "")
                except Exception:
                    text = ""
                if any(norm_text(needle) in text for needle in label_needles):
                    return fs
        return None

    def _fresh_fieldset(self, names, label_needles=(), attempts: int = 3):
        """
        Поле модалки заново: после смены одного списка Vue перерисовывает
        модалку, и прежние ссылки на элементы становятся недействительными.
        """
        for attempt in range(1, attempts + 1):
            modal = self.modal(timeout=2)
            if modal is None:
                time.sleep(POLL_INTERVAL)
                continue
            try:
                fieldset = self._modal_fieldset(modal, names, label_needles)
            except StaleElementReferenceException:
                time.sleep(POLL_INTERVAL)
                continue
            except Exception as exc:
                logger.warning(f"Поиск поля {names[0]}: {str(exc).splitlines()[0][:80]}")
                time.sleep(POLL_INTERVAL)
                continue
            if fieldset is not None:
                return fieldset
        return None

    def _modal_fill(self, names, value: str, label_needles=()) -> bool:
        """
        Ввод в текстовое поле модалки с проверкой прочитанного значения.
        Значение считается введённым только если оно реально стоит в поле.
        """
        if not value:
            return True
        for variant in (value, digits_only(value)):
            if not variant:
                continue
            for attempt in range(1, MEMBER_FILL_ATTEMPTS + 1):
                try:
                    fieldset = self._fresh_fieldset(names, label_needles)
                    if fieldset is None:
                        logger.warning(f"Поле {names[0]} в модалке не найдено")
                        return False
                    field_input = fieldset.find_element(By.CSS_SELECTOR, "input, textarea")
                    read_back = lambda: (field_input.get_attribute("value") or "")
                    if self.automator._fill_input(field_input, variant, read_back=read_back):
                        time.sleep(AFTER_FIELD_PAUSE)
                        current = read_back()
                        if (norm_text(current) == norm_text(variant)
                                or self._same_digits(current, variant)
                                or norm_doc_code(current) == norm_doc_code(variant)):
                            marker = "" if variant == value else " (без маски)"
                            actions.info(f"МОДАЛКА {names[0]} = {current}{marker}")
                            return True
                        logger.warning(f"МОДАЛКА {names[0]}: в поле «{current}», "
                                       f"ожидалось «{variant}»")
                    else:
                        logger.warning(f"МОДАЛКА {names[0]}: «{variant}» не введено "
                                       f"(попытка {attempt}/{MEMBER_FILL_ATTEMPTS})")
                except StaleElementReferenceException:
                    time.sleep(AFTER_ERROR_PAUSE)
                except Exception as exc:
                    logger.warning(f"МОДАЛКА {names[0]}: {str(exc).splitlines()[0][:100]}")
                    time.sleep(AFTER_ERROR_PAUSE)
                time.sleep(AFTER_ERROR_PAUSE)
        return False

    @staticmethod
    def _same_digits(left: str, right: str) -> bool:
        """Сравнение по цифрам: маска телефона и пробелы в ЖШШИР не мешают."""
        left_digits, right_digits = digits_only(left), digits_only(right)
        return bool(left_digits) and left_digits == right_digits

    def _learn_options(self, name: str, names, label_needles=()) -> Dict[str, str]:
        """
        {подпись: значение} для списка. В native select этого сайта подписи
        опций пустые, а тексты рисует select2 — их и читаем, сопоставляя по
        порядку со значениями.
        """
        cached = self.option_maps.get(name)
        if cached:
            return cached
        values: List[str] = []
        texts: List[str] = []
        for attempt in range(1, 3):
            fieldset = self._fresh_fieldset(names, label_needles)
            if fieldset is None:
                return {}
            try:
                state = self.automator.js(JS_FIELDSET_SELECT_STATE, fieldset) or {}
                values = [str(item.get("value")) for item in state.get("options", [])]
                if not self.automator._open_dropdown(fieldset):
                    self.automator._close_dropdown()
                    continue
                texts = []
                for option in self.automator._visible_options():
                    text = " ".join((option.text or "").split())
                    if text:
                        texts.append(text)
                self.automator._close_dropdown()
                if texts:
                    break
            except StaleElementReferenceException:
                self.automator._close_dropdown()
                time.sleep(POLL_INTERVAL)
            except Exception as exc:
                logger.warning(f"Список {name}: чтение вариантов — "
                               f"{str(exc).splitlines()[0][:100]}")
                self.automator._close_dropdown()
                time.sleep(POLL_INTERVAL)

        mapping: Dict[str, str] = {}
        if texts and values:
            if len(texts) != len(values):


                logger.warning(f"Список {name}: вариантов {len(texts)}, значений "
                               f"{len(values)} — карта не строится, только выбор кликом")
            else:
                mapping = {norm_text(t): v for t, v in zip(texts, values)}
        self.option_maps[name] = mapping
        actions.info(f"СПИСОК {name}: {brief(mapping)}")
        return mapping

    def _modal_select(self, names, value: str, label_needles=()) -> bool:
        """
        Выбор варианта списка в модалке.

        Порядок важен для правильности данных: сначала пробуем кликнуть по
        варианту в открытом списке и сверяем, что именно он отрисовался в поле.
        Только если клик невозможен, ставим значение из выученной карты, и
        результат так же проверяем по отрисованному тексту. Ни одно значение не
        принимается без проверки: ошибка тут приводит к тому, что сайт ругается
        на несоответствие данных.
        """
        fieldset = self._fresh_fieldset(names, label_needles)
        if fieldset is None:
            logger.warning(f"Список {names[0]} в модалке не найден")
            return False
        name = (fieldset.get_attribute("data-name") or names[0])
        target = norm_text(value)

        for attempt in range(1, MEMBER_FILL_ATTEMPTS + 1):
            try:
                fieldset = self._fresh_fieldset(names, label_needles)
                if fieldset is None:
                    time.sleep(AFTER_ERROR_PAUSE)
                    continue

                if self._click_option_in_fieldset(fieldset, value, name):
                    return True
                if self._set_value_from_map(fieldset, names, label_needles, value, name):
                    return True
            except StaleElementReferenceException:
                time.sleep(AFTER_ERROR_PAUSE)
            except Exception as exc:
                logger.warning(f"МОДАЛКА {name}: {str(exc).splitlines()[0][:100]}")
                self.automator._close_dropdown()
                time.sleep(AFTER_ERROR_PAUSE)
            logger.warning(f"МОДАЛКА {name}: «{value}» не выбрано "
                           f"(попытка {attempt}/{MEMBER_FILL_ATTEMPTS})")
            time.sleep(AFTER_ERROR_PAUSE)

        self.automator._close_dropdown()
        self.automator._log_field_html(name)
        logger.warning(f"МОДАЛКА {name}: «{value}» не выбрано. Варианты: "
                       f"{brief(self.automator._option_texts())}")
        return False

    def _click_option_in_fieldset(self, fieldset, value: str, name: str) -> bool:
        """
        Открыть список, кликнуть по подходящему варианту и убедиться, что он
        подставился. Возвращает True только при подтверждённой подстановке.
        """
        if not self.automator._open_dropdown(fieldset):
            self.automator._close_dropdown()
            return False
        time.sleep(AFTER_FIELD_PAUSE)
        picked = self.automator._pick_option_exact(value, timeout=OPTION_WAIT_TIMEOUT)
        if not picked:
            self.automator._type_in_search(value[:8])
            picked = self.automator._pick_option_exact(value,
                                                       timeout=OPTION_WAIT_AFTER_TYPE)
        if not picked:
            self.automator._close_dropdown()
            actions.info(f"МОДАЛКА {name}: в списке нет «{value}»")
            return False
        time.sleep(AFTER_FIELD_PAUSE)
        if self._verify_selection(names=(name,), expected=picked, label=name):
            actions.info(f"МОДАЛКА {name} = {picked} (клик по варианту)")
            return True
        logger.warning(f"МОДАЛКА {name}: клик по «{picked}» не подтвердился")
        self.automator._close_dropdown()
        time.sleep(AFTER_ERROR_PAUSE)
        return False

    def _set_value_from_map(self, fieldset, names, label_needles, value: str,
                            name: str) -> bool:
        """
        Значение из выученной карты {подпись: значение}. Принимается только
        после проверки отрисованного текста: карта строится по порядку, и без
        сверки ошибка сопоставления ушла бы на сайт молча.
        """
        mapping = self._learn_options(name, names, label_needles) or {}
        if not mapping:
            return False
        target = norm_text(value)
        value_id = mapping.get(target)
        if not value_id:
            value_id = next((vid for text, vid in mapping.items() if target in text), "")
        if not value_id:
            return False
        set_value = self.automator.js(JS_SET_FIELDSET_SELECT_VALUE, fieldset, value_id)
        time.sleep(AFTER_FIELD_PAUSE)
        if str(set_value) != str(value_id):
            return False
        if self._verify_selection(names=(name,), expected=value, label=name):
            actions.info(f"МОДАЛКА {name} = {value} (значение {value_id})")
            return True
        return False

    def _verify_selection(self, names, expected: str, label: str = "") -> bool:
        """
        Что реально стоит в списке сейчас. Сверяем отрисованный текст, а при
        его отсутствии — текст опции, выбранной в нативном select.
        """
        try:
            fieldset = self._fresh_fieldset(names)
            if fieldset is None:
                return False
            state = self.automator.js(JS_FIELDSET_SELECT_STATE, fieldset) or {}
        except Exception:
            return False
        current = norm_text(state.get("rendered") or "")
        if not current:
            selected = str(state.get("value") or "")
            for item in state.get("options", []):
                if str(item.get("value")) == selected:
                    current = norm_text(item.get("text") or "")
                    break
        target = norm_text(expected)
        if not target:
            return False
        if current == target or current.startswith(target) or target.startswith(current):
            return True
        if current and norm_doc_code(current) == norm_doc_code(target):
            return True
        logger.warning(f"МОДАЛКА {label or names[0]}: ожидалось «{expected}», "
                       f"в поле «{state.get('rendered')}»")
        return False

    def _modal_click(self, xpaths: List[str]) -> bool:
        for attempt in range(1, SELECT_ATTEMPTS + 1):
            modal = self.modal(timeout=2)
            if modal is None:
                continue
            for xpath in xpaths:
                try:
                    elements = modal.find_elements(By.XPATH, xpath)
                except Exception:
                    continue
                for button in elements:
                    try:
                        if not button.is_displayed():
                            continue
                        self.automator.js(
                            "arguments[0].scrollIntoView({block:'center'});", button)
                        try:
                            button.click()
                        except Exception:
                            self.automator.js("arguments[0].click();", button)
                        actions.info(f"МОДАЛКА клик: {xpath[:60]}")
                        return True
                    except StaleElementReferenceException:
                        break
                    except Exception:
                        continue
        return False

    def _wait_member_search(self) -> bool:
        """Ждём, пока «Қидириш» подтянет ЖШШИР и Ф.И.Ш. в поля модалки."""
        timeout = self._scale(SEARCH_RESULT_TIMEOUT)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                filled = self.automator.js(JS_MODAL_FIELDS) or []
            except Exception:
                filled = []
            values = {item.get("name"): (item.get("value") or "") for item in filled}
            pinfl_ok = any(v for k, v in values.items() if k and "pinfl" in k)
            name_ok = any(v for k, v in values.items()
                          if k and ("fio" in k or "name" in k))
            if name_ok and (pinfl_ok or values.get("full_name")):
                actions.info(f"МОДАЛКА: данные подтянулись | {brief(values)}")
                return True
            notices = self.automator.capture_notices(settle=NOTICE_SETTLE_QUICK)
            if notices:
                logger.warning("Модалка: уведомление при поиске — " + " || ".join(notices))
                return False
            time.sleep(POLL_INTERVAL)
        logger.warning("Модалка: ЖШШИР/Ф.И.Ш. не подтянулись за "
                       f"{timeout:.0f} с | поля: {brief(values)}")
        return False

    def close_member_modal(self) -> bool:
        """
        Закрыть модалку члена семьи. Нужна, чтобы после неудачной строки
        следующая начиналась с чистого окна, а не с «залипшей» формы.
        """
        try:
            closed = self.automator.js(JS_MODAL_CLOSE)
        except Exception as exc:
            logger.warning(f"Закрытие модалки: {str(exc).splitlines()[0][:80]}")
            return False
        actions.info(f"МОДАЛКА: закрытие → {closed}")
        if str(closed).startswith(("clicked", "esc")):
            time.sleep(AFTER_MODAL_CLOSE)
            return not self.automator.js(JS_MODAL_VISIBLE)
        return False


    def _fill_member_fields(self, row: ExcelRow) -> List[str]:
        """
        Заполнить поля открытой модалки. Возвращает список того, что не встало:
        по нему вызывающий код решает, переоткрывать форму или идти дальше.
        """
        problems: List[str] = []
        if not self._modal_select(RELATION_NAMES, RELATION_VALUE, ("қариндош",)):
            problems.append("қариндошлиги")

        doc_ok = False
        for needle in row.doc_type_needles():
            if self._modal_select(DOC_TYPE_NAMES, needle,
                                  ("ҳужжат тури", "документ тури")):
                doc_ok = True
                break
        if not doc_ok:
            problems.append("ҳужжат тури")

        if not self._modal_fill(DOC_SERIES_NAMES, row.doc_series,
                                ("серия", "серияси")):
            problems.append("ҳужжат серияси")
        if not self._modal_fill(DOC_NUMBER_NAMES, row.doc_number,
                                ("рақам", "рақами")):
            problems.append("ҳужжат рақами")
        if not self._modal_fill(MEMBER_BIRTH_NAMES, row.birth_date(),
                                ("туғилган", "тугилган")):
            problems.append("туғилган санаси")

        pinfl = row.pinfl_digits()
        if pinfl and not self._modal_fill(PINFL_NAMES, pinfl,
                                          ("жшшир", "пинфл", "jshshir")):
            problems.append("жшшир")
        return problems

    def _reopen_modal(self) -> bool:
        """Закрыть модалку и открыть заново: чистая форма без зависших списков."""
        self.close_member_modal()
        time.sleep(AFTER_MODAL_CLOSE)
        clicked = self.automator.js(JS_CLICK_MEMBER_SAVE)
        if str(clicked) == "not-found":
            return False
        if self.modal(timeout=FORM_READY_TIMEOUT) is None:
            return False
        self.automator.wait_page_settled(timeout=self._scale(FORM_READY_TIMEOUT))
        return self.modal(timeout=FORM_READY_TIMEOUT) is not None

    def add_member(self, row: ExcelRow) -> Tuple[bool, str]:
        automator = self.automator
        before = self.members_count()
        automator.close_notices()
        automator.http_errors(clear=True)

        clicked = automator.js(JS_CLICK_MEMBER_SAVE)
        actions.info(f"МОДАЛКА: «Сақлаш» на вкладке → {clicked}")
        if str(clicked) == "not-found":
            return False, "кнопка «Сақлаш» на вкладке не найдена"

        modal = self.modal(timeout=FORM_READY_TIMEOUT)
        if modal is None:
            actions.info("МОДАЛКА: повторное нажатие «Сақлаш» на вкладке")
            automator.js(JS_CLICK_MEMBER_SAVE)
            modal = self.modal(timeout=FORM_READY_TIMEOUT)
        if modal is None:
            automator._screenshot("member_modal_fail")
            return False, "модалка «Оила аъзосини киритиш» не открылась"
        automator.wait_page_settled(timeout=self._scale(FORM_READY_TIMEOUT))
        modal = self.modal(timeout=FORM_READY_TIMEOUT) or modal
        fields = automator.js(JS_MODAL_FIELDS) or []
        actions.info(f"МОДАЛКА поля: {brief([f.get('name') for f in fields])}")

        problems = self._fill_member_fields(row)
        if [p for p in problems if p in MODAL_CRITICAL_PROBLEMS]:
            actions.info(f"МОДАЛКА: повторное заполнение после — {brief(problems)}")
            if self._reopen_modal():
                problems = self._fill_member_fields(row)
        if problems:
            actions.info(f"МОДАЛКА: не заполнено — {brief(problems)}")
            logger.warning("Модалка: не заполнено — " + "; ".join(problems))

        try:
            search = automator.js(JS_SEARCH_MEMBER_CLICK)
        except Exception as exc:
            search = f"error:{str(exc).splitlines()[0][:80]}"
        actions.info(f"МОДАЛКА: «Қидириш» (ЖШШИР) → {search}")
        if str(search).startswith("clicked"):
            self._wait_member_search()
        else:
            problems.append("«Қидириш» не нажата")
            automator._screenshot("member_search_fail")

        if not self._modal_select(EDUCATION_NAMES, EDUCATION_VALUE,
                                  ("маълумоти", "маълумот")):
            problems.append("маълумоти")
        phone = row.get_formatted_phone()
        if not self._modal_fill(PHONE_NAMES, phone, ("телефон",)):
            problems.append("телефон")


        empty = self._empty_required_fields()
        if empty:
            logger.warning("Модалка: пустые обязательные поля — "
                           + ", ".join(f"{item.get('label') or item.get('name')}"
                                       for item in empty))
            if not self._refill_required(row, empty):
                automator._screenshot("member_required_empty")
                self.close_member_modal()
                return False, ("не заполнены обязательные поля: "
                               + ", ".join(str(item.get("name")) for item in empty))

        time.sleep(AFTER_FIELD_PAUSE)
        result = automator.js(JS_MODAL_SAVE_CLICK)
        actions.info(f"МОДАЛКА: «Сақлаш» → {result}")
        if not str(result).startswith("clicked"):
            automator._screenshot("member_save_fail")
            self.close_member_modal()
            return False, f"«Сақлаш» в модалке не нажата ({result})"
        time.sleep(AFTER_SAVE_PAUSE)

        toasts = self._wait_member_toast()
        notices: List[str] = []
        for toast in toasts:
            text = (toast.get("title", "") + ": " + toast.get("body", "")).strip(": ")
            if text and text not in notices:
                notices.append(text)
        if notices:
            logger.info("Модалка: уведомление — " + " || ".join(notices))

        rate_wait = self._rate_limit_wait(toasts)
        if rate_wait:
            automator.close_notices()
            self.close_member_modal()
            logger.warning(f"   ⏳ сайт ограничил запросы: пауза {rate_wait} с")
            time.sleep(rate_wait)
            return False, RATE_LIMIT_PREFIX + " || ".join(notices)

        if any(t.get("kind") == "ok" for t in toasts):
            automator.http_errors(clear=True)
            after = self._wait_member_added(before, timeout=SAVE_NOTICE_QUICK_TIMEOUT)
            if after > before or "сақланди" in norm_text(" ".join(notices)):
                automator.close_notices()
                actions.info(f"МОДАЛКА: член семьи добавлен ({before} → {after})")
                return True, ""

        http_text = automator.format_http_errors(automator.http_errors(clear=True))
        if http_text:
            notices.append(http_text)


        failed_toast = any(t.get("kind") in ("error", "warn") for t in toasts) or bool(http_text)
        after = self._wait_member_added(
            before, timeout=SAVE_NOTICE_QUICK_TIMEOUT if failed_toast else SAVE_NOTICE_TIMEOUT)
        if after > before:
            automator.close_notices()
            actions.info(f"МОДАЛКА: член семьи добавлен ({before} → {after})")
            return True, ""

        problem = "; ".join(problems) if problems else "счётчик «Бошқа» не вырос"
        automator._screenshot("member_fail")
        automator.close_notices()
        self.close_member_modal()
        reason = problem + (" | " + " || ".join(notices) if notices else "")
        if self._row_rejected_by_site(reason):

            self.members.mark_row_used(row.code)
            self.used_rows.add(row.code)
            actions.info(f"СТРОКА {row.label()} помечена использованной "
                         f"(сайт: уже есть в другом хонадоне)")
            return False, ROW_SKIP_PREFIX + reason
        return False, reason

    def _empty_required_fields(self) -> List[dict]:
        """Обязательные поля модалки, которые остались пустыми."""
        try:
            empty = self.automator.js(JS_EMPTY_REQUIRED)
        except Exception as exc:
            logger.warning(f"Модалка: проверка обязательных полей — "
                           f"{str(exc).splitlines()[0][:80]}")
            return []
        return empty or []

    def _refill_required(self, row: ExcelRow, empty: List[dict]) -> bool:
        """
        Дозаполнить пустые обязательные поля теми же данными строки.
        Возвращает True, если после попытки пустых полей не осталось.
        """
        handlers = {
            "relationship": lambda: self._modal_select(
                RELATION_NAMES, RELATION_VALUE, ("қариндош",)),
            "document_type": lambda: any(
                self._modal_select(DOC_TYPE_NAMES, needle, ("ҳужжат тури", "документ тури"))
                for needle in row.doc_type_needles()),
            "doc_serial": lambda: self._modal_fill(
                DOC_SERIES_NAMES, row.doc_series, ("серия", "серияси")),
            "doc_number": lambda: self._modal_fill(
                DOC_NUMBER_NAMES, row.doc_number, ("рақам", "рақами")),
            "birth_date": lambda: self._modal_fill(
                MEMBER_BIRTH_NAMES, row.birth_date(), ("туғилган", "тугилган")),
            "pinfl": lambda: self._modal_fill(
                PINFL_NAMES, row.pinfl_digits(), ("жшшир", "пинфл", "jshshir")),
            "phone": lambda: self._modal_fill(
                PHONE_NAMES, row.get_formatted_phone(), ("телефон",)),
            "study_level_id": lambda: self._modal_select(
                EDUCATION_NAMES, EDUCATION_VALUE, ("маълумоти", "маълумот")),
        }
        for item in empty:
            name = str(item.get("name") or "")
            handler = handlers.get(name)
            if handler is None:
                logger.warning(f"Модалка: поле {name} нечем дозаполнить")
                continue
            actions.info(f"МОДАЛКА: дозаполняю {name}")
            handler()
            time.sleep(AFTER_FIELD_PAUSE)
        time.sleep(AFTER_FIELD_PAUSE)
        left = self._empty_required_fields()
        if left:
            logger.warning("Модалка: после дозаполнения пусто — "
                           + ", ".join(str(item.get("name")) for item in left))
        return not left

    def _wait_member_toast(self, timeout: Optional[int] = None) -> List[dict]:
        """
        Ждёт тост сайта после «Сақлаш» и возвращает его разбор:
        kind (ok/warn/error/info), title, body. Читается тот же узел, что и
        «Хатолик / Request failed with status code 400».
        """
        timeout = self._scale(TOAST_WAIT_TIMEOUT if timeout is None else timeout)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                toasts = self.automator.js(JS_TOAST_STATE) or []
            except Exception:
                toasts = []
            if toasts:
                actions.info(f"ТОСТЫ после «Сақлаш»: {brief(toasts)}")
                time.sleep(TOAST_SETTLE)
                try:
                    more = self.automator.js(JS_TOAST_STATE) or []
                except Exception:
                    more = []
                keys = {t.get("body", "") for t in toasts}
                toasts += [t for t in more if t.get("body", "") not in keys]
                return toasts
            time.sleep(TOAST_POLL_INTERVAL)
        actions.info("ТОСТЫ после «Сақлаш»: нет")
        return []

    def _rate_limit_wait(self, toasts: List[dict]) -> int:
        """«So'rovlar ko'payib ketdi. N soniya kuting» — сколько секунд подождать."""
        for toast in toasts:
            text = norm_text(f"{toast.get('title', '')} {toast.get('body', '')}")
            if "soniya kuting" in text or "секунд кут" in text:
                found = re.search(r"(\d+)\s*(soniya|секунд)", text)
                wait = int(found.group(1)) if found else RATE_LIMIT_DEFAULT_WAIT
                return min(wait + RATE_LIMIT_EXTRA, RATE_LIMIT_MAX_WAIT)
        return 0

    def _row_rejected_by_site(self, reason: str) -> bool:
        """Сайт отказал по самой строке — повторять её бессмысленно."""
        text = norm_text(reason)
        return any(marker in text for marker in ROW_SKIP_MARKERS)

    def _wait_member_added(self, before: int, timeout: int = SAVE_NOTICE_TIMEOUT) -> int:
        deadline = time.time() + self._scale(timeout)
        count = before
        while time.time() < deadline:
            if self.automator.js(JS_MODAL_VISIBLE):
                time.sleep(POLL_INTERVAL)
                continue
            count = self.members_count()
            if count > before:
                return count
            time.sleep(POLL_INTERVAL)
        return count


    def process_cadaster(self, unit: dict, link: dict) -> None:
        key = link["url"] or f"{unit['street_id']}:{link['home_id']}"
        label = link["cadaster"] or f"хонадон {link['home_id']}"
        self.stats["CADASTERS"] += 1

        if self.members.is_done(key, self.args.target) and not self.args.rescan_cadasters:
            self.stats["CADASTERS_SKIP"] += 1
            logger.info(f"↷ {label} — уже набрано {self.members.count(key)}/"
                        f"{self.args.target} «Бошқа», пропуск")
            return

        logger.info("─" * 60)
        logger.info(f"[кадастр] {label} | {unit['name'][:60]}")
        actions.info("=" * 70)
        actions.info(f"КАДАСТР {label} | {key} | улица {unit['name'][:60]} | "
                     f"уже «Бошқа» {self.members.count(key)}")

        started = time.perf_counter()
        count = self.members.count(key)
        failures = 0
        deadline = time.time() + CADASTER_TIMEOUT
        status, info = "OK", ""

        with timed("Открытие кадастра", label):
            if not self.automator.alive():
                self.automator.restart()
            self.automator.open_url(
                link["url"], wait_selector="a.nav-link", timeout=STREET_READY_TIMEOUT)
        if not self.open_members_tab():
            self.automator._screenshot("members_tab_fail")
            status, info = "FAILED", "Вкладка «Хонадон аъзолари» не найдена"
            self._finish_cadaster(unit, link, key, label, status, info, count, started)
            return

        count = self.members_count()
        self.members.set_count(key, count, street=unit["name"], street_id=unit["street_id"],
                               cadaster=link["cadaster"], home_id=link["home_id"],
                               url=link["url"])
        logger.info(f"   «Бошқа» сейчас: {count} (цель {self.args.target})")

        while count < self.args.target:
            if time.time() > deadline:
                status, info = "FAILED", f"таймаут кадастра ({CADASTER_TIMEOUT} с)"
                logger.warning(f"   {info}")
                break
            if failures >= MEMBER_FAIL_LIMIT:
                status, info = "FAILED", f"подряд не сохранено {failures} членов семьи"
                logger.warning(f"   {info}")
                break
            row = self.next_row()
            if row is None:
                status, info = "FAILED", "в таблице нет строк с документами"
                break

            actions.info(f"ЧЛЕН СЕМЬИ {count + 1}/{self.args.target}: {row.label()}")
            member_started = time.perf_counter()
            try:
                ok, reason = self.add_member(row)
            except WebDriverException as exc:

                logger.warning(f"   Браузер потерян ({str(exc).splitlines()[0][:80]}) — "
                               f"перезапуск")
                count = self._reload_cadaster(link)
                continue
            elapsed = time.perf_counter() - member_started
            if ok:
                failures = 0
                count += 1
                self.stats["MEMBERS"] += 1
                self.members.mark_row_used(row.code)
                self.used_rows.add(row.code)
                self.progress.mark(row.code, "член семьи добавлен")
                self.members.set_count(key, count, street=unit["name"],
                                       street_id=unit["street_id"],
                                       cadaster=link["cadaster"], home_id=link["home_id"],
                                       url=link["url"])
                logger.info(f"   ✔ «Бошқа» {count}/{self.args.target} — {row.label()} "
                            f"за {elapsed:.2f} с")
            else:
                if reason.startswith(RATE_LIMIT_PREFIX):

                    logger.warning(f"   ⏳ лимит запросов, строка остаётся в очереди: "
                                   f"{row.label()}")
                    time.sleep(MEMBER_PAUSE)
                    continue

                self.members.mark_row_used(row.code)
                self.used_rows.add(row.code)
                self.stats["ROWS_SKIPPED"] += 1
                if reason.startswith(ROW_SKIP_PREFIX):
                    self.progress.mark(row.code, "пропущена (уже в другом хонадоне)")
                    logger.warning(f"   ↷ строка пропущена (уже введена на сайте): "
                                   f"{row.label()}")
                else:
                    failures += 1
                    self.stats["MEMBER_FAIL"] += 1
                    self.progress.mark(row.code, "пропущена (ошибка)")
                    logger.warning(f"   ↷ строка пропущена (ошибка {failures}/"
                                   f"{MEMBER_FAIL_LIMIT}): {reason[:160]} за "
                                   f"{elapsed:.2f} с")
                    if failures % FULL_RESET_AFTER_FAILURES == 0:


                        logger.warning(f"   ⟳ полная перезагрузка формы после "
                                       f"{failures} ошибок подряд")
                        count = self._reload_cadaster(link)
                        continue
            time.sleep(MEMBER_PAUSE)

        self._finish_cadaster(unit, link, key, label, status, info, count, started)

    def _reload_cadaster(self, link: dict) -> int:
        """
        Переоткрыть форму кадастра и вернуть актуальное число «Бошқа».
        Нужно после потери браузера или серии ошибок.
        """
        if not self.automator.alive():
            self.automator.restart()
        else:
            self.close_member_modal()
        self.automator.open_url(link["url"], wait_selector="a.nav-link",
                                timeout=self._scale(STREET_READY_TIMEOUT))
        self.open_members_tab()
        count = self.members_count()
        logger.info(f"   «Бошқа» после перезагрузки формы: {count}")
        return count

    def _finish_cadaster(self, unit: dict, link: dict, key: str, label: str,
                         status: str, info: str, count: int, started: float) -> None:
        elapsed = time.perf_counter() - started
        self.cadaster_times.append(elapsed)
        self.members.set_count(key, count, street=unit["name"], street_id=unit["street_id"],
                               cadaster=link["cadaster"], home_id=link["home_id"],
                               url=link["url"], done=count >= self.args.target)
        if count >= self.args.target:
            self.stats["CADASTERS_DONE"] += 1
            status = "OK" if status == "OK" else "OK_WARN"
            logger.info(f"   итог {label}: «Бошқа» {count}/{self.args.target}, "
                        f"{elapsed:.2f} с")
        else:
            self.stats["FAILED"] += 1
            logger.warning(f"   итог {label}: «Бошқа» {count}/{self.args.target}, "
                           f"{info or 'не набрано'} — {elapsed:.2f} с")

        self.report.add(SHEET_OK if count >= self.args.target else SHEET_ERRORS,
                        unit["name"], label, "", "", "", "",
                        "ГОТОВО" if count >= self.args.target else "НЕ НАБРАНО",
                        info or f"«Бошқа» {count}/{self.args.target}",
                        "", link["url"])
        if count < self.args.target:
            self.report.add_not_entered(unit["name"], label, "", "", "", "",
                                        f"«Бошқа» {count}/{self.args.target}. {info}")
        self.cadasters.add(link["cadaster"] or link["home_id"],
                           f"члены семьи: «Бошқа» {count}/{self.args.target}",
                           unit["name"])
        actions.info(f"ИТОГ КАДАСТРА {label}: «Бошқа»={count}, статус={status} | "
                     f"{elapsed:.2f} с")


    def run(self) -> None:
        self.load_rows()
        self.automator.start()
        processed = 0
        try:
            self.automator.open_url(SURVEY_URL)
            self.automator.remember_main_window()
            self.automator._close_extra_windows()
            self.automator.wait_for_login()

            units = self.street_units()
            self.stats["STREETS"] = len(units)
            for street_idx, unit in enumerate(units, 1):
                if self.args.limit and processed >= self.args.limit:
                    logger.info("Достигнут лимит кадастров (--limit) — останавливаюсь")
                    break
                if self.args.street_id and unit["street_id"] != self.args.street_id:
                    continue
                logger.info("═" * 60)
                logger.info(f"[улица {street_idx}/{len(units)}] {unit['name'][:70]}")
                actions.info("=" * 70)
                actions.info(f"УЛИЦА {street_idx}/{len(units)}: {unit['url']} | "
                             f"{unit['name'][:70]}")
                if not self.automator.alive():
                    self.automator.restart()
                self.automator.open_street(unit["url"])
                links = self.read_street_links()
                logger.info(f"   кадастров на странице: {len(links)}")
                self.automator.sleep_if_rate_limited()
                if not links:
                    self.automator._screenshot("street_no_cadasters")
                    continue

                for link in links:
                    if self.args.limit and processed >= self.args.limit:
                        break
                    if self.args.cadaster and self.args.cadaster not in link["url"] \
                            and self.args.cadaster not in (link["cadaster"] or ""):
                        continue
                    if not self.automator.alive():
                        self.automator.restart()
                    self.process_cadaster(unit, link)
                    processed += 1
                    time.sleep(self.args.delay)
        finally:
            self._print_summary()
            self.automator.close()

    def _print_summary(self) -> None:
        s = self.stats
        logger.info("═" * 60)
        logger.info(f"Членов семьи добавлено: {s['MEMBERS']} | не удалось: {s['MEMBER_FAIL']}")
        logger.info(f"Строк пропущено (уже введены на сайте): {s['ROWS_SKIPPED']} | "
                    f"израсходовано строк таблицы: {len(self.members.used)}")
        logger.info(f"Кадастров пройдено: {s['CADASTERS']} | доведено до "
                    f"{self.args.target} «Бошқа»: {s['CADASTERS_DONE']} | "
                    f"пропущено (уже готовы): {s['CADASTERS_SKIP']} | "
                    f"не набрано: {s['FAILED']}")
        logger.info(f"Улиц: {s['STREETS']} | состояние: {MEMBERS_STATE_FILE} "
                    f"({len(self.members.cadasters)} кадастров)")
        logger.info(f"Реестр кадастров: {len(self.cadasters.known)} ({CADASTERS_FILE})")
        logger.info(f"Отчёт: {self.report.path}")
        if self.cadaster_times:
            total = sum(self.cadaster_times)
            logger.info(f"Время работы: {time.perf_counter() - self.started:.2f} с | "
                        f"кадастров: {len(self.cadaster_times)} | среднее: "
                        f"{total / len(self.cadaster_times):.2f} с | мин: "
                        f"{min(self.cadaster_times):.2f} с | макс: "
                        f"{max(self.cadaster_times):.2f} с")
        else:
            logger.info(f"Время работы: {time.perf_counter() - self.started:.2f} с | "
                        f"обработанных кадастров нет")
        logger.info(f"Подробный лог действий: {ACTIONS_LOG_FILE}")
        logger.info("═" * 60)
