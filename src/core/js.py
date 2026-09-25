


JS_NOTICES = """
const out = [], seen = new Set();
const push = el => {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return;
    let title = '', body = '';
    const h = el.querySelector('.toast-header strong, .toast-header');
    const b = el.querySelector('.toast-body');
    if (h) title = (h.innerText || '').replace(/\\s+/g, ' ').trim();
    if (b) body = (b.innerText || '').replace(/\\s+/g, ' ').trim();
    let txt = (title || body) ? (title + (title && body ? ': ' : '') + body)
                              : (el.innerText || '').replace(/\\s+/g, ' ').trim();
    txt = txt.replace(/^×\\s*/, '').trim();
    if (!txt || seen.has(txt)) return;
    seen.add(txt); out.push(txt);
};
const sel = ['.b-toaster .toast', '.b-toast .toast', '.toast', '#pa-error-modal',
             '.modal.show', '.modal.in', '.swal2-popup', '.alert-danger',
             '.alert-warning', '.alert-success', '.vue-notification',
             '.notification', '.el-message'];
sel.forEach(s => document.querySelectorAll(s).forEach(push));
return out;
"""


JS_TOAST_STATE = """
const seen = new Set();
const out = [];
document.querySelectorAll('.b-toast, .toast, .b-toaster .toast').forEach(el => {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const head = el.querySelector('.toast-header strong, .toast-header');
    const bodyEl = el.querySelector('.toast-body');
    const title = head ? (head.innerText || '').replace(/\\s+/g, ' ').replace(/×/g, '').trim() : '';
    const body = bodyEl ? (bodyEl.innerText || '').replace(/\\s+/g, ' ').trim() : '';
    const cls = (el.className || '').toString();
    let kind = 'info';
    if (cls.indexOf('danger') >= 0 || title.indexOf('Хатолик') >= 0) kind = 'error';
    else if (cls.indexOf('warning') >= 0 || title.indexOf('Диққат') >= 0) kind = 'warn';
    else if (cls.indexOf('success') >= 0 || title.indexOf('Хабар') >= 0) kind = 'ok';
    const key = kind + '|' + title + '|' + body;
    if ((!title && !body) || seen.has(key)) return;
    seen.add(key);
    out.push({kind: kind, title: title, body: body});
});
return out;
"""


JS_CLOSE_TOASTS = """
document.querySelectorAll('.b-toaster .toast .close, .b-toast .close, .toast .close')
        .forEach(b => { try { b.click(); } catch (e) {} });
document.querySelectorAll('.modal-backdrop').forEach(e => e.remove());
document.body.classList.remove('modal-open');
return true;
"""


JS_FIELD_SNAPSHOT = """
const out = {};
document.querySelectorAll('fieldset[data-name]').forEach(fs => {
    const name = fs.getAttribute('data-name');
    const inp = fs.querySelector('input:not([type=checkbox]):not([type=radio]), textarea');
    const s2  = fs.querySelector('.select2-selection__rendered');
    const vs  = fs.querySelector('.vs__selected');
    const sel = fs.querySelector('select');
    let val = '';
    if (s2) val = s2.textContent.trim();
    else if (vs) val = vs.textContent.trim();
    else if (sel && sel.selectedIndex >= 0 && sel.options[sel.selectedIndex])
        val = sel.options[sel.selectedIndex].text.trim();
    else if (inp) val = inp.value || '';
    out[name] = val;
});
return out;
"""


JS_ALL_FIELDSETS = """
return Array.from(document.querySelectorAll('fieldset[data-name]'))
            .map(fs => fs.getAttribute('data-name'));
"""


JS_FIELDSET_HTML = """
const fs = document.querySelector('fieldset[data-name="' + arguments[0] + '"]');
return fs ? fs.outerHTML : '';
"""


JS_SET_INPUT = """
const input = arguments[0], value = arguments[1];
const proto = Object.getPrototypeOf(input);
const desc = Object.getOwnPropertyDescriptor(proto, 'value')
          || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
input.focus();
if (desc && desc.set) desc.set.call(input, value); else input.value = value;
['input', 'keyup', 'change'].forEach(t =>
    input.dispatchEvent(new Event(t, {bubbles: true})));
input.dispatchEvent(new Event('blur', {bubbles: true}));
return input.value;
"""


JS_SET_SELECT_VALUE = """
const sel = arguments[0], value = arguments[1];
const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
setter.call(sel, value);
sel.dispatchEvent(new Event('input', {bubbles: true}));
sel.dispatchEvent(new Event('change', {bubbles: true}));
if (window.jQuery) { try { window.jQuery(sel).trigger('change'); } catch (e) {} }
return sel.value;
"""


JS_SELECT_VALUE_BY_NAME = """
const fs = document.querySelector('fieldset[data-name="' + arguments[0] + '"]');
const sel = fs ? fs.querySelector('select') : null;
return sel ? (sel.value || '') : '';
"""


JS_SELECT_OPTION_VALUES = """
const fs = document.querySelector('fieldset[data-name="' + arguments[0] + '"]');
const sel = fs ? fs.querySelector('select') : null;
if (!sel) return [];
return Array.from(sel.options).map(o => o.value || '').filter(v => v);
"""


JS_SELECT_RENDERED = """
const fs = document.querySelector('fieldset[data-name="' + arguments[0] + '"]');
if (!fs) return '';
const r = fs.querySelector('.select2-selection__rendered');
if (r && (r.innerText || '').trim()) return r.innerText.trim();
const sel = fs.querySelector('select');
if (!sel) return '';
const o = sel.options[sel.selectedIndex];
return o ? (o.text || '') : '';
"""


JS_SELECT_NATIVE_BY_INDEX = """
const sel = arguments[0], idx = arguments[1];
sel.selectedIndex = idx;
sel.dispatchEvent(new Event('input', {bubbles: true}));
sel.dispatchEvent(new Event('change', {bubbles: true}));
return sel.options[idx] ? sel.options[idx].text : '';
"""


JS_SELECT_NATIVE_BY_NEEDLE = """
const sel = arguments[0], needle = arguments[1];
for (const o of sel.options) {
    if ((o.text || '').toLowerCase().includes(needle)) {
        sel.value = o.value;
        sel.dispatchEvent(new Event('input', {bubbles: true}));
        sel.dispatchEvent(new Event('change', {bubbles: true}));
        return o.text;
    }
}
return null;
"""


JS_CLICK = "arguments[0].click();"


JS_SCROLL_CENTER = "arguments[0].scrollIntoView({block:'center'});"


JS_FOCUS = "arguments[0].focus();"


JS_CHECK_TARGETS = """
const targets = arguments[0];
const norm = s => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
const pane = document.querySelector('div.tab-pane.active');
if (!pane) return {error: 'no_pane', results: []};
const results = [];
for (const [section, option] of targets) {
    const sNeedle = norm(section), oNeedle = norm(option);
    let scope = pane;
    for (const card of pane.querySelectorAll('div.card')) {
        const h = card.querySelector('h5');
        if (h && norm(h.textContent).includes(sNeedle)) { scope = card; break; }
    }
    let state = 'missing', title = option;
    for (const label of scope.querySelectorAll('label')) {
        const cb = label.querySelector('input[type="checkbox"]');
        if (!cb) continue;
        const t = norm(label.textContent);
        if (!t.includes(oNeedle)) continue;
        title = t;
        if (cb.checked) { state = 'already'; break; }
        const vis = cb.id ? label.querySelector("label.custom-control-label[for='" + cb.id + "']") : null;
        (vis || cb).click();
        if (!cb.checked) {
            cb.checked = true;
            cb.dispatchEvent(new Event('input', {bubbles: true}));
            cb.dispatchEvent(new Event('change', {bubbles: true}));
        }
        state = cb.checked ? 'checked' : 'failed';
        break;
    }
    results.push({section: section, option: option, state: state, title: title});
}
return {error: '', results: results};
"""


JS_TABLE_HEADERS = """
return Array.from(document.querySelectorAll('table.platon-table thead th'))
            .map(th => (th.innerText || '').replace(/\\s+/g, ' ').trim());
"""


JS_TABLE_ROWS = """
const out = [];
document.querySelectorAll('table.platon-table tbody tr').forEach(tr => {
    const a = tr.querySelector('a.link');
    if (!a) return;
    const cells = Array.from(tr.querySelectorAll('td'))
                       .map(td => (td.innerText || '').replace(/\\s+/g, ' ').trim());
    out.push({href: a.getAttribute('href') || '',
              text: (a.innerText || a.textContent || '').replace(/\\s+/g, ' ').trim(),
              cells: cells});
});
return out;
"""


JS_SCROLL_STEP = """
const c = document.querySelector('div.table-h-scroll')
       || document.querySelector('div.table-responsive');
if (!c) { window.scrollBy(0, Math.round(window.innerHeight * 0.8)); return -1; }
const before = c.scrollTop;
c.scrollTop = before + Math.round(c.clientHeight * 0.8);
return c.scrollTop > before ? 1 : 0;
"""


JS_SCROLL_TOP = """
const c = document.querySelector('div.table-h-scroll')
       || document.querySelector('div.table-responsive');
if (c) { c.scrollTop = 0; } else { window.scrollTo(0, 0); }
"""


JS_CLEAR_FORM = """
const names = arguments[0] || [];
const left = [];
const setValue = (inp, value) => {
    const proto = inp.tagName === 'TEXTAREA'
        ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(inp, value);
    inp.dispatchEvent(new Event('input', {bubbles: true}));
    inp.dispatchEvent(new Event('change', {bubbles: true}));
    inp.dispatchEvent(new Event('blur', {bubbles: true}));
};
names.forEach(name => {
    const fs = document.querySelector('fieldset[data-name="' + name + '"]');
    if (!fs) return;
    fs.querySelectorAll('input, textarea').forEach(inp => {
        if (inp.disabled || inp.readOnly) return;
        setValue(inp, '');
    });
});
names.forEach(name => {
    const fs = document.querySelector('fieldset[data-name="' + name + '"]');
    if (!fs) return;
    const inp = fs.querySelector('input, textarea');
    if (inp && (inp.value || '').trim()) left.push(name);
});
return left;
"""


JS_ADD_HOME_HREF = """
for (const a of document.querySelectorAll('a[href*="/forms/survey_homes"]')) {
    const t = (a.innerText || a.textContent || '').toLowerCase();
    if (t.indexOf('қўшиш') >= 0 || t.indexOf('qoshish') >= 0 || a.querySelector('i.fa-plus'))
        return a.getAttribute('href');
}
return null;
"""


JS_PAGE_STREET_NAME = """
const h = document.querySelector('h3.text-center') || document.querySelector('h3');
if (!h) return null;
const text = (h.innerText || h.textContent || '').replace(/\\s+/g, ' ').trim();
if (!text) return null;
let street = '';
for (const part of text.split(',')) {
    const p = part.trim();
    if (p.indexOf('ул.') === 0 || p.indexOf('кўча') === 0 || p.indexOf('куча') === 0
            || p.indexOf("ko'cha") === 0) { street = p; }
}
if (!street) {
    const parts = text.split(',').map(s => s.trim()).filter(Boolean);
    street = parts.length ? parts[parts.length - 1] : '';
}
return street.replace(/[\\s\\-–—]+$/, '').trim() || null;
"""


JS_BROWSER_ERROR_PAGE = """
const title = document.title || '';
const txt = ((document.body && document.body.innerText) || '').replace(/\\s+/g, ' ').trim();
const html = (document.documentElement && document.documentElement.innerHTML) || '';
const text = title + ' ' + txt;
const m = text.match(/HTTP ERROR \\d{3}/i);
if (m) {
    const tail = txt.slice(0, 300);
    return ('Страница ошибки: ' + m[0] + (tail ? ' | ' + tail : '')).trim();
}
if (html.length < 3000 && /(can't be reached|refused to connect|недоступна|ERR_[A-Z]+)/i.test(html)) {
    return ('Страница ошибки: ' + (title || 'страница не открылась')).trim();
}
return '';
"""


HTTP_HOOK_JS = """
(function () {
    if (window.__httpErrHooked) return;
    window.__httpErrHooked = true;
    window.__httpErrors = [];
    const push = (status, method, url, body) => {
        try {
            window.__httpErrors.push({
                status: status, method: method, url: String(url).slice(0, 300),
                body: String(body || '').slice(0, 1200), t: Date.now()});
        } catch (e) {}
    };
    const origFetch = window.fetch;
    if (origFetch) {
        window.fetch = function () {
            const args = arguments;
            const method = (args[1] && args[1].method) || 'GET';
            return origFetch.apply(this, args).then(resp => {
                if (resp.status >= 400) {
                    resp.clone().text().then(t =>
                        push(resp.status, method, resp.url || args[0], t))
                        .catch(() => push(resp.status, method, resp.url || args[0], ''));
                }
                return resp;
            });
        };
    }
    const origOpen = XMLHttpRequest.prototype.open;
    const origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (m, u) {
        this.__m = m; this.__u = u;
        return origOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function () {
        this.addEventListener('loadend', function () {
            if (this.status >= 400) {
                let body = '';
                try { body = this.responseText; } catch (e) {}
                push(this.status, this.__m, this.__u, body);
            }
        });
        return origSend.apply(this, arguments);
    };
})();
"""


JS_PENDING_REQUESTS = """
if (!window.__pendingHooked) {
    window.__pendingHooked = true;
    window.__pending = 0;
    const of = window.fetch;
    if (of) {
        window.fetch = function () {
            window.__pending++;
            return of.apply(this, arguments).finally(() => { window.__pending--; });
        };
    }
    const oo = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function () {
        window.__pending++;
        this.addEventListener('loadend', () => { window.__pending--; });
        return oo.apply(this, arguments);
    };
}
return window.__pending || 0;
"""


JS_SPINNER_VISIBLE = """
const sel = ['.spinner-border', '.loading', '.loader', '.b-spinner', '.overlay-loading',
             '.v-spinner', '.pa-loading', '.el-loading-mask', '.fa-spin'];
for (const s of sel) {
    for (const el of document.querySelectorAll(s)) {
        const r = el.getBoundingClientRect();
        const st = getComputedStyle(el);
        if (r.width && r.height && st.visibility !== 'hidden' && st.display !== 'none')
            return true;
    }
}
return false;
"""


JS_PAGE_SIGNATURE = """
return [document.readyState, document.body ? document.body.innerText.length : 0,
        document.querySelectorAll('input,select,fieldset,tr').length].join('|');
"""


JS_CLOSE_SELECT = """
document.querySelectorAll('.select2-container--open')
    .forEach(e => e.classList.remove('select2-container--open'));
document.querySelectorAll('.select2-results').forEach(e => { e.style.display = 'none'; });
if (window.jQuery) { try { window.jQuery('.select2-hidden-accessible').select2('close'); } catch (e) {} }
return true;
"""
