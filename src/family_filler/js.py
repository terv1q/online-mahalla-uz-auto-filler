


JS_TABLE_LINKS_FILTERED = """const needle = arguments[0] || '';
const out = [];
document.querySelectorAll('table tr').forEach(tr => {
    const a = tr.querySelector('a[href*="' + needle + '"]');
    if (!a) return;
    const cells = Array.from(tr.querySelectorAll('td'))
        .map(td => (td.innerText || '').replace(/\\s+/g, ' ').trim());
    out.push({href: a.getAttribute('href') || '',
              text: (a.innerText || a.textContent || '').replace(/\\s+/g, ' ').trim(),
              cells: cells});
});
return out;
"""


JS_OPEN_TAB = """
const needle = (arguments[0] || '').toLowerCase();
const nodes = document.querySelectorAll(
    'a.nav-link, button.nav-link, li.nav-item a, li.nav-item button');
for (const a of nodes) {
    const t = (a.innerText || a.textContent || '').toLowerCase();
    if (t.indexOf(needle) >= 0) {
        a.scrollIntoView({block: 'center'});
        a.click();
        return (a.innerText || '').replace(/\\s+/g, ' ').trim();
    }
}
return null;
"""


JS_MEMBERS_ROWS = """
const pane = document.querySelector('div.tab-pane.active');
const scope = pane || document;
const out = [];
scope.querySelectorAll('table.platon-table tbody tr, table.table tbody tr')
     .forEach(tr => {
    const cells = Array.from(tr.querySelectorAll('td'))
        .map(td => (td.innerText || '').replace(/\\s+/g, ' ').trim());
    if (cells.length) out.push(cells);
});
return out;
"""


JS_MODAL_VISIBLE = """
for (const el of document.querySelectorAll('div.vm--modal, div.modal')) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && el.querySelectorAll('fieldset[data-name]').length)
        return true;
}
return false;
"""


JS_MODAL_FIELDS = """
let root = null;
for (const el of document.querySelectorAll('div.vm--modal, div.modal')) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && el.querySelectorAll('fieldset[data-name]').length) {
        root = el; break;
    }
}
if (!root) return null;
const out = [];
root.querySelectorAll('fieldset[data-name]').forEach(fs => {
    const box = fs.closest('.col-md-6, .col-md-4, .col-md-3, .col-12') || fs.parentElement;
    const label = ((box ? box.innerText : '') || '').replace(/\\s+/g, ' ').trim();
    const inp = fs.querySelector('input, textarea');
    const sel = fs.querySelector('select');
    out.push({name: fs.getAttribute('data-name'), label: label.slice(0, 70),
              value: ((inp || {}).value || (sel || {}).value || '')});
});
return out;
"""


JS_MODAL_CLOSE = """
let root = null;
for (const el of document.querySelectorAll('div.vm--modal, div.modal')) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && el.querySelectorAll('fieldset[data-name]').length) {
        root = el; break;
    }
}
if (!root) return 'no-modal';
for (const b of root.querySelectorAll('button')) {
    const t = (b.innerText || b.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
    if (t.indexOf('чиқиш') >= 0 || t.indexOf('чикиш') >= 0 || t.indexOf('бекор') >= 0
            || b.classList.contains('close-btn')) {
        b.scrollIntoView({block: 'center'});
        b.click();
        return 'clicked:' + t.slice(0, 20);
    }
}
const esc = new KeyboardEvent('keydown', {key: 'Escape', keyCode: 27, which: 27, bubbles: true});
document.dispatchEvent(esc);
return 'esc';
"""


JS_CLICK_MEMBER_SAVE = """
const pane = document.querySelector('div.tab-pane.active') || document;
const buttons = Array.from(pane.querySelectorAll('button'));
const byText = (needle) => buttons.find(b => {
    const t = (b.innerText || b.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
    return t.indexOf(needle) >= 0 && b.offsetParent !== null;
});
const add = byText('қўшиш') || byText('qo\\'shish') || byText('қўш');
if (add) { add.scrollIntoView({block: 'center'}); add.click(); return 'add:' + (add.innerText || '').trim(); }
const save = buttons.find(b => b.classList.contains('save-btn') && b.offsetParent !== null);
if (save) { save.scrollIntoView({block: 'center'}); save.click(); return 'save:' + (save.innerText || '').trim(); }
return 'not-found';
"""


JS_MODAL_SAVE_CLICK = """
let root = null;
for (const el of document.querySelectorAll('div.vm--modal, div.modal')) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && el.querySelectorAll('fieldset[data-name]').length) {
        root = el; break;
    }
}
if (!root) return 'no-modal';
for (const b of root.querySelectorAll('button')) {
    const t = (b.innerText || b.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
    if (b.classList.contains('save-btn') || t.indexOf('сақлаш') >= 0 || t.indexOf('saqlash') >= 0
            || t.indexOf('тасдиқлаш') >= 0) {
        b.scrollIntoView({block: 'center'});
        b.click();
        return 'clicked:' + (t || 'button').slice(0, 30);
    }
}
return 'no-button';
"""


JS_EMPTY_REQUIRED = """
let root = null;
for (const el of document.querySelectorAll('div.vm--modal, div.modal')) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && el.querySelectorAll('fieldset[data-name]').length) {
        root = el;
        break;
    }
}
if (!root) return null;
const empty = [];
root.querySelectorAll('fieldset[data-name]').forEach(fs => {
    const box = fs.closest('.col-md-6, .col-md-4, .col-md-3, .col-12') || fs.parentElement;
    const label = ((box ? box.innerText : '') || '').replace(/\\s+/g, ' ').trim();
    if (label.indexOf('*') < 0) return;
    const shown = fs.querySelector('.select2-selection__rendered, .vs__selected');
    const sel = fs.querySelector('select');
    const inp = fs.querySelector('input:not([type=checkbox]):not([type=radio]), textarea');
    let value = '';
    if (shown) value = (shown.innerText || '').trim();
    else if (sel) value = (sel.value || '').trim();
    else if (inp) value = (inp.value || '').trim();
    if (!value) empty.push({name: fs.getAttribute('data-name'), label: label.slice(0, 50)});
});
return empty;
"""


JS_SET_FIELDSET_SELECT_VALUE = """
const fs = arguments[0], value = arguments[1];
const sel = fs.querySelector('select');
if (!sel) return '';
const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
setter.call(sel, value);
sel.dispatchEvent(new Event('input', {bubbles: true}));
sel.dispatchEvent(new Event('change', {bubbles: true}));
if (window.jQuery) { try { window.jQuery(sel).trigger('change'); } catch (e) {} }
return sel.value;
"""


JS_FIELDSET_SELECT_STATE = """
const fs = arguments[0];
const sel = fs.querySelector('select');
const out = {value: sel ? sel.value : '', rendered: '', options: []};
if (sel) {
    for (const o of sel.options)
        out.options.push({value: o.value, text: (o.textContent || '').trim()});
}
const shown = fs.querySelector('.select2-selection__rendered, .vs__selected');
out.rendered = shown ? (shown.innerText || '').replace(/\\s+/g, ' ').trim() : '';
return out;
"""


JS_SEARCH_MEMBER_CLICK = """
let root = null;
const modals = document.querySelectorAll('div.vm--modal, div.modal');
for (const el of modals) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && el.querySelectorAll('fieldset[data-name]').length) {
        root = el;
        break;
    }
}
if (!root) return 'no-modal';
const buttons = [];
root.querySelectorAll('button').forEach(b => {
    const t = (b.innerText || b.textContent || '').replace(/\\s+/g, ' ').trim();
    if (t.indexOf('Қидириш') >= 0 || t.indexOf('Qidirish') >= 0) buttons.push(b);
});
if (!buttons.length) return 'no-button';
let target = null;
for (const b of buttons) {
    const title = (b.getAttribute('title') || '').toUpperCase();
    if (title.indexOf('ЖШШИР') >= 0) { target = b; break; }
}
if (!target) {
    for (const b of buttons) {
        if (b.classList.contains('pa-inline-btn')) { target = b; break; }
    }
}
if (!target) target = buttons[0];
target.scrollIntoView({block: 'center'});
target.click();
return 'clicked:' + (target.getAttribute('title') || target.className || '').toString().slice(0, 40);
"""
