import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import argparse
import json
import time


def out(*parts) -> None:
    print(*parts, flush=True)


def silence_console_logging() -> None:
    log = logging.getLogger("family")
    for handler in list(log.handlers):
        if isinstance(handler, logging.FileHandler):
            continue
        log.removeHandler(handler)


def out_json(label, data, limit=3000):
    text = json.dumps(data, ensure_ascii=False, indent=1)
    if len(text) > limit:
        text = text[:limit] + " … (обрезано)"
    out(f"{label}\n{text}")


import family_filler as fam


silence_console_logging()


CADASTER_URL = ("https://www.online-mahalla.uz/forms/survey_homes/9432436"
                "?obl_id=30&area_id=3005&district_id=3005049&street_id=300500881")

DUMP = """
let root = null;
for (const el of document.querySelectorAll('div.vm--modal, div.modal')) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && el.querySelectorAll('fieldset[data-name]').length) {
        root = el; break;
    }
}
if (!root) return {modal: false};
const fields = [];
root.querySelectorAll('fieldset[data-name]').forEach(fs => {
    const box = fs.closest('.col-md-6, .col-md-4, .col-md-3, .col-12') || fs.parentElement;
    const input = fs.querySelector('input, textarea, select');
    fields.push({
        name: fs.getAttribute('data-name'),
        tag: input ? input.tagName : '',
        value: input ? (input.value || '') : '',
        label: ((box ? box.innerText : '') || '').replace(/\\s+/g, ' ').trim().slice(0, 50)
    });
});
const buttons = [];
root.querySelectorAll('button').forEach(b => {
    buttons.push({cls: (b.className || '').toString().slice(0, 50),
                  text: (b.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 30),
                  visible: b.offsetParent !== null});
});
const hints = [];
root.querySelectorAll('.invalid-feedback, .text-danger, .alert, .help-block').forEach(e => {
    const t = (e.innerText || '').replace(/\\s+/g, ' ').trim();
    if (t) hints.push(t.slice(0, 120));
});
return {modal: true, fields: fields, buttons: buttons, hints: hints};
"""


def main() -> None:
    argparse.ArgumentParser().parse_args()
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
        out("ВКЛАДКА:", app.open_members_tab())
        out("«Бошқа» до:", app.members_count())
        row = app.next_row()
        out("СТРОКА:", row.label(), "| ПИНФЛ:", row.pinfl_digits(),
              "| тип:", row.doc_type)
        out("КЛИК:", app.automator.js(fam.JS_CLICK_MEMBER_SAVE))
        time.sleep(2)
        out_json("ПОЛЯ ДО:", app.automator.js(DUMP), 2500)

        out("rel:", app._modal_select(fam.RELATION_NAMES, fam.RELATION_VALUE,
                                        ("қариндош",)))
        doc_ok = False
        for needle in row.doc_type_needles():
            if app._modal_select(fam.DOC_TYPE_NAMES, needle, ("ҳужжат тури",)):
                doc_ok = True
                break
        out("doc:", doc_ok)
        out("serial:", app._modal_fill(fam.DOC_SERIES_NAMES, row.doc_series))
        out("number:", app._modal_fill(fam.DOC_NUMBER_NAMES, row.doc_number))
        out("birth:", app._modal_fill(fam.MEMBER_BIRTH_NAMES, row.birth_date()))
        out("pinfl:", app._modal_fill(fam.PINFL_NAMES, row.pinfl_digits()))

        app.automator.http_errors(clear=True)
        app.automator.close_notices()
        out_json("ПОЛЯ ПЕРЕД ПОИСКОМ:", app.automator.js(DUMP), 2000)

        JS_SEARCH_IN_PINFL = """
        for (const el of document.querySelectorAll('div.vm--modal, div.modal')) {
            const r = el.getBoundingClientRect();
            if (!r.width || !r.height) continue;
            const fs = el.querySelector('fieldset[data-name="pinfl"]');
            if (!fs) continue;
            for (const b of fs.querySelectorAll('button')) {
                if ((b.innerText || '').indexOf('Қидириш') >= 0) {
                    b.click();
                    return 'clicked:' + (b.className || '').toString().slice(0, 40);
                }
            }
            return 'no-button-in-pinfl';
        }
        return 'no-modal';
        """
        out("КЛИК Қидириш (в поле ЖШШИР):",
              app.automator.js(JS_SEARCH_IN_PINFL))

        for second in range(1, 9):
            time.sleep(1)
            out(f"  +{second}s уведомления:",
                  app.automator.capture_notices(settle=0.2))
        out_json("ПОЛЯ ПОСЛЕ ПОИСКА:", app.automator.js(DUMP), 2500)

        JS_RECORDER = """
        window.__net = [];
        if (!window.__netHooked) {
            window.__netHooked = true;
            const origFetch = window.fetch;
            window.fetch = function() {
                const url = (arguments[0] && arguments[0].url) || String(arguments[0]);
                return origFetch.apply(this, arguments).then(resp => {
                    const copy = resp.clone();
                    copy.text().then(t => window.__net.push(
                        {kind: 'fetch', url: url, status: resp.status,
                         body: (t || '').slice(0, 400)}));
                    return resp;
                });
            };
            const open = XMLHttpRequest.prototype.open;
            const send = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.open = function(method, url) {
                this.__url = url;
                return open.apply(this, arguments);
            };
            XMLHttpRequest.prototype.send = function() {
                this.addEventListener('load', () => {
                    window.__net.push({kind: 'xhr', url: this.__url,
                                       status: this.status,
                                       body: (this.responseText || '').slice(0, 400)});
                });
                return send.apply(this, arguments);
            };
        }
        return window.__net.length;
        """
        out("РЕКОРДЕР:", app.automator.js(JS_RECORDER))

        out("КЛИК Қидириш (общий):", app._modal_click(fam.MEMBER_SEARCH_XPATHS))
        time.sleep(4)
        out_json("СЕТЬ:", app.automator.js("return window.__net || [];"), 3000)
        out_json("ПОЛЯ ПОСЛЕ 2:", app.automator.js(DUMP), 1500)
        out("HTTP:", app.automator.format_http_errors(
            app.automator.http_errors(clear=True)))
        out("SCREENSHOT:", app.automator._screenshot("diag_search"))
    finally:
        time.sleep(1)
        app.automator.close()


if __name__ == "__main__":
    main()
