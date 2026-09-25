from ..core.profile import SessionProfile
from ..core.paths import (
    INPUT_DIR,
    LOG_DIR,
    REPORT_DIR,
    STATE_DIR,
    STREETS_DIR,
    VAR_DIR,
)


EXCEL_FILE = str(INPUT_DIR / "household_entries.xlsx")


REPORT_FILE = str(REPORT_DIR / "household_report.xlsx")


PROGRESS_FILE = str(STATE_DIR / "household_progress.json")


STREETS_STATE_FILE = str(STATE_DIR / "household_streets_state.json")


STREETS_FOUND_FILE = str(STATE_DIR / "household_streets_cadasters.txt")


CADASTERS_FILE = str(STATE_DIR / "household_cadasters.txt")


IGNORE_FILE = str(STATE_DIR / "household_ignored.txt")


LOG_FILE = str(LOG_DIR / "household.log")


ACTIONS_LOG_FILE = str(LOG_DIR / "household_actions.log")


SCREENSHOT_DIR = str(VAR_DIR / "screenshots" / "household")


START_ROW = 2


TAB_TEXT = "Ижтимоий-иқтисодий ҳолат"


TAB_FALLBACKS = ["Ижтимоий-иқтисодий", "Ижтимоий"]


LOGIN_WAIT_TIMEOUT = 60


PHONE_NAMES = ["mobile_phone", "phone", "phone_number", "tel"]


STREETS_FILE = str(STREETS_DIR / "streets_source.txt")


STREETS_FILE_FROM = 1


STREETS_FROM = 2


REPORT_HEADERS = [
    "№", "Время", "Улица", "Кадастр", "Дом", "ПИНФЛ", "Дата рождения",
    "Телефон", "Статус", "Тип ошибки", "Уведомление сайта", "Ссылка",
]


REPORT_WIDTHS = (6, 19, 28, 30, 10, 16, 14, 20, 18, 34, 60, 46)


NOT_ENTERED_HEADERS = [
    "№", "Время", "Кадастр", "Улица", "Дом", "ПИНФЛ", "Дата рождения",
    "Телефон", "Ошибка",
]


NOT_ENTERED_WIDTHS = (6, 19, 30, 28, 10, 16, 14, 20, 70)

PROFILE = SessionProfile(
    login_wait_timeout=LOGIN_WAIT_TIMEOUT,
    tab_text=TAB_TEXT,
    tab_fallbacks=tuple(TAB_FALLBACKS),
    phone_names=tuple(PHONE_NAMES),
    screenshot_dir=SCREENSHOT_DIR,
)
