from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


DATA_DIR = PROJECT_ROOT / "data"


INPUT_DIR = DATA_DIR / "input"


STREETS_DIR = DATA_DIR / "streets"


VAR_DIR = PROJECT_ROOT / "var"


STATE_DIR = VAR_DIR / "state"


REPORT_DIR = VAR_DIR / "reports"


LOG_DIR = VAR_DIR / "logs"


BROWSER_DIR = PROJECT_ROOT / "browsers"
