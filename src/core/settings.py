from .paths import BROWSER_DIR


BASE_URL = "https://www.online-mahalla.uz"


TRACE_JS = True


TRACE_VALUE_LIMIT = 160


HEADLESS = False


USER_DATA_DIR = str(BROWSER_DIR / "edge_profile_v3")


PROFILE_NAME = "automation_profile"


SAVE_SCREENSHOTS = True


MAX_EXTRA_WINDOWS = 0


PINFL_LENGTH = 14


STREET_MATCH_THRESHOLD = 0.75


NOTICE_TEXT_LIMIT = 2000


HTTP_ERRORS_LIMIT = 5


EMPTY_VALUES = {"", "-", "—", "–"}


EXCEL_DATE_MIN = 40000


EXCEL_DATE_MAX = 60000
