import re


OWNERSHIP_VALUE = "шахсий"


HOME_TYPE_VALUE = "ҳовли"


STUDY_LEVEL_VALUE = "олий"


HOME_REGISTERED_VALUE = "доимий"


CADASTER_NAMES = ["cadaster_number", "cadaster", "cadaster_num", "kadastr",
                  "cadastr", "kadastr_number"]


HOUSE_NAMES = ["home_num", "house_number", "home_number", "house", "dom"]


STREET_NAMES = ["street_id", "street", "street_name", "kucha", "mfy_street"]


OWNERSHIP_NAMES = ["ownership", "ownership_id", "home_ownership", "mulk", "mulkiy"]


HOME_TYPE_NAMES = ["home_type", "home_type_id", "house_type", "xonadon_turi"]


STUDY_LEVEL_NAMES = ["study_level_id", "study_level", "education_id", "education"]


HOME_REGISTERED_NAMES = ["home_registered", "home_registered_id", "registered", "royxat"]


PINFL_FIELD = "pinfl"


BIRTH_FIELD = "birth_date"


CADASTER_PLACEHOLDER = "00:00:00:00:00:0000"


CADASTER_SELECTOR = (
    f'fieldset[data-name="cadaster_number"], input[placeholder="{CADASTER_PLACEHOLDER}"]')


PINFL_SELECTOR = f'fieldset[data-name="{PINFL_FIELD}"]'


HOME_NUM_SELECTOR = 'fieldset[data-name="home_num"]'


ADD_HOME_CSS = ('a[href*="/forms/survey_homes"] button, '
                'a[href*="/forms/survey_homes"]')


CHECKBOX_TARGETS = [
    ("Хонадоннинг асосий даромад манбаи", "Тадбиркорлик фаолиятидан"),
    ("Хонадоннинг бир ойлик даромади миқдори", "5 млн. сўмдан 10 млн. сўмгача"),
]


ADD_HOME_XPATHS = [
    "//a[contains(@href,'/forms/survey_homes')][contains(.,'Хонадон қўшиш')]",
    "//a[contains(@href,'/forms/survey_homes')][contains(.,'қўшиш')]",
    "//a[contains(@href,'/forms/survey_homes')][.//i[contains(@class,'fa-plus')]]",
    "//button[contains(@class,'btn-success')][contains(.,'қўшиш')]",
    "//button[contains(.,'Хонадон қўшиш')]",
    "//i[contains(@class,'fa-plus')]/ancestor::button[1]",
]


PINFL_SEARCH_XPATHS = [
    "//button[@title='ЖШШИР бўйича қидириш']",
    "//fieldset[@data-name='pinfl']//button[contains(@title,'ЖШШИР')]",
    "//button[contains(@title,'ЖШШИР') and contains(@class,'pa-inline-btn')]",
    "//button[contains(@title,'қидир')]",
]


SAVE_XPATHS = [
    "//button[contains(@class,'save-btn')]",
    "//button[contains(text(),'Сақлаш')]",
    "//button[contains(text(),'Saqlash')]",
    "//button[contains(text(),'Ўтказиш')]",
    "//button[contains(text(),'Тасдиқлаш')]",
    "//button[.//i[contains(@class,'fa-save')]]",
    "//button[@type='submit']",
]


LOGIN_MARKER_XPATH = (
    "//*[contains(text(),'Чиқиш') or contains(text(),'Выйти') or contains(text(),'Logout')]"
)


CLOSE_MODAL_XPATHS = [
    "//div[contains(@class,'modal') and contains(@class,'show')]"
    "//button[contains(@class,'close') or contains(.,'OK') or contains(.,'Ёпиш')"
    " or contains(.,'Закрыть') or contains(.,'Yopish')]",
    "//div[@id='pa-error-modal']//button",
    "//div[contains(@class,'swal2-popup')]//button[contains(@class,'swal2-confirm')]",
]


OPTION_SELECTORS = [
    ".select2-container--open .select2-results__option",
    ".select2-results__option",
    ".vs__dropdown-menu .vs__dropdown-option",
    ".dropdown-menu.show .dropdown-item",
    ".dropdown-menu .dropdown-item",
    "ul.typeahead.dropdown-menu li",
    ".multiselect__content .multiselect__element",
    "[role='option']",
    ".autocomplete-result",
    ".b-dropdown .dropdown-item",
]


OPENER_SELECTORS = [
    ".select2-selection", ".vs__dropdown-toggle", ".custom-select",
    "select", "input", ".form-control", "button",
]


SEARCH_INPUT_SELECTOR = (
    ".select2-search__field, .vs__search, "
    ".multiselect__input, .dropdown-menu input[type='search']"
)


ERROR_MARKERS = (
    "хато", "xato", "ошибк", "error", "мавжуд эмас", "топилмади", "topilmadi",
    "нотўғри", "noto'g'ri", "noto‘g‘ri", "тўлдиринг", "to'ldiring", "мажбурий",
    "majburiy", "ko'pay", "ko‘pay", "kuting", "status code 4", "status code 5",
    "http 400", "http 4", "http 5", "lumot topilmadi", "мавжуд",
)


SUCCESS_MARKERS = ("муваффақ", "muvaffaq", "сақланди", "saqlandi", "успешно", "success")


RATE_LIMIT_MARKERS = (
    "kuting", "кутинг", "ko'pay", "ko‘pay", "kopay", "so'rov", "so‘rov",
    "sorov", "много запросов", "подожд",
)


COOLDOWN_RE = re.compile(
    r"(\d{1,3})\s*(?:soniya|сония|сек|секунд|second|s\b)", re.IGNORECASE)


ERR_EXISTS = "EXISTS"


ERR_ACTIVE = "NO_DATA_ACTIVE"


ERR_DEAD = "NO_DATA_DEAD"


ERROR_SHEETS = {
    ERR_EXISTS: "Уже в системе",
    ERR_ACTIVE: "Нет данных (aktiv)",
    ERR_DEAD: "Нет данных (vafot)",
}


ERROR_TITLES = {
    ERR_EXISTS: "Бу фуқаро тизимда мавжуд, қайта киритиб бўлмайди",
    ERR_ACTIVE: "Ma'lumot topilmadi (status=1, aktiv, Yaroqli hujjat yo'q)",
    ERR_DEAD: "Ma'lumot topilmadi (status=2, vafot etgan, Yaroqli hujjat yo'q)",
}


SHEET_OK = "Успешно"


SHEET_ERRORS = "Ошибки"


SHEET_SKIPPED = "Пропущено"


SHEET_NOT_ENTERED = "Не введены"


REPORT_SHEETS = (SHEET_OK, SHEET_ERRORS, SHEET_SKIPPED, SHEET_NOT_ENTERED)


HEADER_FONT_COLOR = "FFFFFF"


HEADER_FILL_COLOR = "4472C4"


CADASTER_IN_TEXT = re.compile(r"\d{2}:\d{2}:\d{2}:\d{2}:\d{2}:\d{4}(?:/\d{1,4})?")


STREETS_FROM = 2


UNKNOWN_STREET_MARKERS = ("номаълум", "номалъум", "н/д", "unknown", "noma'lum")


FORM_CLEAR_NAMES = ("cadaster_number", "home_num", "pinfl", "birth_date")


FORM_KEEP_NAMES = ("cadaster_number", "home_num")


FORM_PERSON_CLEAR_NAMES = ("pinfl", "birth_date", "passport", "passport_number",
                           "passport_series", "jshshir", "fio", "full_name",
                           "last_name", "first_name", "middle_name", "phone",
                           "phone_number", "mobile", "gender", "sex", "nationality")


PINFL_SPLIT_RE = re.compile(r"[,;/|\s]+")


CADASTER_EXISTS_MARKERS = (
    "мавжуд", "уже", "exists", "takroriy", "такрорий", "қайта киритиб",
    "дубликат", "duplicate", "band", "занят",
)


PERSON_FIELD_MARKERS = (
    "pinfl", "birth", "fio", "ф.и.ш", "familia", "last_name", "first_name",
    "middle_name", "passport", "jshshir", "жшшир",
)


NEGATION_MARKERS = ("эмас", "emas", "no data", "not found", "topilmadi", "топилмади")


UZ_PHONE_PREFIXES = ("90", "91", "93", "94", "95", "97", "98", "99", "88",
                     "33", "50", "77", "20", "55")


STREET_CHAR_MAP = str.maketrans({
    "ў": "у", "қ": "к", "ғ": "г", "ҳ": "х",
    "ʼ": "'", "’": "'", "‘": "'", "`": "'", "ё": "е",
})


NETWORK_FAIL_KEYS = (
    "invalid session id", "no such window", "disconnected",
    "target crashed", "chrome not reachable",
)
