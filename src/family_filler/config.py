from ..core.profile import SessionProfile
from ..core.paths import (
    INPUT_DIR,
    LOG_DIR,
    REPORT_DIR,
    STATE_DIR,
    STREETS_DIR,
    VAR_DIR,
)
from ..core.settings import BASE_URL


SURVEY_URL = (f"{BASE_URL}/tables/survey_homes?_level=4&obl_id=30&area_id=3005"
              f"&district_id=3005049&_mid=3548")


EXCEL_FILE = str(INPUT_DIR / "family_members.xlsx")


HEADER_ROW = 6


MAX_ROWS = 100000


REPORT_FILE = str(REPORT_DIR / "family_report.xlsx")


PROGRESS_FILE = str(STATE_DIR / "family_progress.json")


MEMBERS_STATE_FILE = str(STATE_DIR / "family_members_state.json")


STREETS_STATE_FILE = str(STATE_DIR / "family_streets_state.json")


STREETS_FOUND_FILE = str(STATE_DIR / "family_streets_found.txt")


CADASTERS_FILE = str(STATE_DIR / "family_cadasters.txt")


IGNORE_FILE = str(STATE_DIR / "family_ignored.txt")


LOG_FILE = str(LOG_DIR / "family.log")


ACTIONS_LOG_FILE = str(LOG_DIR / "family_actions.log")


SCREENSHOT_DIR = str(VAR_DIR / "screenshots" / "family")


START_ROW = 10414


TARGET_BOSHQA = 15


MEMBER_PAUSE = 0.2


CADASTER_TIMEOUT = 900


MEMBER_FAIL_LIMIT = 3


ROW_SKIP_PREFIX = "СТРОКА_ИСПОЛЬЗОВАНА: "


ROW_SKIP_MARKERS = ("қайта киритиб бўлмайди", "қайта киритиб булмайди",
                    "мавжуд, қайта", "уже существует", "уже введен", "уже заведен")


RATE_LIMIT_PREFIX = "ЛИМИТ_ЗАПРОСОВ: "


RATE_LIMIT_DEFAULT_WAIT = 30


RATE_LIMIT_EXTRA = 3


RATE_LIMIT_MAX_WAIT = 120


TOAST_WAIT_TIMEOUT = 10


TOAST_SETTLE = 0.8


TOAST_POLL_INTERVAL = 0.2


SAVE_NOTICE_QUICK_TIMEOUT = 2.5


AFTER_MODAL_CLOSE = 0.4


FULL_RESET_AFTER_FAILURES = 2


AFTER_FIELD_PAUSE = 0.2


AFTER_ERROR_PAUSE = 0.2


AFTER_SAVE_PAUSE = 0.2


MEMBER_FILL_ATTEMPTS = 3


TAB_TEXT = "Хонадон аъзолари"


TAB_FALLBACKS = ["Хонадон аъзо", "аъзолари", "A'zolar", "Аъзолар"]


LOGIN_WAIT_TIMEOUT = 300


PHONE_NAMES = ["phone", "mobile_phone", "phone_number", "tel"]


RELATION_NAMES = ["relationship", "relationship_id", "qarindoshlik"]


RELATION_VALUE = "Бошқа"


DOC_TYPE_NAMES = ["document_type", "document_type_id", "doc_type"]


DOC_SERIES_NAMES = ["doc_serial", "document_series", "doc_series", "series"]


DOC_NUMBER_NAMES = ["doc_number", "document_number", "number"]


MEMBER_BIRTH_NAMES = ["birth_date", "birthday", "tugilgan_sana"]


PINFL_NAMES = ["pinfl", "jshshir", "jshshir_pinfl", "pinfl_number", "inn"]


MEMBER_SEARCH_XPATHS = [

    "//button[contains(@class,'btn-success') and not(contains(@class,'pa-inline-btn'))]"
    "[contains(.,'Қидириш')]",
    "//button[contains(.,'Қидириш')]",
    "//button[contains(.,'Qidirish')]",
]


EDUCATION_VALUE = "Маълумоти йўқ"


EDUCATION_NAMES = ["study_level_id", "education_id", "education", "malumoti"]


DOC_TYPE_MAP = {
    "свидетельство о рождении": ("гувоҳнома", "гувохнома", "туғилганлик"),
    "документ иностранного гражданина": ("чет эл", "чет эллик", "иностран",
                                         "xorijiy", "паспорт"),
    "id-карта": ("id", "ид-карта", "ид карта"),
    "биометрик паспорт": ("биометрик", "паспорт"),
    "паспорт": ("паспорт", "passport"),
}


DOC_TYPE_DEFAULT = ("паспорт",)


FAMILY_MODAL_CSS = ("div.vm--modal, div.modal.show, div.modal[style*='display: block'], "
                    "form[form-name='survey_homes_family']")


FAMILY_FORM_MARKERS = ("survey_homes_family",)


STREETS_FILE = str(STREETS_DIR / "streets_source.txt")


STREETS_FILE_FROM = 2


REPORT_HEADERS = [
    "№", "Время", "Улица", "Кадастр", "Ф.И.Ш.", "Серия", "Номер",
    "Дата рождения", "Статус", "Ошибка", "Уведомление сайта", "Ссылка",
]


REPORT_WIDTHS = (6, 19, 28, 26, 34, 10, 16, 14, 18, 34, 60, 46)


NOT_ENTERED_HEADERS = [
    "№", "Время", "Улица", "Кадастр", "Ф.И.Ш.", "Серия", "Номер",
    "Дата рождения", "Ошибка",
]


NOT_ENTERED_WIDTHS = (6, 19, 28, 26, 34, 10, 16, 14, 70)

PROFILE = SessionProfile(
    login_wait_timeout=LOGIN_WAIT_TIMEOUT,
    tab_text=TAB_TEXT,
    tab_fallbacks=tuple(TAB_FALLBACKS),
    phone_names=tuple(PHONE_NAMES),
    screenshot_dir=SCREENSHOT_DIR,
)
