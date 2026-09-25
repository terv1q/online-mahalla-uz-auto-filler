from .profile import SessionProfile
import difflib
import json
import time

from .js import (
    HTTP_HOOK_JS,
    JS_ADD_HOME_HREF,
    JS_ALL_FIELDSETS,
    JS_BROWSER_ERROR_PAGE,
    JS_CHECK_TARGETS,
    JS_CLEAR_FORM,
    JS_CLICK,
    JS_CLOSE_SELECT,
    JS_CLOSE_TOASTS,
    JS_FIELDSET_HTML,
    JS_FIELD_SNAPSHOT,
    JS_FOCUS,
    JS_NOTICES,
    JS_PAGE_SIGNATURE,
    JS_PAGE_STREET_NAME,
    JS_PENDING_REQUESTS,
    JS_SCROLL_CENTER,
    JS_SCROLL_STEP,
    JS_SCROLL_TOP,
    JS_SELECT_NATIVE_BY_INDEX,
    JS_SELECT_NATIVE_BY_NEEDLE,
    JS_SELECT_OPTION_VALUES,
    JS_SELECT_RENDERED,
    JS_SELECT_VALUE_BY_NAME,
    JS_SET_INPUT,
    JS_SET_SELECT_VALUE,
    JS_SPINNER_VISIBLE,
    JS_TABLE_ROWS,
)
from .logs import (
    actions,
    brief,
    logger,
    timed,
)
from .selectors import (
    ADD_HOME_CSS,
    ADD_HOME_XPATHS,
    BIRTH_FIELD,
    CADASTER_EXISTS_MARKERS,
    CADASTER_IN_TEXT,
    CADASTER_NAMES,
    CADASTER_PLACEHOLDER,
    CADASTER_SELECTOR,
    CHECKBOX_TARGETS,
    CLOSE_MODAL_XPATHS,
    COOLDOWN_RE,
    ERROR_MARKERS,
    ERROR_TITLES,
    ERR_EXISTS,
    FORM_CLEAR_NAMES,
    FORM_KEEP_NAMES,
    FORM_PERSON_CLEAR_NAMES,
    HOME_NUM_SELECTOR,
    HOME_REGISTERED_NAMES,
    HOME_REGISTERED_VALUE,
    HOME_TYPE_NAMES,
    HOME_TYPE_VALUE,
    HOUSE_NAMES,
    LOGIN_MARKER_XPATH,
    NEGATION_MARKERS,
    OPENER_SELECTORS,
    OPTION_SELECTORS,
    OWNERSHIP_NAMES,
    OWNERSHIP_VALUE,
    PERSON_FIELD_MARKERS,
    PINFL_FIELD,
    PINFL_SEARCH_XPATHS,
    RATE_LIMIT_MARKERS,
    SAVE_XPATHS,
    SEARCH_INPUT_SELECTOR,
    STREET_NAMES,
    STUDY_LEVEL_NAMES,
    STUDY_LEVEL_VALUE,
    SUCCESS_MARKERS,
)
from .settings import (
    BASE_URL,
    HEADLESS,
    HTTP_ERRORS_LIMIT,
    PROFILE_NAME,
    SAVE_SCREENSHOTS,
    STREET_MATCH_THRESHOLD,
    USER_DATA_DIR,
)
from .timing import (
    AFTER_CADASTER_PAUSE,
    AFTER_CLICK_PAUSE,
    AFTER_DROPDOWN_OPEN,
    AFTER_INPUT_PAUSE,
    AFTER_OPTION_CLICK,
    AFTER_SEARCH_TYPE,
    AFTER_TAB_OPEN,
    BROWSER_RESTART_PAUSE,
    COOLDOWN_DEFAULT,
    COOLDOWN_EXTRA,
    DROPDOWN_FIELDSET_TIMEOUT,
    ELEMENT_WAIT_TIMEOUT,
    FIELD_ATTEMPTS,
    FIELD_VALUE_CHECKS,
    FORM_READY_TIMEOUT,
    MAX_COOLDOWN,
    NOTICE_POLL_INTERVAL,
    NOTICE_SETTLE_DEFAULT,
    NOTICE_SETTLE_QUICK,
    OPEN_URL_ATTEMPTS,
    OPTION_WAIT_AFTER_TYPE,
    OPTION_WAIT_SHORT,
    OPTION_WAIT_TIMEOUT,
    PAGE_LOAD_TIMEOUT,
    POLL_INTERVAL,
    RETRY_PAUSE,
    REUSE_FORM_TIMEOUT,
    ROW_TIMEOUT,
    SAVE_ATTEMPTS,
    SAVE_CONFIRM_TIMEOUT,
    SAVE_NOTICE_TIMEOUT,
    SEARCH_ATTEMPTS,
    SEARCH_RESULT_TIMEOUT,
    SELECT_ATTEMPTS,
    SITE_FROZEN_TIMEOUT,
    STREET_READY_TIMEOUT,
    TABLE_SCROLL_PAUSE,
    TAB_CHECKBOX_TIMEOUT,
)
from .utils import (
    classify_error,
    digits_only,
    merge_url_params,
    norm_street,
    norm_text,
    normalize_code,
    url_params,
)
from datetime import datetime, timedelta
from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse


class BrowserAutomator:
    def __init__(self, profile: SessionProfile, debug_select: bool = False):
        self.profile = profile
        self.debug_select = debug_select
        self.driver: Optional[webdriver.Edge] = None
        self.current_street_url: str = ""
        self.main_handle: str = ""
        self.form_handle: str = ""
        Path(self.profile.screenshot_dir).mkdir(parents=True, exist_ok=True)


    def start(self) -> None:
        options = Options()
        Path(USER_DATA_DIR).mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
        options.add_argument(f"--profile-directory={PROFILE_NAME}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        if HEADLESS:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1920,1080")
        self.driver = webdriver.Edge(options=options)


        try:
            self.driver.set_page_load_strategy("eager")
        except Exception:
            pass
        self.driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        for source in ("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});",
                       HTTP_HOOK_JS):
            try:
                self.driver.execute_cdp_cmd(
                    "Page.addScriptToEvaluateOnNewDocument", {"source": source})
            except Exception:
                pass
        try:
            self.driver.execute_script(HTTP_HOOK_JS)
        except Exception:
            pass
        logger.info("Браузер запущен")

    def close(self) -> None:
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        finally:
            self.driver = None

    def restart(self) -> None:
        logger.warning("Перезапуск браузера")
        self.close()
        time.sleep(BROWSER_RESTART_PAUSE)
        self.start()
        self.current_street_url = ""
        self.main_handle = ""
        self.form_handle = ""

    def alive(self) -> bool:
        try:
            _ = self.driver.current_url
            return True
        except Exception:
            return False

    def js(self, script: str, *args):
        return self.driver.execute_script(script, *args)

    def _screenshot(self, prefix: str) -> str:
        if not SAVE_SCREENSHOTS or not self.driver:
            return ""
        try:
            name = Path(self.profile.screenshot_dir) / (
                f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            self.driver.save_screenshot(str(name))
            return str(name)
        except Exception:
            return ""


    def _page_busy(self) -> bool:
        try:
            if self.js("return document.readyState") != "complete":
                return True
            if self.js(JS_PENDING_REQUESTS) > 0:
                return True
            return bool(self.js(JS_SPINNER_VISIBLE))
        except Exception:
            return False

    def wait_page_settled(self, timeout: int = SITE_FROZEN_TIMEOUT) -> bool:
        """
        Ждёт, пока страница перестанет быть занятой. Пока страница «живая»
        (растёт DOM, идут запросы, крутится спиннер) — таймер продлевается,
        поэтому долгая загрузка под нагрузкой не считается ошибкой.
        """
        last_signature = ""
        last_change = time.time()
        while True:
            try:
                signature = self.js(JS_PAGE_SIGNATURE)
            except Exception:
                signature = ""
            if signature != last_signature:
                last_signature = signature
                last_change = time.time()
            busy = self._page_busy()
            if not busy and time.time() - last_change > 0.3:
                return True
            if time.time() - last_change > timeout:
                logger.warning(f"Страница не меняется {timeout} сек")
                return False
            time.sleep(POLL_INTERVAL)

    def wait_element(self, selector: str, timeout: int = FORM_READY_TIMEOUT) -> bool:
        last_signature = ""
        last_change = time.time()
        while True:
            try:
                if self.driver.find_elements(By.CSS_SELECTOR, selector):
                    return True
                signature = self.js(JS_PAGE_SIGNATURE)
            except Exception:
                signature = ""
            if signature != last_signature:
                last_signature = signature
                last_change = time.time()
            if self._page_busy():
                last_change = max(last_change, time.time() - timeout / 2)
            if time.time() - last_change > timeout:
                return False
            time.sleep(POLL_INTERVAL)

    def open_url(self, url: str, wait_selector: Optional[str] = None,
                 attempts: int = OPEN_URL_ATTEMPTS, timeout: int = STREET_READY_TIMEOUT
                 ) -> bool:
        for attempt in range(1, attempts + 1):
            try:
                self.driver.get(url)
                self.wait_page_settled(timeout=timeout)
                if wait_selector and not self.wait_element(wait_selector, timeout):
                    logger.warning(f"Элемент {wait_selector} не появился ({attempt}/{attempts})")
                    time.sleep(RETRY_PAUSE * attempt)
                    continue
                self.sleep_if_rate_limited()
                return True
            except TimeoutException:
                logger.warning(f"Долгая загрузка ({attempt}/{attempts}), ждём дальше")
                if wait_selector is None or self.wait_element(wait_selector, timeout):
                    try:
                        self.sleep_if_rate_limited()
                    except Exception:
                        pass
                    return True
            except WebDriverException as exc:
                logger.warning(f"Ошибка загрузки ({attempt}/{attempts}): "
                               f"{str(exc).splitlines()[0][:120]}")
                if not self.alive():
                    self.restart()
            time.sleep(RETRY_PAUSE * attempt)
        return False

    def _switch_to_new_window(self, handles_before) -> bool:
        try:
            for handle in self.driver.window_handles:
                if handle not in handles_before:
                    self.driver.switch_to.window(handle)
                    self.form_handle = handle
                    self._close_extra_windows(keep=handle)
                    return True
        except Exception:
            pass
        return False


    def _handles(self) -> List[str]:
        try:
            return list(self.driver.window_handles)
        except Exception:
            return []

    def _current_handle(self) -> Optional[str]:
        try:
            return self.driver.current_window_handle
        except Exception:
            return None

    def remember_main_window(self) -> str:
        """Основная вкладка — та, где живёт список хонадонов улицы."""
        handles = self._handles()
        if handles and self.main_handle not in handles:
            self.main_handle = handles[0]
            logger.info(f"Основная вкладка: {self.main_handle[:10]}…")
        return self.main_handle or ""

    def focus_main(self) -> bool:
        handle = self.main_handle
        if handle and handle in self._handles():
            try:
                self.driver.switch_to.window(handle)
                return True
            except Exception:
                return False
        return False

    def _close_extra_windows(self, keep: Optional[str] = None) -> int:
        """
        Закрывает все вкладки, кроме основной и keep. Новые вкладки не плодим:
        работаем с теми, что уже открыты.
        """
        main = self.remember_main_window()
        keep = keep or self._current_handle()
        closed = 0
        actions.info(f"Вкладки до чистки: {len(self._handles())}, "
                     f"держу main={str(main)[:10]}, keep={str(keep)[:10]}")
        for handle in self._handles():
            if handle in (main, keep):
                continue
            try:
                self.driver.switch_to.window(handle)
                self.driver.close()
                closed += 1
            except Exception:
                pass
        try:
            if keep and keep in self._handles():
                self.driver.switch_to.window(keep)
            elif main and main in self._handles():
                self.driver.switch_to.window(main)
        except Exception:
            pass
        if closed:
            logger.info(f"Закрыто лишних вкладок: {closed}, "
                        f"осталось {len(self._handles())}")
        return closed

    def form_window_ready(self) -> bool:
        """Открыта ли ещё форма добавления хонадона в своей вкладке."""
        handle = self.form_handle
        if not handle or handle not in self._handles():
            return False
        if self._current_handle() != handle:
            try:
                self.driver.switch_to.window(handle)
            except Exception:
                return False
        return self.wait_cadaster(timeout=REUSE_FORM_TIMEOUT)

    def reuse_form_window(self) -> bool:
        """
        Открытая форма — подставляем данные новой строки вместо перезагрузки.
        Чистим поля кадастра/дома и все поля человека (pinfl, дата, паспорт,
        ФИО, телефон). Перезагрузка нужна только если кадастр или дом не
        очистились — тогда форму нельзя использовать под новую строку.
        """
        names = list(dict.fromkeys(list(FORM_CLEAR_NAMES) + list(FORM_PERSON_CLEAR_NAMES)))
        left: List[str] = []
        try:
            left = self.js(JS_CLEAR_FORM, names) or []
        except Exception as exc:
            logger.warning(f"Очистка формы не удалась: {str(exc).splitlines()[0][:100]}")
        stuck = [n for n in (left or []) if n in FORM_KEEP_NAMES]
        person_left = [n for n in (left or []) if n not in FORM_KEEP_NAMES]
        actions.info(f"Переиспользование формы: чистил {len(names)} полей, "
                     f"не очистилось {brief(left)}")
        if person_left:
            logger.warning("Поля человека не очистились (" + ", ".join(person_left[:6])
                           + ") — поиск нового ЖШШИР всё равно перезапишет их")
        if stuck:
            logger.warning("Форма сохранила кадастр/дом (" + ", ".join(stuck)
                           + ") — перезагружаю форму")
            return False
        return True


    def _collect_table_rows(self) -> List[dict]:
        """Прокручивает список хонадонов улицы и собирает все строки таблицы."""
        rows: Dict[str, dict] = {}
        try:
            self.js(JS_SCROLL_TOP)
        except Exception:
            pass
        stagnant, last_count, guard = 0, -1, 0
        while stagnant < 3 and guard < 400:
            guard += 1
            try:
                for row in self.js(JS_TABLE_ROWS) or []:
                    key = row.get("href") or row.get("text") or ""
                    if key:
                        rows[key] = row
            except Exception as exc:
                logger.warning(f"Ошибка чтения строк таблицы: {str(exc).splitlines()[0][:100]}")
                break
            try:
                self.js(JS_SCROLL_STEP)
            except Exception:
                break
            time.sleep(TABLE_SCROLL_PAUSE)
            if len(rows) == last_count:
                stagnant += 1
            else:
                stagnant, last_count = 0, len(rows)
        try:
            self.js(JS_SCROLL_TOP)
        except Exception:
            pass
        return list(rows.values())

    @staticmethod
    def _cadaster_in_text(text: str) -> str:
        match = CADASTER_IN_TEXT.search(text or "")
        return normalize_code(match.group(0)) if match else ""

    def read_street_cadasters(self) -> List[dict]:
        """
        Кадастры, уже заведённые на странице улицы:
        [{'cadaster', 'href', 'text', 'cells'}].
        """
        found: List[dict] = []
        seen = set()
        for row in self._collect_table_rows():
            cells = row.get("cells") or []
            code = ""
            for cell in cells:
                code = self._cadaster_in_text(cell)
                if code:
                    break
            if not code:
                code = self._cadaster_in_text(row.get("text", ""))
            if not code or code in seen:
                continue
            seen.add(code)
            found.append({"cadaster": code, "href": row.get("href", ""),
                          "text": (row.get("text") or "")[:120],
                          "cells": cells[:6]})
        return found

    def _reload_form_window(self) -> bool:
        """Перезагрузка уже открытой вкладки формы (новая вкладка не создаётся)."""
        try:
            url = self.driver.current_url
        except Exception:
            url = ""
        if not url:
            return False
        logger.info(f"Перезагрузка открытой формы: {url[:120]}")
        self._navigate(url)
        return self.wait_cadaster(timeout=FORM_READY_TIMEOUT)

    def wait_for_login(self) -> None:
        deadline = time.time() + self.profile.login_wait_timeout
        logger.info("Проверка авторизации (при необходимости войдите вручную)")
        while time.time() < deadline:
            try:
                if (self.driver.find_elements(By.XPATH, LOGIN_MARKER_XPATH)
                        or self.driver.find_elements(By.CSS_SELECTOR, "table.platon-table")):
                    logger.info("Авторизация подтверждена")
                    return
            except Exception:
                pass
            time.sleep(2)
        logger.info("Авторизация не подтверждена, продолжаем")


    def http_errors(self, clear: bool = True) -> List[dict]:
        try:
            errors = self.js("return window.__httpErrors ? window.__httpErrors.slice() : [];") or []
            if clear:
                self.js("window.__httpErrors = [];")
            return errors
        except Exception:
            return []

    @staticmethod
    def _readable_body(raw: str) -> str:
        """
        Превращает тело ответа ошибки в читаемый текст: JSON разбирается и
        склеивается по полям (message/error/errors/detail и вложенным),
        обычный текст просто обрезается.
        """
        raw = (raw or "").strip()
        if not raw:
            return ""
        if raw[:1] not in "{[":
            return raw[:500]
        try:
            data = json.loads(raw)
        except Exception:
            return raw[:500]

        parts: List[str] = []

        def walk(node, key: str = "") -> None:
            if isinstance(node, dict):
                for sub_key, value in node.items():
                    walk(value, str(sub_key))
            elif isinstance(node, list):
                for value in node:
                    walk(value, key)
            elif isinstance(node, (str, int, float, bool)):
                text = str(node).strip()
                if not text or text in ("None", "True", "False"):
                    return
                low = key.lower()
                label = "" if low in ("message", "error", "detail", "msg") else (
                    f"{key}: " if key else "")
                parts.append(label + text)

        walk(data)
        text = "; ".join(parts[:10])
        return (text or raw)[:600]

    @staticmethod
    def format_http_errors(errors: List[dict]) -> str:
        parts = []
        for err in errors[:HTTP_ERRORS_LIMIT]:
            body = BrowserAutomator._readable_body(str(err.get("body", "")))
            entry = (f"HTTP {err.get('status')} {err.get('method', '')} "
                     f"{err.get('url', '')}")
            if body:
                entry += f" — {body}"
            parts.append(entry)
        return " || ".join(parts)

    def capture_notices(self, settle: float = NOTICE_SETTLE_DEFAULT) -> List[str]:
        notices: List[str] = []
        deadline = time.time() + settle
        while time.time() < deadline:
            try:
                for text in self.js(JS_NOTICES) or []:
                    if text and text not in notices:
                        notices.append(text)
            except Exception:
                break
            time.sleep(NOTICE_POLL_INTERVAL)


        page_error = self.page_error()
        if page_error:
            notices.append(page_error)

        http_text = self.format_http_errors(self.http_errors())
        if http_text:
            notices.append(http_text)
            logger.warning(f"HTTP-ошибка (записана в отчёт): {http_text[:800]}")
        return notices

    def close_notices(self) -> None:
        try:
            self.js(JS_CLOSE_TOASTS)
        except Exception:
            pass
        for xpath in CLOSE_MODAL_XPATHS:
            for button in self.driver.find_elements(By.XPATH, xpath):
                try:
                    if button.is_displayed():
                        self.js(JS_CLICK, button)
                except Exception:
                    continue

    @staticmethod
    def cooldown_from(notices: List[str]) -> int:
        wait = 0
        for text in notices:
            low = text.lower()
            if not any(k in low for k in RATE_LIMIT_MARKERS):
                continue
            match = COOLDOWN_RE.search(text)
            wait = max(wait, int(match.group(1)) if match else COOLDOWN_DEFAULT)
        return min(wait, MAX_COOLDOWN)

    def wait_cooldown(self, seconds: int, reason: str = "") -> None:
        seconds = max(1, min(seconds + COOLDOWN_EXTRA, MAX_COOLDOWN))
        logger.warning(f"Лимит запросов{(' (' + reason + ')') if reason else ''}: "
                       f"пауза {seconds} сек")
        self.close_notices()
        time.sleep(seconds)

    def sleep_if_rate_limited(self) -> bool:
        notices = self.capture_notices(settle=NOTICE_SETTLE_QUICK)
        cooldown = self.cooldown_from(notices)
        if cooldown:
            self.wait_cooldown(cooldown, "загрузка страницы")
            return True
        if notices:
            self.close_notices()
        return False

    @staticmethod
    def notices_have_error(notices: List[str]) -> Optional[str]:
        for text in notices:
            low = text.lower()
            has_error = any(m in low for m in ERROR_MARKERS)
            has_success = any(m in low for m in SUCCESS_MARKERS)
            if has_success and not has_error:
                continue
            if has_error:
                return text
        return None


    def open_street(self, url: str) -> bool:
        """
        Работает в основной вкладке (вкладку формы не переиспользует под список).
        Если это та же улица — страницу не перезагружаем, кнопка уже на месте.
        """
        self.focus_main()
        if url and url == self.current_street_url and self.alive():
            if self.wait_add_home_button(timeout=1.0):
                logger.info("Та же улица — страницу не перезагружаю")
                actions.info(f"Улица без перезагрузки: {url[:120]}")
                return True

        try:
            self.driver.get(url)
        except TimeoutException:
            logger.warning("Долгая загрузка страницы улицы — продолжаю")
            try:
                self.js("window.stop();")
            except Exception:
                pass
        except WebDriverException as exc:
            logger.warning(f"Ошибка загрузки страницы улицы: "
                           f"{str(exc).splitlines()[0][:120]}")
            if not self.alive():
                self.restart()
                try:
                    self.driver.get(url)
                except Exception:
                    pass

        found = self.wait_add_home_button(timeout=STREET_READY_TIMEOUT)
        if not found:
            logger.warning("Кнопка «Хонадон қўшиш» не появилась — продолжаю")
        self.current_street_url = url
        self.sleep_if_rate_limited()
        return True

    def wait_add_home_button(self, timeout: int = STREET_READY_TIMEOUT) -> bool:
        """
        Плотный опрос кнопки «Хонадон қўшиш». Выходит сразу, как только кнопка
        появилась, и сразу, если браузер показал страницу-заглушку ошибки.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                for element in self.driver.find_elements(By.CSS_SELECTOR, ADD_HOME_CSS):
                    try:
                        if element.is_displayed():
                            return True
                    except StaleElementReferenceException:
                        continue
            except Exception:
                pass
            if self.page_error():
                logger.warning("Страница улицы не открылась (ошибка браузера)")
                return False
            time.sleep(POLL_INTERVAL)
        return False

    def page_error(self) -> str:
        """Текст страницы-заглушки браузера («HTTP ERROR 400», «недоступна»)."""
        try:
            return (self.js(JS_BROWSER_ERROR_PAGE) or "").strip()
        except Exception:
            return ""

    def wait_cadaster(self, timeout: int = FORM_READY_TIMEOUT) -> bool:
        """Плотный опрос поля кадастра после открытия формы."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.driver.find_elements(By.CSS_SELECTOR, CADASTER_SELECTOR):
                    return True
            except Exception:
                pass
            if self.page_error():
                return False
            time.sleep(POLL_INTERVAL)
        return False

    def _navigate(self, url: str) -> bool:
        try:
            self.driver.get(url)
            return True
        except TimeoutException:
            try:
                self.js("window.stop();")
            except Exception:
                pass
            return True
        except WebDriverException as exc:
            logger.warning(f"Переход не удался: {str(exc).splitlines()[0][:120]}")
            if not self.alive():
                self.restart()
            return False

    def _add_home_href(self) -> Optional[str]:
        try:
            return self.js(JS_ADD_HOME_HREF)
        except Exception:
            return None

    def open_add_form(self) -> bool:
        """
        Форму добавления открываем один раз и дальше переиспользуем: поля
        очищаются, вводим данные новой строки и жмём «Сақлаш». Новых вкладок
        не плодим. Если форма закрылась после сохранения — жмём кнопку снова.
        """
        if self.form_window_ready():
            if self.reuse_form_window():
                logger.info("Использую уже открытую форму — без новой вкладки")
                return True
            if self._reload_form_window():
                return True

        self.focus_main()
        href = self._add_home_href()
        if not self.wait_add_home_button(timeout=FORM_READY_TIMEOUT):
            logger.warning("Кнопка «Хонадон қўшиш» так и не появилась")
            return self._open_add_form_by_href(href)

        handles_before = set(self.driver.window_handles)
        if not self._click_button(ADD_HOME_XPATHS):
            logger.warning("Клик по «Хонадон қўшиш» не удался")
            return self._open_add_form_by_href(href)
        self._switch_to_new_window(handles_before)

        if self.wait_cadaster(timeout=FORM_READY_TIMEOUT):
            return True
        logger.warning("Поле кадастра не появилось — пробую ссылку кнопки")
        return self._open_add_form_by_href(href)

    def _open_add_form_by_href(self, href: Optional[str]) -> bool:
        if not href:
            logger.warning("Ссылка формы добавления на странице не найдена")
            return False
        target = merge_url_params(urljoin(BASE_URL, href),
                                  url_params(self.current_street_url), force=False)


        handle = self.form_handle if self.form_handle in self._handles() else ""
        if not handle:
            extras = [h for h in self._handles() if h != self.main_handle]
            handle = extras[0] if extras else ""
        if handle:
            try:
                self.driver.switch_to.window(handle)
            except Exception:
                handle = ""
        if handle:
            self.form_handle = handle
            logger.warning(f"Переход к форме добавления в открытой вкладке: {target[:120]}")
            if not self._navigate(target):
                return False
            return self.wait_cadaster(timeout=FORM_READY_TIMEOUT)


        logger.warning(f"Открываю вкладку формы добавления: {target[:120]}")
        self.focus_main()
        before = set(self._handles())
        try:
            self.js("window.open(arguments[0], 'mahalla_form_tab');", target)
        except Exception as exc:
            logger.warning(f"window.open не сработал: {str(exc).splitlines()[0][:100]}")
            return False
        deadline = time.time() + FORM_READY_TIMEOUT
        while time.time() < deadline:
            new = [h for h in self._handles() if h not in before]
            if new:
                try:
                    self.driver.switch_to.window(new[-1])
                except Exception:
                    time.sleep(POLL_INTERVAL)
                    continue
                self.form_handle = new[-1]
                self._close_extra_windows(keep=self.form_handle)
                break
            time.sleep(POLL_INTERVAL)
        return self.wait_cadaster(timeout=FORM_READY_TIMEOUT)


    def _fieldset(self, data_name: str, timeout: int = ELEMENT_WAIT_TIMEOUT):
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, f'fieldset[data-name="{data_name}"]')))

    def _first_existing(self, names: List[str]) -> Optional[str]:
        for name in names:
            if self.driver.find_elements(By.CSS_SELECTOR, f'fieldset[data-name="{name}"]'):
                return name
        return None

    def _read_field(self, data_name: str) -> str:
        try:
            fs = self.driver.find_element(By.CSS_SELECTOR, f'fieldset[data-name="{data_name}"]')
            inputs = fs.find_elements(By.CSS_SELECTOR, "input")
            return inputs[0].get_attribute("value") if inputs else ""
        except Exception:
            return ""

    @staticmethod
    def _value_matches(actual: str, value: str) -> bool:
        return (digits_only(actual) == digits_only(value)
                or (actual or "").strip() == (value or "").strip())

    def _fill_input(self, field_input, value: str, attempts: int = FIELD_ATTEMPTS,
                    read_back=None) -> bool:
        """Заполняет input: сначала JS, затем клавиатурой. read_back — функция проверки."""
        read_back = read_back or (lambda: field_input.get_attribute("value") or "")
        for attempt in range(1, attempts + 1):
            try:
                if attempt == 1:
                    try:
                        self.js(JS_SET_INPUT, field_input, value)
                        time.sleep(AFTER_INPUT_PAUSE)
                        if self._value_matches(read_back(), value):
                            return True
                    except StaleElementReferenceException:
                        raise
                    except Exception:
                        pass

                self.js(JS_SCROLL_CENTER, field_input)
                try:
                    field_input.click()
                except ElementClickInterceptedException:
                    self.close_notices()
                    self.js(JS_FOCUS, field_input)
                field_input.send_keys(Keys.CONTROL, "a")
                field_input.send_keys(Keys.DELETE)
                field_input.send_keys(value)
                field_input.send_keys(Keys.TAB)

                for _ in range(FIELD_VALUE_CHECKS):
                    time.sleep(POLL_INTERVAL)
                    if self._value_matches(read_back(), value):
                        return True
            except StaleElementReferenceException:
                time.sleep(POLL_INTERVAL)
            except Exception as exc:
                logger.warning(f"Ввод «{value[:24]}»: {str(exc).splitlines()[0][:100]}")
                time.sleep(POLL_INTERVAL)
        return False

    def _set_field(self, data_name: str, value: str, attempts: int = FIELD_ATTEMPTS) -> bool:
        for attempt in range(1, attempts + 1):
            try:
                field_input = self._fieldset(data_name).find_element(By.CSS_SELECTOR, "input")
            except Exception:
                time.sleep(POLL_INTERVAL)
                continue
            if self._fill_input(field_input, value, attempts=1,
                                read_back=lambda: self._read_field(data_name)):
                return True
        return False

    def _find_cadaster_fieldset(self) -> Optional[str]:
        name = self._first_existing(CADASTER_NAMES)
        if name:
            return name
        try:
            return self.js("""
                for (const l of document.querySelectorAll('label.pa-label')) {
                    const t = (l.textContent || '').toLowerCase();
                    if (t.includes('кадастр') || t.includes('kadastr')) {
                        const fs = l.closest('fieldset[data-name]');
                        if (fs) return fs.getAttribute('data-name');
                    }
                }
                return null;
            """)
        except Exception:
            return None

    def fill_cadaster(self, cadaster: str) -> bool:
        """Вводит кадастровый номер в поле «Кадастр рақами»."""
        value = normalize_code(cadaster)
        if not value:
            return False
        data_name = self._find_cadaster_fieldset()
        if data_name and self._set_field(data_name, value):
            logger.info(f"Кадастр введён: {value}")
            return True

        try:
            field_input = self.driver.find_element(
                By.CSS_SELECTOR, f'input[placeholder="{CADASTER_PLACEHOLDER}"]')
        except Exception:
            logger.warning("Поле «Кадастр рақами» не найдено. Поля формы: "
                           + ", ".join((self.js(JS_ALL_FIELDSETS) or [])[:40]))
            return False
        if self._fill_input(field_input, value):
            logger.info(f"Кадастр введён: {value}")
            return True
        logger.warning(f"Кадастр «{value}» не удалось ввести")
        return False

    def _find_house_fieldset(self) -> Optional[str]:
        name = self._first_existing(HOUSE_NAMES)
        if name:
            return name
        try:
            return self.js("""
                for (const l of document.querySelectorAll('label.pa-label')) {
                    const t = (l.textContent || '').trim().toLowerCase();
                    if (t.startsWith('хонадон') && t.indexOf('тури') < 0) {
                        const fs = l.closest('fieldset[data-name]');
                        if (fs) return fs.getAttribute('data-name');
                    }
                }
                return null;
            """)
        except Exception:
            return None

    def fill_house(self, house: str) -> bool:
        """Вводит столбец «ДОМ» в поле «Хонадон» (data-name=home_num)."""
        if not house:
            logger.warning("В таблице пустой столбец «ДОМ» — поле «Хонадон» не заполнить")
            return False
        data_name = self._find_house_fieldset()
        if not data_name:
            try:
                field_input = self.driver.find_element(By.CSS_SELECTOR, HOME_NUM_SELECTOR
                                                       + " input")
            except Exception:
                logger.warning("Поле «Хонадон» не найдено. Поля формы: "
                               + ", ".join((self.js(JS_ALL_FIELDSETS) or [])[:40]))
                return False
            if self._fill_input(field_input, house):
                logger.info(f"Хонадон записан: {house}")
                return True
            logger.warning(f"Хонадон «{house}» не удалось ввести")
            return False

        current = (self._read_field(data_name) or "").strip()
        if current and self._value_matches(current, house):
            logger.info(f"Хонадон уже указан: {current}")
            return True
        if self._set_field(data_name, house):
            logger.info(f"Хонадон записан: {house}")
            return True
        logger.warning(f"Хонадон «{house}» не удалось ввести (поле {data_name})")
        return False


    def _current_select_value(self, data_name: str) -> str:
        try:
            return (self.js(JS_FIELD_SNAPSHOT) or {}).get(data_name, "") or ""
        except Exception:
            return ""

    def _visible_options(self) -> List:
        found = []
        for selector in OPTION_SELECTORS:
            for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                try:
                    if element.is_displayed() and (element.text or "").strip():
                        found.append(element)
                except StaleElementReferenceException:
                    continue
            if found:
                break
        return found

    def _click_element(self, element) -> None:
        self.js(JS_SCROLL_CENTER, element)
        try:
            element.click()
        except Exception:
            self.js(JS_CLICK, element)

    def _pick_option(self, needle: str, timeout: float = OPTION_WAIT_TIMEOUT) -> Optional[str]:
        target = norm_text(needle)
        deadline = time.time() + timeout
        while time.time() < deadline:
            for option in self._visible_options():
                try:
                    text = (option.text or "").strip()
                    if text and target in norm_text(text):
                        self._click_element(option)
                        time.sleep(AFTER_OPTION_CLICK)
                        return text
                except StaleElementReferenceException:
                    break
            time.sleep(POLL_INTERVAL)
        return None

    def _pick_option_exact(self, needle: str,
                           timeout: float = OPTION_WAIT_TIMEOUT) -> Optional[str]:
        """
        Вариант списка по точному тексту, затем по началу, и лишь потом по
        вхождению. Так «Бошқа» не совпадёт с «Бошқа ...», а нужный тип
        документа не подменится похожим.
        """
        target = norm_text(needle)
        if not target:
            return None
        deadline = time.time() + timeout
        while time.time() < deadline:
            options = []
            for option in self._visible_options():
                try:
                    text = (option.text or "").strip()
                    if text:
                        options.append((norm_text(text), text, option))
                except StaleElementReferenceException:
                    continue
            for matcher in (
                lambda text: text == target,
                lambda text: text.startswith(target),
                lambda text: target in text,
            ):
                for normalized, text, option in options:
                    if not matcher(normalized):
                        continue
                    try:
                        self._click_element(option)
                        time.sleep(AFTER_OPTION_CLICK)
                        return text
                    except StaleElementReferenceException:
                        break
            time.sleep(POLL_INTERVAL)
        return None

    def _option_texts(self) -> List[str]:
        """Тексты открытого списка, без клика."""
        texts = []
        for option in self._visible_options():
            try:
                text = " ".join((option.text or "").split())
            except StaleElementReferenceException:
                continue
            if text:
                texts.append(text)
        return texts

    def _try_native_select(self, fieldset, needle: str) -> Optional[str]:
        selects = fieldset.find_elements(By.TAG_NAME, "select")
        if not selects:
            return None
        element = selects[0]
        target = norm_text(needle)
        try:
            control = Select(element)
            for option in control.options:
                if target in norm_text(option.text):
                    control.select_by_visible_text(option.text)
                    self.js("arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                            element)
                    return option.text.strip()
        except Exception:
            pass
        try:
            picked = self.js(JS_SELECT_NATIVE_BY_NEEDLE, element, target)
            if picked:
                return picked
        except Exception:
            pass
        return None

    def _open_dropdown(self, fieldset) -> bool:
        for selector in OPENER_SELECTORS:
            for element in fieldset.find_elements(By.CSS_SELECTOR, selector):
                try:
                    if not element.is_displayed():
                        continue
                    self.js(JS_SCROLL_CENTER, element)
                    try:
                        element.click()
                    except ElementClickInterceptedException:
                        self.close_notices()
                        self.js(JS_CLICK, element)
                    except Exception:
                        self.js(JS_CLICK, element)
                    time.sleep(AFTER_DROPDOWN_OPEN)
                    if self._visible_options():
                        return True
                    if element.tag_name == "input":
                        try:
                            element.send_keys(" ")
                            time.sleep(AFTER_DROPDOWN_OPEN)
                            element.send_keys(Keys.BACKSPACE)
                            time.sleep(AFTER_DROPDOWN_OPEN)
                            if self._visible_options():
                                return True
                        except Exception:
                            pass
                except StaleElementReferenceException:
                    continue
                except Exception:
                    continue
        return False

    def _type_in_search(self, text: str) -> bool:
        for search in self.driver.find_elements(By.CSS_SELECTOR, SEARCH_INPUT_SELECTOR):
            try:
                if search.is_displayed():
                    search.send_keys(text)
                    time.sleep(AFTER_SEARCH_TYPE)
                    return True
            except Exception:
                continue
        return False

    def _close_dropdown(self) -> None:

        try:
            self.driver.execute_script(JS_CLOSE_SELECT)
        except Exception:
            pass

    def _log_field_html(self, data_name: str) -> None:
        if not self.debug_select:
            return
        try:
            logger.warning(f"HTML {data_name}: {self.js(JS_FIELDSET_HTML, data_name)[:900]}")
        except Exception:
            pass


    def _street_data_name(self) -> Optional[str]:
        return self._first_existing(STREET_NAMES) or self._find_street_fieldset_by_label()

    def current_street_id(self) -> str:
        """Номер выбранной улицы (значение select в поле «Кўча»)."""
        data_name = self._street_data_name()
        if not data_name:
            return ""
        try:
            return digits_only(self.js(JS_SELECT_VALUE_BY_NAME, data_name) or "")
        except Exception:
            return ""

    def street_rendered_text(self) -> str:
        """Что видно в поле улицы (select2 может показать название)."""
        data_name = self._street_data_name()
        if not data_name:
            return ""
        try:
            return " ".join((self.js(JS_SELECT_RENDERED, data_name) or "").split())
        except Exception:
            return ""

    def select_street_by_id(self, street_id: str) -> bool:
        """
        Выбор улицы по номеру street_id из ссылки строки. У опций этого select
        текст пустой, поэтому выбрать по названию часто нельзя — номер надёжнее.
        """
        street_id = digits_only(street_id)
        if not street_id:
            return False
        data_name = self._street_data_name()
        if not data_name:
            logger.warning("Поле «Кўча» не найдено на форме")
            return False

        for attempt in range(1, SELECT_ATTEMPTS + 1):
            try:
                if self.current_street_id() == street_id:
                    logger.info(f"Улица уже выбрана: street_id={street_id} "
                                f"({self.street_rendered_text() or 'без названия'})")
                    return True

                values = [digits_only(v) for v in
                          (self.js(JS_SELECT_OPTION_VALUES, data_name) or [])]
                if street_id not in values:
                    logger.warning(f"street_id={street_id} нет среди {len(values)} улиц "
                                   f"в списке формы — пробую по названию")
                    return False

                fieldset = self._fieldset(data_name, timeout=DROPDOWN_FIELDSET_TIMEOUT)
                selects = fieldset.find_elements(By.TAG_NAME, "select")
                if not selects:
                    return False
                select_el = selects[0]

                self.js(JS_SET_SELECT_VALUE, select_el, street_id)
                time.sleep(AFTER_OPTION_CLICK)
                if self.current_street_id() != street_id:
                    try:
                        Select(select_el).select_by_value(street_id)
                        time.sleep(AFTER_OPTION_CLICK)
                    except Exception as exc:
                        logger.warning(f"select_by_value: {str(exc).splitlines()[0][:100]}")

                if self.current_street_id() == street_id:
                    logger.info(f"Улица выбрана по номеру: street_id={street_id} "
                                f"({self.street_rendered_text() or 'без названия'})")
                    self._close_dropdown()
                    return True
                logger.warning(f"Улица street_id={street_id} не удержалась в поле "
                               f"(попытка {attempt}/{SELECT_ATTEMPTS})")
            except StaleElementReferenceException:
                time.sleep(POLL_INTERVAL)
            except Exception as exc:
                logger.warning(f"Выбор улицы по номеру: {str(exc).splitlines()[0][:100]}")
                time.sleep(POLL_INTERVAL)
        return False

    def read_street_name(self) -> str:
        """Улица из заголовка формы: «… Баҳор, ул. С.Рахимов тор - -» → «ул. С.Рахимов тор»."""
        try:
            return (self.js(JS_PAGE_STREET_NAME) or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _best_street_match(target: str, options: List) -> Optional[object]:
        want = norm_street(target)
        if not want:
            return None
        scored = []
        for option in options:
            try:
                text = (option.text or "").strip()
            except StaleElementReferenceException:
                continue
            if not text:
                continue
            have = norm_street(text)
            if have == want:
                return option
            ratio = difflib.SequenceMatcher(None, want, have).ratio()
            if want in have or have in want:
                ratio = max(ratio, 0.85 - abs(len(have) - len(want)) * 0.01)
            scored.append((ratio, option))
        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        best_ratio, best = scored[0]
        return best if best_ratio >= STREET_MATCH_THRESHOLD else None

    @staticmethod
    def _best_native_index(target: str, select_el) -> int:
        want = norm_street(target)
        best_idx, best_ratio = -1, 0.0
        for idx, option in enumerate(Select(select_el).options):
            have = norm_street(option.text)
            if not have:
                continue
            if have == want:
                return idx
            ratio = difflib.SequenceMatcher(None, want, have).ratio()
            if want in have or have in want:
                ratio = max(ratio, 0.85)
            if ratio > best_ratio:
                best_idx, best_ratio = idx, ratio
        return best_idx if best_ratio >= STREET_MATCH_THRESHOLD else -1

    def _find_street_fieldset_by_label(self) -> Optional[str]:
        try:
            return self.js("""
                for (const l of document.querySelectorAll('label.pa-label')) {
                    const t = (l.textContent || '').toLowerCase();
                    if (t.includes('кўча') || t.includes('куча') || t.includes("ko'cha")) {
                        const fs = l.closest('fieldset[data-name]');
                        if (fs) return fs.getAttribute('data-name');
                    }
                }
                return null;
            """)
        except Exception:
            return None

    def _current_street(self) -> str:
        data_name = self._first_existing(STREET_NAMES) or self._find_street_fieldset_by_label()
        return self._current_select_value(data_name) if data_name else ""

    def pick_open_street_option(self, street_name: str) -> bool:
        """
        Выбирает улицу в списке, который раскрывается сам после ввода кадастра.
        Если список закрыт — открывает поле улицы и ищет заново.
        """
        if not street_name:
            return False
        for _ in range(2):
            options = self._visible_options()
            if options:
                match = self._best_street_match(street_name, options)
                if match is not None:
                    picked = " ".join((match.text or "").split())
                    self._click_element(match)
                    time.sleep(AFTER_OPTION_CLICK)
                    self._close_dropdown()
                    logger.info(f"Улица выбрана из списка: {picked}")
                    return True
            time.sleep(POLL_INTERVAL)
        return self.select_street(street_name)

    def select_street(self, street_name: str, attempts: int = SELECT_ATTEMPTS) -> bool:
        """Выбор улицы через поле формы (если список не был открыт)."""
        if not street_name:
            return True
        data_name = self._first_existing(STREET_NAMES) or self._find_street_fieldset_by_label()
        if not data_name:
            logger.warning("Поле «Кўча» не найдено на форме")
            return False

        for attempt in range(1, attempts + 1):
            try:
                current = self._current_select_value(data_name)
                if current and norm_street(current) == norm_street(street_name):
                    return True

                fieldset = self._fieldset(data_name, timeout=DROPDOWN_FIELDSET_TIMEOUT)

                selects = fieldset.find_elements(By.TAG_NAME, "select")
                if selects:
                    idx = self._best_native_index(street_name, selects[0])
                    if idx >= 0:
                        self.js(JS_SELECT_NATIVE_BY_INDEX, selects[0], idx)
                        logger.info(f"Улица выбрана: {street_name}")
                        return True

                if not self._open_dropdown(fieldset):
                    self._close_dropdown()
                    continue

                options = self._visible_options()
                match = self._best_street_match(street_name, options)
                if match is None:
                    first_word = norm_street(street_name).split(" ")[0]
                    if first_word and self._type_in_search(first_word):
                        options = self._visible_options()
                        match = self._best_street_match(street_name, options)

                if match is not None:
                    picked = " ".join((match.text or "").split())
                    self._click_element(match)
                    time.sleep(AFTER_OPTION_CLICK)
                    self._close_dropdown()
                    logger.info(f"Улица выбрана: {picked}")
                    return True

                visible = [" ".join((o.text or "").split()) for o in options][:30]
                logger.warning(f"Улица «{street_name}» не найдена среди {visible}")
                self._close_dropdown()
            except StaleElementReferenceException:
                time.sleep(POLL_INTERVAL)
            except Exception as exc:
                logger.warning(f"Улица: {str(exc).splitlines()[0][:100]}")
                self._close_dropdown()
                time.sleep(POLL_INTERVAL)

        self._log_field_html(data_name)
        return False

    def select_value(self, names: List[str], needle: str,
                     attempts: int = SELECT_ATTEMPTS) -> bool:
        data_name = self._first_existing(names)
        if not data_name:
            logger.warning(f"Поле {names[0]} не найдено на форме")
            return False

        for attempt in range(1, attempts + 1):
            try:
                current = self._current_select_value(data_name)
                if current and norm_text(needle) in norm_text(current):
                    return True

                fieldset = self._fieldset(data_name, timeout=DROPDOWN_FIELDSET_TIMEOUT)

                if self._try_native_select(fieldset, needle):
                    return True

                if not self._open_dropdown(fieldset):
                    self._close_dropdown()
                    continue

                picked = self._pick_option(needle, timeout=OPTION_WAIT_SHORT)
                if not picked:
                    self._type_in_search(needle[:6])
                    picked = self._pick_option(needle, timeout=OPTION_WAIT_AFTER_TYPE)

                if picked:
                    self._close_dropdown()
                    return True

                visible = [" ".join((o.text or "").split()) for o in self._visible_options()][:25]
                logger.warning(f"{data_name}: «{needle}» не найдено среди {visible}")
                self._close_dropdown()
            except StaleElementReferenceException:
                time.sleep(POLL_INTERVAL)
            except Exception as exc:
                logger.warning(f"{data_name}: {str(exc).splitlines()[0][:100]}")
                self._close_dropdown()
                time.sleep(POLL_INTERVAL)

        self._log_field_html(data_name)
        return False


    def fill_dictionaries(self) -> List[str]:
        failed = []
        plan = [
            (HOME_TYPE_NAMES, HOME_TYPE_VALUE, "хонадон тури"),
            (OWNERSHIP_NAMES, OWNERSHIP_VALUE, "мулкий мансублиги"),
            (STUDY_LEVEL_NAMES, STUDY_LEVEL_VALUE, "маълумоти"),
            (HOME_REGISTERED_NAMES, HOME_REGISTERED_VALUE, "рўйхатда туриши"),
        ]
        for names, value, title in plan:
            if not self.select_value(names, value):
                failed.append(f"{title} ({value})")
        return failed

    def fill_phone(self, phone: str) -> bool:
        if not phone:
            return True
        data_name = self._first_existing(self.profile.phone_names)
        if not data_name:
            logger.warning("Поле телефона не найдено")
            return False
        if self._set_field(data_name, phone):
            logger.info(f"Телефон записан: {phone}")
            return True
        if self._set_field(data_name, digits_only(phone)):
            logger.info(f"Телефон записан без маски: {digits_only(phone)}")
            return True
        return False


    def _click_button(self, xpaths: List[str]) -> bool:
        for xpath in xpaths:
            for button in self.driver.find_elements(By.XPATH, xpath):
                try:
                    if not (button.is_displayed() and button.is_enabled()):
                        continue
                    self.js(JS_SCROLL_CENTER, button)
                    try:
                        button.click()
                    except ElementClickInterceptedException:
                        self.close_notices()
                        self.js(JS_CLICK, button)
                    except Exception:
                        self.js(JS_CLICK, button)
                    return True
                except Exception:
                    continue
        return False

    def _click_pinfl_search(self) -> bool:
        return self._click_button(PINFL_SEARCH_XPATHS)

    def _signature(self) -> str:
        try:
            return self.js(JS_PAGE_SIGNATURE) or ""
        except Exception:
            return ""

    def _notices_present(self) -> bool:
        try:
            return bool(self.js(JS_NOTICES))
        except Exception:
            return False

    def _find_button(self, xpaths: List[str]):
        for xpath in xpaths:
            for button in self.driver.find_elements(By.XPATH, xpath):
                try:
                    if button.is_displayed() and button.is_enabled():
                        return button
                except Exception:
                    continue
        return None

    def click_save_confirm(self) -> Tuple[bool, str]:
        """
        Нажимает «Сақлаш» и подтверждает, что клик дошёл: ждёт запрос к серверу,
        уведомление, смену подписи страницы или переход. Возвращает
        (клик подтверждён, пояснение).
        """
        button = self._find_button(SAVE_XPATHS)
        if button is None:
            return False, "Кнопка сохранения не найдена"

        signature_before = self._signature()
        try:
            url_before = self.driver.current_url
        except Exception:
            url_before = ""

        self.js(JS_SCROLL_CENTER, button)
        try:
            button.click()
        except ElementClickInterceptedException:
            self.close_notices()
            self.js(JS_CLICK, button)
        except Exception:
            try:
                self.js(JS_CLICK, button)
            except Exception as exc:
                return False, f"клик не удался: {str(exc).splitlines()[0][:80]}"

        deadline = time.time() + SAVE_CONFIRM_TIMEOUT
        while time.time() < deadline:
            if self._page_busy():
                return True, "запрос ушёл на сервер"
            if self._notices_present() or self.http_errors(clear=False):
                return True, "появилось уведомление"
            try:
                if self.driver.current_url != url_before:
                    return True, "страница сменилась"
            except Exception:
                pass
            if self._signature() != signature_before:
                return True, "страница изменилась"
            time.sleep(POLL_INTERVAL)
        return False, "клик прошёл, но страница не отреагировала"

    def wait_save_notices(self, timeout: int = SAVE_NOTICE_TIMEOUT) -> List[str]:
        """Ждёт уведомление сайта после сохранения (тост/модалка/HTTP-ошибка)."""
        notices: List[str] = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            for text in self.capture_notices(settle=NOTICE_SETTLE_QUICK):
                if text and text not in notices:
                    notices.append(text)
            if notices:
                for text in self.capture_notices(settle=NOTICE_SETTLE_DEFAULT):
                    if text and text not in notices:
                        notices.append(text)
                return notices
            time.sleep(POLL_INTERVAL)
        return notices

    def left_form(self) -> bool:
        """Форма добавления закрылась (поля кадастра и кнопки «Сақлаш» нет)."""
        try:
            if self.driver.find_elements(By.CSS_SELECTOR, CADASTER_SELECTOR):
                return False
            if self.driver.find_elements(By.CSS_SELECTOR, "button.save-btn"):
                return False
            return True
        except Exception:
            return False

    def _snapshot_fields(self) -> Dict[str, str]:
        try:
            return self.js(JS_FIELD_SNAPSHOT) or {}
        except Exception:
            return {}

    def _wait_search_results(self, before: Dict[str, str],
                             timeout: int = SEARCH_RESULT_TIMEOUT) -> Tuple[bool, List[str]]:
        """Ждёт, пока подтянутся данные по ЖШШИР или появится уведомление."""
        deadline = time.time() + timeout
        skip = (PINFL_FIELD, BIRTH_FIELD, *CADASTER_NAMES, *STREET_NAMES, *HOUSE_NAMES)
        notices: List[str] = []
        while time.time() < deadline:
            after = self._snapshot_fields()
            if [k for k, v in after.items() if v and not before.get(k) and k not in skip]:
                return True, self.capture_notices(settle=NOTICE_SETTLE_QUICK)

            try:
                current = self.js(JS_NOTICES) or []
            except Exception:
                current = []
            http_text = self.format_http_errors(self.http_errors(clear=False))
            if http_text:
                current = list(current) + [http_text]
            if current:
                notices = self.capture_notices(settle=NOTICE_SETTLE_QUICK)
                return False, notices or list(current)
            time.sleep(POLL_INTERVAL)
        return False, notices


    def _open_tab(self) -> bool:
        for needle in [self.profile.tab_text] + list(self.profile.tab_fallbacks):
            for selector in (
                f"//a[contains(@class,'nav-link')][.//span[contains(text(),'{needle}')]]",
                f"//a[contains(@class,'nav-link')][contains(.,'{needle}')]",
                f"//button[contains(@class,'nav-link')][contains(.,'{needle}')]",
            ):
                for tab in self.driver.find_elements(By.XPATH, selector):
                    if not tab.is_displayed():
                        continue
                    self.js(JS_SCROLL_CENTER, tab)
                    self.js(JS_CLICK, tab)
                    try:
                        WebDriverWait(self.driver, TAB_CHECKBOX_TIMEOUT).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR,
                                 "div.tab-pane.active input[type='checkbox']")))
                    except TimeoutException:
                        logger.warning("Чекбоксы на вкладке не найдены")
                    time.sleep(AFTER_TAB_OPEN)
                    return True
        return False

    def _check_required_boxes(self) -> List[str]:
        """Отмечает все чекбоксы одним JS-вызовом; при неудаче — повтор."""
        targets = [list(pair) for pair in CHECKBOX_TARGETS]
        missed: List[str] = []
        for _ in range(2):
            try:
                result = self.js(JS_CHECK_TARGETS, targets) or {}
            except Exception as exc:
                logger.warning(f"Чекбоксы: {str(exc).splitlines()[0][:100]}")
                result = {}
            items = result.get("results", [])
            missed = [f"{i['section']} → {i['option']}" for i in items
                      if i.get("state") not in ("checked", "already")]
            if not missed and items:
                return []
            time.sleep(AFTER_CLICK_PAUSE)
        for entry in missed:
            logger.warning(f"Чекбокс не отмечен: {entry}")
        return missed


    def wait_cadaster_reaction(self, timeout: float = AFTER_CADASTER_PAUSE) -> None:
        """
        Ждёт реакцию сайта на кадастр ~timeout секунд, затем проверяются поля.
        Выходит раньше, если сайт уже отреагировал: появилось уведомление,
        поля начали заполняться сами или показана страница ошибки.
        """
        before = self._snapshot_fields()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._notices_present() or self.http_errors(clear=False) \
                    or self.page_error():
                break
            if self._snapshot_fields() != before:
                break
            time.sleep(POLL_INTERVAL)
        remain = deadline - time.time()
        if remain > 0:
            time.sleep(remain)

    def check_cadaster_result(self) -> Tuple[str, List[str]]:
        """
        Смотрит, что сайт ответил на кадастр: '' (ничего), 'known:<код>'
        (запись уже в системе) или 'error'.
        """
        notices = self.capture_notices(settle=NOTICE_SETTLE_QUICK)
        cooldown = self.cooldown_from(notices)
        if cooldown:
            self.wait_cooldown(cooldown, "ввод кадастра")
            for text in self.capture_notices(settle=NOTICE_SETTLE_QUICK):
                if text not in notices:
                    notices.append(text)
        if not notices:
            return "", []
        known = next((k for k in (classify_error(n) for n in notices) if k), None)
        if known:
            return f"known:{known}", notices
        positive = [n for n in notices
                    if not any(neg in norm_text(n) for neg in NEGATION_MARKERS)]
        joined = norm_text(" ".join(positive))
        if joined and any(marker in joined for marker in CADASTER_EXISTS_MARKERS):
            return f"known:{ERR_EXISTS}", notices
        if self.notices_have_error(notices):
            return "error", notices
        return "", notices

    def prefilled_person_fields(self) -> List[str]:
        """
        Поля «о человеке», которые сайт заполнил сам после ввода кадастра.
        Непустой список = данные по этому хонадону уже введены.
        """
        snapshot = self._snapshot_fields()
        found: List[str] = []
        for name, value in snapshot.items():
            if not value:
                continue
            low = name.lower()
            if any(marker in low for marker in PERSON_FIELD_MARKERS):
                found.append(name)
        return found


    def _search_once(self) -> Tuple[str, List[str]]:
        """
        Один цикл поиска по ЖШШИР с уже заполненными полями.
        Возвращает (результат, уведомления): ok | btn_missing | known:<код> |
        error:<текст> | empty.
        """
        notices: List[str] = []
        for _ in range(SEARCH_ATTEMPTS):
            before = self._snapshot_fields()
            self.close_notices()
            self.http_errors(clear=True)
            if not self._click_pinfl_search():
                return "btn_missing", notices

            found, notices = self._wait_search_results(before)
            cooldown = self.cooldown_from(notices)
            if cooldown:
                self.wait_cooldown(cooldown, "поиск по ЖШШИР")
                continue

            known = next((k for k in (classify_error(n) for n in notices) if k), None)
            if known:
                self.close_notices()
                return f"known:{known}", notices

            error_text = self.notices_have_error(notices)
            self.close_notices()
            if error_text:
                return f"error:{error_text[:150]}", notices
            if found:
                return "ok", notices
        return "empty", notices


    def process_row(self, row) -> Tuple[str, str, str, str, str]:
        """
        Обрабатывает строку Excel. Возвращает
        (статус, тип_ошибки/ключ, уведомления, ПИНФЛ, дата рождения).
        """
        notices_all: List[str] = []
        deadline = time.time() + ROW_TIMEOUT


        if not row.street_url:
            return "SKIPPED", "Нет ссылки на улицу", "", "", ""
        with timed("3.1 Открытие страницы улицы", row.street_label()):
            self.open_street(row.street_url)


        with timed("3.2 Кнопка «Хонадон қўшиш» и форма добавления"):
            if not self.open_add_form():
                self._screenshot("add_form_fail")
                if self.page_error():
                    return "FAILED", "Страница не открылась: " + self.page_error()[:150], \
                           "", "", ""
                return "FAILED", "Форма добавления хонадона не открылась", "", "", ""


        with timed("3.3 Ввод кадастра и «Хонадон»", f"{row.cadaster} / дом {row.house or '—'}"):
            if not self.fill_cadaster(row.cadaster):
                self._screenshot("cadaster_fail")
                return "FAILED", "Кадастр не введён", "", "", ""
            house_ok = self.fill_house(row.house)
            if not house_ok:
                self._screenshot("home_num_fail")
            self.wait_cadaster_reaction()


        with timed("3.4 Проверка реакции сайта на кадастр"):
            cad_result, cad_notices = self.check_cadaster_result()
        notices_all.extend(n for n in cad_notices if n not in notices_all)
        actions.info(f"Реакция на кадастр: результат={cad_result or 'тихо'}, "
                     f"уведомления={brief(cad_notices)}")
        if cad_result.startswith("known:"):
            key = cad_result.split(":", 1)[1]
            logger.warning(f"Кадастр уже заведён ({ERROR_TITLES.get(key, key)}) — "
                           f"следующая строка")
            self.close_notices()
            return "KNOWN_ERROR", key, " || ".join(notices_all), "", ""
        if cad_result == "error":
            self.close_notices()
            self._screenshot("cadaster_notice")
            error_text = self.notices_have_error(cad_notices) or "ошибка сайта"
            return ("FAILED", f"Ошибка после ввода кадастра: {error_text[:150]}",
                    " || ".join(notices_all), "", "")


        candidates = row.pinfl_candidates()
        with timed("3.5 Проверка: не введены ли данные заранее"):
            prefilled = self.prefilled_person_fields()
        actions.info(f"Заполненные поля человека: {brief(prefilled)}")
        if prefilled:
            current = digits_only(self._read_field(PINFL_FIELD))
            own = {digits_only(p) for p, _ in candidates}
            if current and current not in own:

                logger.warning(f"В форме остался прошлый ЖШШИР {current} — очищаю поля "
                               f"и продолжаю со своей строкой")
                try:
                    self.js(JS_CLEAR_FORM, list(FORM_PERSON_CLEAR_NAMES))
                except Exception:
                    pass
                prefilled = []
        if prefilled:
            logger.warning("Данные уже введены (поля: " + ", ".join(prefilled[:6])
                           + ") — следующая строка")
            self.close_notices()
            return "SKIPPED", "Данные уже введены", " || ".join(notices_all), "", ""


        if not candidates:
            return "SKIPPED", "Нет/некорректный ЖШШИР", "", "", ""

        used_pinfl = used_birth = ""
        search_result = "empty"
        last_error = ""
        for idx, (pinfl, birth) in enumerate(candidates, 1):
            if time.time() > deadline:
                last_error = f"Таймаут обработки строки ({ROW_TIMEOUT} сек)"
                logger.warning(last_error + " — следующая строка")
                break
            if idx > 1:
                logger.info(f"Повтор поиска: вариант {idx}/{len(candidates)} "
                            f"({pinfl})")
            actions.info(f"ПОИСК вариант {idx}/{len(candidates)}: ЖШШИР {pinfl}, ДР {birth}")
            attempt_started = time.perf_counter()
            with timed(f"3.6 Поиск {idx}/{len(candidates)}", f"ЖШШИР {pinfl}, ДР {birth}",
                       quiet=(idx == 1)):
                if not self._set_field(PINFL_FIELD, pinfl):
                    last_error = "ЖШШИР не введён"
                    continue
                if not self._set_field(BIRTH_FIELD, birth):
                    last_error = "Дата рождения не введена"
                    continue

                result, notices = self._search_once()
                notices_all.extend(n for n in notices if n not in notices_all)
                used_pinfl, used_birth = pinfl, birth

                if result == "ok":
                    search_result = "ok"
                    break
                if result == "btn_missing":

                    logger.warning("Кнопка поиска по ЖШШИР не найдена — продолжаю")
                    last_error = "Кнопка поиска по ЖШШИР не найдена"
                    continue
                if result.startswith("known:"):
                    key = result.split(":", 1)[1]
                    return ("KNOWN_ERROR", key, " || ".join(notices_all),
                            used_pinfl, used_birth)
                if result.startswith("error:"):
                    last_error = result.split(":", 1)[1]
                if result == "empty":
                    last_error = "Данные по ЖШШИР не подтянулись"
            actions.info(f"ПОИСК вариант {idx}: результат={result}, "
                         f"{time.perf_counter() - attempt_started:.2f} с, "
                         f"уведомления={brief(notices)}")

        if search_result != "ok":
            self._screenshot("search_empty")
            reason = last_error or "Данные по ЖШШИР не подтянулись"
            if len(candidates) > 1:
                reason += f" (проверено вариантов: {len(candidates)})"
            return "FAILED", reason, " || ".join(notices_all), used_pinfl, used_birth


        row.street_name = self.read_street_name()
        self.close_notices()
        street_ok = False
        actions.info(f"Улица из заголовка формы: {brief(row.street_name)}")
        with timed("3.7 Выбор улицы", row.street_name or "не найдена"):
            street_id = digits_only(url_params(row.street_url).get("street_id", ""))
            if street_id:
                logger.info(f"Выбор улицы по street_id={street_id} из ссылки строки")
                street_ok = self.select_street_by_id(street_id)
            if not street_ok and row.street_name:
                logger.info(f"Подбор улицы по названию из заголовка: {row.street_name}")
                street_ok = self.pick_open_street_option(row.street_name)
            if street_ok:

                self.wait_page_settled(timeout=FORM_READY_TIMEOUT)
            else:
                self._screenshot("street_fail")
                logger.warning(f"Улица «{row.street_name or '—'}» (street_id={street_id or '—'}) "
                               f"не выбрана — продолжаю с текущей: {self._current_street() or '—'}")


        with timed("3.8 Справочники и телефон"):
            failed_dicts = self.fill_dictionaries()
            if not house_ok:
                failed_dicts.append(f"«Хонадон» ({row.house or 'пусто в Excel'})")
            if not street_ok:
                failed_dicts.append(f"улица «{row.street_name or '—'}»")
            phone = row.get_formatted_phone()
            if not self.fill_phone(phone):
                failed_dicts.append("телефон")
        actions.info(f"Справочники: не заполнено {brief(failed_dicts)}, телефон {phone}")


        with timed("3.9 Вкладка «Ижтимоий-иқтисодий ҳолат» и чекбоксы"):
            tab_ok = self._open_tab()
            if not tab_ok:
                self._screenshot("tab_fail")
                logger.warning("Вкладка «Ижтимоий-иқтисодий ҳолат» не найдена — продолжаю")
            missed_boxes = self._check_required_boxes() if tab_ok else []
        actions.info(f"Вкладка открыта: {tab_ok}, не отмечены {brief(missed_boxes)}")


        saved, save_error, save_problem = False, "", ""
        save_started = time.perf_counter()
        logger.info("▶ 3.10 Сохранение «Сақлаш»")
        for attempt in range(1, SAVE_ATTEMPTS + 1):
            attempt_started = time.perf_counter()
            actions.info(f"СОХРАНЕНИЕ попытка {attempt}/{SAVE_ATTEMPTS} — начало")
            if time.time() > deadline:
                save_problem = f"Таймаут обработки строки ({ROW_TIMEOUT} сек)"
                logger.warning(save_problem)
                break
            self.close_notices()
            self.http_errors(clear=True)

            clicked, evidence = self.click_save_confirm()
            actions.info(f"Клик «Сақлаш»: clicked={clicked}, признак={evidence} | "
                         f"{time.perf_counter() - attempt_started:.2f} с")
            if not clicked:
                self._screenshot("save_click_fail")
                save_problem = evidence
                logger.warning(f"«Сақлаш» (попытка {attempt}/{SAVE_ATTEMPTS}): {evidence}")
                time.sleep(RETRY_PAUSE)
                continue

            logger.info(f"«Сақлаш» нажата ({evidence}) — ждём уведомление")
            notice_started = time.perf_counter()
            notices = self.wait_save_notices()
            actions.info(f"Ожидание уведомления: {brief(notices)} | "
                         f"{time.perf_counter() - notice_started:.2f} с")
            notices_all.extend(n for n in notices if n not in notices_all)
            if notices:
                logger.info("Уведомление после сохранения: " + " || ".join(notices))
            else:
                logger.warning("Уведомление после сохранения не пришло")

            cooldown = self.cooldown_from(notices)
            if cooldown:
                self.wait_cooldown(cooldown, "сохранение")
                continue

            known = next((k for k in (classify_error(n) for n in notices) if k), None)
            if known:
                actions.info(f"СОХРАНЕНИЕ: ошибка сайта {known} | "
                             f"{time.perf_counter() - attempt_started:.2f} с")
                self.close_notices()
                return ("KNOWN_ERROR", known, " || ".join(notices_all),
                        used_pinfl, used_birth)

            save_error = self.notices_have_error(notices) or ""
            if save_error:
                actions.info(f"СОХРАНЕНИЕ: ошибка «{save_error}» | "
                             f"{time.perf_counter() - attempt_started:.2f} с")
                self.close_notices()
                break

            if any(m in " ".join(notices).lower() for m in SUCCESS_MARKERS):
                saved = True
                actions.info(f"СОХРАНЕНИЕ: успех по уведомлению | "
                             f"{time.perf_counter() - attempt_started:.2f} с")
                self.close_notices()
                break


            if self.left_form():
                saved = True
                actions.info(f"СОХРАНЕНИЕ: форма закрылась | "
                             f"{time.perf_counter() - attempt_started:.2f} с")
                logger.info("Форма добавления закрылась — сохранение принято")
                break

            save_problem = "уведомление о сохранении не пришло"
            self._screenshot("save_no_notice")
            logger.warning(f"«Сақлаш» (попытка {attempt}/{SAVE_ATTEMPTS}): {save_problem}")
            time.sleep(RETRY_PAUSE)
        actions.info(f"Итог сохранения: saved={saved}, ошибка={save_error or '—'}, "
                     f"проблема={save_problem or '—'} | всего {time.perf_counter() - save_started:.2f} с")

        if not saved:
            self._screenshot("save_fail")
            if save_error:
                reason = f"Ошибка сохранения: {save_error[:150]}"
            else:
                reason = save_problem or "Сохранение не подтверждено"
            return "FAILED", reason, " || ".join(notices_all), used_pinfl, used_birth

        warnings = []
        if not tab_ok:
            warnings.append("Вкладка «Ижтимоий-иқтисодий ҳолат» не найдена")
        if failed_dicts:
            warnings.append("Не заполнено: " + "; ".join(failed_dicts))
        if missed_boxes:
            warnings.append("Не отмечены чекбоксы: " + "; ".join(missed_boxes))
        if warnings:
            return "OK_WARN", " | ".join(warnings), " || ".join(notices_all), \
                   used_pinfl, used_birth
        return "OK", "", " || ".join(notices_all), used_pinfl, used_birth
