import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import argparse
import json
import time


def out(*parts) -> None:
    print(*parts, flush=True)


def silence_console_logging() -> None:
    log = logging.getLogger("mahalla")
    for handler in list(log.handlers):
        if isinstance(handler, logging.FileHandler):
            continue
        log.removeHandler(handler)


def out_json(label, data, limit=3000):
    text = json.dumps(data, ensure_ascii=False, indent=1)
    if len(text) > limit:
        text = text[:limit] + " … (обрезано)"
    out(f"{label}\n{text}")


import src.family_filler as fam


silence_console_logging()


CADASTER_URL = ("https://www.online-mahalla.uz/forms/survey_homes/9432436"
                "?obl_id=30&area_id=3005&district_id=3005049&street_id=300500881")

JS_MODAL_OPTIONS = """
let root = null;
for (const el of document.querySelectorAll('div.vm--modal, div.modal')) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) { root = el; break; }
}
if (!root) return null;
const out = [];
root.querySelectorAll('fieldset[data-name]').forEach(fs => {
    const options = [];
    fs.querySelectorAll('select option').forEach(o => {
        options.push({value: o.value, text: (o.text || '').trim()});
    });
    out.push({name: fs.getAttribute('data-name'),
              tag: (fs.querySelector('input,textarea,select,button') || {}).tagName || '',
              options: options.slice(0, 60)});
});
return out;
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug-select", action="store_true")
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
        app.automator.open_url(CADASTER_URL, wait_selector="a.nav-link",
                               timeout=fam.STREET_READY_TIMEOUT)
        out("ФОРМА:", app.automator.driver.current_url)
        out("ВКЛАДКА:", app.open_members_tab())
        out("«Бошқа»:", app.members_count())
        out("КЛИК:", app.automator.js(fam.JS_CLICK_MEMBER_SAVE))
        time.sleep(2)
        out("МОДАЛКА:", app.automator.js(fam.JS_MODAL_VISIBLE))
        out_json("ПОЛЯ:", app.automator.js(fam.JS_MODAL_FIELDS), 1500)
        out_json("СПИСКИ:", app.automator.js(JS_MODAL_OPTIONS), 4000)
        out_json("КНОПКИ МОДАЛКИ:", app.automator.js("""
            let root = null;
            for (const el of document.querySelectorAll('div.vm--modal, div.modal')) {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) { root = el; break; }
            }
            if (!root) return null;
            const out = [];
            root.querySelectorAll('button').forEach(b => {
                out.push({cls: (b.className || '').toString().slice(0, 60),
                          text: (b.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 40)});
            });
            return out;
        """), 2000)
        out("SCREENSHOT:", app.automator._screenshot("diag_modal_options"))
    finally:
        time.sleep(1)
        app.automator.close()


if __name__ == "__main__":
    main()
