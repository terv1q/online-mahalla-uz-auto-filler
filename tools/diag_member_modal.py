import argparse
import json
import logging
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import src.family_filler as fam

DUMP_OVERLAYS = """
const rows = [];
document.querySelectorAll('div.vm--modal, div.modal, form, div[role="dialog"], div.overlay, div.v-modal')
    .forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width < 60 || r.height < 40) return;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    rows.push({
        tag: el.tagName,
        cls: (el.className || '').toString().slice(0, 120),
        id: el.id || '',
        formName: el.getAttribute('form-name') || el.getAttribute('data-form-name') || '',
        top: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height),
        z: cs.zIndex,
        fieldsets: el.querySelectorAll('fieldset[data-name]').length,
        head: (el.innerText || '').replace(/\\s+/g, ' ').slice(0, 160)
    });
});
return rows;
"""

DUMP_FIELDSETS = """
const rows = [];
document.querySelectorAll('fieldset[data-name]').forEach(fs => {
    const r = fs.getBoundingClientRect();
    const box = fs.closest('.col-md-6, .col-md-4, .col-md-3, .col-12') || fs.parentElement;
    const control = fs.querySelector('input, textarea, select');
    rows.push({
        name: fs.getAttribute('data-name'),
        visible: r.width > 0 && r.height > 0,
        label: ((box ? box.innerText : '') || '').replace(/\\s+/g, ' ').slice(0, 60),
        value: ((control || {}).value) || ''
    });
});
return rows;
"""

JS_PAGE_TEXT = "return (document.body.innerText || '').slice(0, 900);"
PAGE_TEXT_LIMIT = 900


def out(*parts) -> None:
    print(*parts, flush=True)


def silence_console_logging() -> None:
    log = logging.getLogger("mahalla")
    for handler in list(log.handlers):
        if isinstance(handler, logging.FileHandler):
            continue
        log.removeHandler(handler)


def out_json(label: str, data, limit: int = 3000) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=1)
    if len(text) > limit:
        text = text[:limit] + " … (обрезано)"
    out(f"{label}\n{text}")


silence_console_logging()


def parse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Диагностика модалки «Оила аъзосини киритиш»")
    parser.add_argument("--street-id", default=None,
                        help="работать только с улицей, чей url содержит этот номер")
    parser.add_argument("--cadaster", default=None,
                        help="остановиться на кадастре с этой подстрокой")
    parser.add_argument("--limit-rows", type=int, default=30,
                        help="сколько строк таблицы читать (по умолчанию 30)")
    parser.add_argument("--debug-select", action="store_true",
                        help="печатать HTML списков, которые не удалось выбрать")
    return parser.parse_args()


def build_args(cli: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        excel=fam.EXCEL_FILE,
        report=fam.REPORT_FILE,
        limit=None,
        limit_rows=cli.limit_rows,
        target=fam.TARGET_BOSHQA,
        delay=0.2,
        cadaster=cli.cadaster,
        street_id=cli.street_id,
        start_row=fam.START_ROW,
        resume=False,
        streets_file=fam.STREETS_FILE,
        streets_from=2,
        rescan_cadasters=False,
        trace_js=False,
        debug_select=cli.debug_select,
    )


def pick_street(app: fam.FamilyAutomation, street_id):
    for unit in app.street_units():
        if street_id and street_id not in (unit.get("url") or ""):
            continue
        out(f"УЛИЦА {unit['name']} {unit['url']}")
        app.automator.open_street(unit["url"])
        links = app.read_street_links()
        out(f"КАДАСТРОВ {len(links)}")
        if links:
            return unit, links
    return None, []


def dump_modal(app: fam.FamilyAutomation) -> None:
    out(f"МОДАЛКА ВИДНА {app.automator.js(fam.JS_MODAL_VISIBLE)}")
    out_json("ПОЛЯ МОДАЛКИ", app.automator.js(fam.JS_MODAL_FIELDS), 2000)
    out_json("OVERLAYS", app.automator.js(DUMP_OVERLAYS), 4000)
    out_json("FIELDSETS ВСЕ", app.automator.js(DUMP_FIELDSETS), 3000)
    out(f"SCREENSHOT {app.automator._screenshot('diag_member_modal')}")
    text = (app.automator.js(JS_PAGE_TEXT) or "")[:PAGE_TEXT_LIMIT]
    out(f"ТЕКСТ СТРАНИЦЫ\n{text}")


def main() -> int:
    cli = parse_cli()
    app = fam.FamilyAutomation(build_args(cli))
    app.load_rows()
    app.automator.start()
    try:
        app.automator.open_url(fam.SURVEY_URL)
        app.automator.remember_main_window()
        app.automator.wait_for_login()

        unit, links = pick_street(app, cli.street_id)
        if not links:
            out("Кадастры не найдены, диагностика остановлена")
            return 1
        out_json("ПЕРВЫЕ КАДАСТРЫ", links[:3], 2500)

        link = links[0]
        app.automator.open_url(link["url"], wait_selector="a.nav-link",
                               timeout=fam.STREET_READY_TIMEOUT)
        out(f"ФОРМА {app.automator.driver.current_url}")
        out(f"ВКЛАДКА {app.open_members_tab()}")
        out(f"«Бошқа» {app.members_count()}")
        out(f"КЛИК САҚЛАШ {app.automator.js(fam.JS_CLICK_MEMBER_SAVE)}")
        time.sleep(2)
        dump_modal(app)
        return 0
    finally:
        time.sleep(1)
        app.automator.close()


if __name__ == "__main__":
    raise SystemExit(main())
