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
from .automation import NewkadastrAutomation
from .config import (ACTIONS_LOG_FILE, EXCEL_FILE, LOG_FILE, REPORT_FILE, SCREENSHOT_DIR,
                     START_ROW, STREETS_FILE, STREETS_FILE_FROM, STREETS_FROM)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="online-mahalla.uz — добавление хонадонов по household_entries.xlsx")
    parser.add_argument("--excel", default=EXCEL_FILE)
    parser.add_argument("--report", default=REPORT_FILE)
    parser.add_argument("--limit", type=int, default=None, help="максимум строк за запуск")
    parser.add_argument("--delay", type=float, default=ROW_DELAY,
                        help="пауза между строками, сек")
    parser.add_argument("--cadaster", default=None,
                        help="обработать только кадастры с этой подстрокой")
    parser.add_argument("--start-row", type=int, default=START_ROW,
                        help=f"с какой строки листа начать (по умолчанию {START_ROW})")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-ignored", action="store_true",
                        help="обрабатывать и те кадастры, что уже в ignore-листе")
    parser.add_argument("--streets-file", default=STREETS_FILE,
                        help=f"HTML-таблица улиц, сохранённая со страницы сайта "
                             f"(по умолчанию {STREETS_FILE}). Пусто — брать улицы из Excel")
    parser.add_argument("--streets-from", type=int, default=None,
                        help=f"с какой улицы начинать обход (по умолчанию "
                             f"{STREETS_FILE_FROM} для файла улиц, {STREETS_FROM} для Excel)")
    parser.add_argument("--street-scan", dest="street_scan", action="store_true",
                        default=True,
                        help="сначала обойти все улицы и собрать уже заведённые кадастры "
                             "(по умолчанию включено)")
    parser.add_argument("--no-street-scan", dest="street_scan", action="store_false",
                        help="не обходить улицы, сразу основной алгоритм")
    parser.add_argument("--rescan-streets", action="store_true",
                        help="обходить улицы заново, даже если они уже проверены")
    parser.add_argument("--streets-file-only", action="store_true",
                        help="обходить только улицы из файла, без добавления улиц из Excel")
    parser.add_argument("--trace-js", action="store_true",
                        help="писать в actions-лог каждый вызов JS (по умолчанию включено)")
    parser.add_argument("--no-trace-js", dest="trace_js", action="store_false",
                        help="не писать в actions-лог вызовы JS")
    parser.add_argument("--debug-select", action="store_true",
                        help="печатать HTML списков, которые не удалось выбрать")
    args = parser.parse_args()
    args.delay = max(0.0, args.delay)
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
                 f"start_row={args.start_row} | limit={args.limit} | "
                 f"delay={args.delay} | resume={args.resume} | "
                 f"retry_ignored={args.retry_ignored} | trace_js={settings.TRACE_JS}")
    started = time.perf_counter()
    try:
        NewkadastrAutomation(args).run()
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception as exc:
        logger.error(f"Критическая ошибка: {exc}")
        raise
    finally:
        actions.info(f"═ КОНЕЦ РАБОТЫ | всего {time.perf_counter() - started:.2f} с")


if __name__ == "__main__":
    main()
