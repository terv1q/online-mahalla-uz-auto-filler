from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class SessionProfile:
    login_wait_timeout: int
    tab_text: str
    tab_fallbacks: Tuple[str, ...]
    phone_names: Tuple[str, ...]
    screenshot_dir: str
