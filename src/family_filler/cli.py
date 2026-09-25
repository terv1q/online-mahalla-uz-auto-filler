import argparse
import io
import sys
import time
from pathlib import Path

from ..core.logs import actions, logger, configure
from ..core import settings
from ..core.paths import (BROWSER_DIR, INPUT_DIR, LOG_DIR, REPORT_DIR, STATE_DIR,
                          STREETS_DIR)
from ..core.timing import ROW_DELAY
from .automation import FamilyAutomation
from .config import (ACTIONS_LOG_FILE, EXCEL_FILE, LOG_FILE, REPORT_FILE, SCREENSHOT_DIR,
                     START_ROW, STREETS_FILE, STREETS_FILE_FROM, TARGET_BOSHQA)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="online-mahalla.uz — члены семьи («Бошқа») по family_members.xlsx")
    parser.add_argument("--excel", default=EXCEL_FILE)
    parser.add_argument("--report", default=REPORT_FILE)
    parser.add_argument("--limit", type=int, default=None,
                        help="максимум кадастров за запуск")
    parser.add_argument("--limit-rows", type=int, default=None,
                        help="сколько строк таблицы family_members.xlsx читать (по умолчанию все)")
    parser.add_argument("--target", type=int, default=TARGET_BOSHQA,
                        help=f"сколько «Бошқа» должно быть в кадастре "
                             f"(по умолчанию {TARGET_BOSHQA})")
    parser.add_argument("--delay", type=float, default=ROW_DELAY,
                        help="пауза между кадастрами, сек")
    parser.add_argument("--cadaster", default=None,
                        help="обработать только кадастры с этой подстрокой")
    parser.add_argument("--street-id", default=None,
                        help="обработать только одну улицу по её street_id")
    parser.add_argument("--start-row", type=int, default=START_ROW,
                        help=f"с какой строки листа брать данные (по умолчанию {START_ROW})")
    parser.add_argument("--resume", action="store_true",
                        help="читать family_progress.json (файл читается и без флага)")
    parser.add_argument("--streets-file", default=STREETS_FILE,
                        help=f"HTML-таблица улиц со страницы сайта "
                             f"(по умолчанию {STREETS_FILE})")
    parser.add_argument("--streets-from", type=int, default=None,
                        help=f"с какой улицы начинать (по умолчанию {STREETS_FILE_FROM})")
    parser.add_argument("--rescan-cadasters", action="store_true",
                        help="перепроверять кадастры, где уже набрано нужное число «Бошқа»")
    parser.add_argument("--trace-js", action="store_true",
                        help="писать в actions-лог каждый вызов JS (по умолчанию включено)")
    parser.add_argument("--no-trace-js", dest="trace_js", action="store_false",
                        help="не писать в actions-лог вызовы JS")
    parser.add_argument("--debug-select", action="store_true",
                        help="печатать HTML списков, которые не удалось выбрать")
    args = parser.parse_args()
    args.delay = max(0.0, args.delay)
    args.target = max(1, args.target)
    return args


def ensure_dirs() -> None:
    """Рабочие папки проекта (var/…) создаются при запуске, если их нет."""
    for directory in (INPUT_DIR, STREETS_DIR, STATE_DIR, REPORT_DIR, LOG_DIR,
                      Path(SCREENSHOT_DIR), BROWSER_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def main() -> None:
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    args = parse_args()
    configure(LOG_FILE, ACTIONS_LOG_FILE)
    ensure_dirs()
    if "trace_js" in vars(args):
        settings.TRACE_JS = bool(args.trace_js)
    actions.info(f"═ ЗАПУСК | excel={args.excel} | report={args.report} | "
                 f"target={args.target} | limit={args.limit} | start_row={args.start_row} "
                 f"| delay={args.delay} | street_id={args.street_id} | "
                 f"rescan={args.rescan_cadasters} | trace_js={settings.TRACE_JS}")
    started = time.perf_counter()
    try:
        FamilyAutomation(args).run()
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception as exc:
        logger.error(f"Критическая ошибка: {exc}")
        raise
    finally:
        actions.info(f"═ КОНЕЦ РАБОТЫ | всего {time.perf_counter() - started:.2f} с")
