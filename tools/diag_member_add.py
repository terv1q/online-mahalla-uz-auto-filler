import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import argparse
import time


def out(*parts) -> None:
    print(*parts, flush=True)


def silence_console_logging() -> None:
    log = logging.getLogger("family")
    for handler in list(log.handlers):
        if isinstance(handler, logging.FileHandler):
            continue
        log.removeHandler(handler)

import family_filler as fam


silence_console_logging()


CADASTER_URL = ("https://www.online-mahalla.uz/forms/survey_homes/9432436"
                "?obl_id=30&area_id=3005&district_id=3005049&street_id=300500881")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="не закрывать браузер")
    parser.parse_args()
    args = argparse.Namespace(
        excel=fam.EXCEL_FILE, report=fam.REPORT_FILE, limit=None, limit_rows=30,
        target=30, delay=0.2, cadaster=None, street_id=None, start_row=fam.START_ROW,
        resume=False, streets_file=fam.STREETS_FILE, streets_from=2,
        rescan_cadasters=False, trace_js=False, debug_select=True)

    app = fam.FamilyAutomation(args)
    app.load_rows()
    app.automator.start()
    try:
        app.automator.open_url(fam.SURVEY_URL)
        app.automator.remember_main_window()
        app.automator.wait_for_login()
        app.automator.open_url(CADASTER_URL, wait_selector="a.nav-link",
                               timeout=fam.STREET_READY_TIMEOUT)
        out("ВКЛАДКА:", app.open_members_tab())
        before = app.members_count()
        out("«Бошқа» до:", before)
        row = app.next_row()
        out("СТРОКА:", row.label(), "| тип:", row.doc_type,
              "| иглы:", row.doc_type_needles())
        started = time.perf_counter()
        ok, reason = app.add_member(row)
        out(f"РЕЗУЛЬТАТ: ok={ok}, причина={reason} | {time.perf_counter() - started:.2f} с")
        out("«Бошқа» после:", app.members_count())
        out("SCREENSHOT:", app.automator._screenshot("test_member"))
        out("УВЕДОМЛЕНИЯ:", app.automator.capture_notices(settle=0.5))
    finally:
        if "--keep" in sys.argv:
            out("Браузер оставлен открытым")
        else:
            app.automator.close()


if __name__ == "__main__":
    main()
