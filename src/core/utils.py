import random
import re

from .logs import logger
from .selectors import (
    ERR_ACTIVE,
    ERR_DEAD,
    ERR_EXISTS,
    STREET_CHAR_MAP,
    UNKNOWN_STREET_MARKERS,
    UZ_PHONE_PREFIXES,
)
from .settings import BASE_URL
from html import unescape
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse


STREET_LINK_RE = re.compile(
    r'<a[^>]+href="([^"]*survey_homes_street[^"]*)"[^>]*>(.*?)</a>', re.S)


def normalize_code(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", "", str(value).strip()).strip(":")


def normalize_date(value: str) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", text):
        return text
    match = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T].*)?", text)
    if match:
        year, month, day = match.groups()
        return f"{int(day):02d}.{int(month):02d}.{year}"
    match = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", text)
    if match:
        day, month, year = match.groups()
        return f"{int(day):02d}.{int(month):02d}.{year}"
    return None


def url_params(url: str) -> Dict[str, str]:
    try:
        return dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
    except Exception:
        return {}


def is_empty_id(value) -> bool:
    return str(value).strip().lower() in ("", "0", "none", "null", "undefined")


def merge_url_params(url: str, extra: Dict[str, str], force: bool = True) -> str:
    try:
        parsed = urlparse(url)
        params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        for key, value in extra.items():
            if is_empty_id(value):
                continue
            if force or is_empty_id(params.get(key)):
                params[key] = str(value)
        return urlunparse(parsed._replace(query=urlencode(params)))
    except Exception:
        return url


def parse_streets_file(path: str) -> List[dict]:
    """
    Разбирает сохранённую со страницы сводную таблицу улиц (HTML).
    Возвращает [{'name', 'url', 'street_id'}] без «номаълум» и street_id=0.
    """
    file = Path(path)
    if not file.exists():
        return []
    try:
        markup = file.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.warning(f"Список улиц не прочитан ({exc})")
        return []

    streets: List[dict] = []
    seen = set()
    for href, raw_name in STREET_LINK_RE.findall(markup):
        url = urljoin(BASE_URL, unescape(href).replace("&amp;", "&"))
        params = url_params(url)
        street_id = params.get("street_id", "")
        name = re.sub(r"<[^>]+>", " ", unescape(raw_name))
        name = re.sub(r"\s+", " ", name).strip()
        low = name.lower()
        if street_id in ("", "0"):
            logger.info(f"Улица пропущена (номер 0): {name or 'без названия'}")
            continue
        if any(marker in low for marker in UNKNOWN_STREET_MARKERS):
            logger.info(f"Улица пропущена («номаълум»): {name}")
            continue
        if street_id in seen:
            continue
        seen.add(street_id)
        streets.append({"name": name, "url": url, "street_id": street_id})
    logger.info(f"Список улиц: файл {path} — улиц {len(streets)}")
    return streets


def norm_street(text: str) -> str:
    value = (text or "").lower().translate(STREET_CHAR_MAP)
    value = re.sub(r"^\s*(ул\.?|улица|кўча|куча|ko'cha|kocha|street)\s*", "", value)
    value = re.sub(r"[^\w/() ]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def norm_text(text: str) -> str:
    return " ".join((text or "").split()).lower().replace("ʼ", "'").replace("‘", "'")


def digits_only(text: str) -> str:
    return "".join(c for c in (text or "") if c.isdigit())


def birth_from_pinfl(pinfl: str) -> Optional[str]:
    """ДД.ММ.ГГГГ из самого ПИНФЛ (1-я цифра — век, 2-7 — дата)."""
    pinfl = digits_only(pinfl)
    if len(pinfl) < 7:
        return None
    try:
        day, month = pinfl[1:3], pinfl[3:5]
        year_short = int(pinfl[5:7])
        year = 1900 + year_short if pinfl[0] in ("3", "4") else 2000 + year_short
        if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            return f"{day}.{month}.{year}"
    except ValueError:
        return None
    return None


def generate_uzbek_phone() -> str:
    """Реалистичный узбекский мобильный номер: +998(XX)XXX-XX-XX."""
    prefix = random.choice(UZ_PHONE_PREFIXES)
    rest = "".join(str(random.randint(0, 9)) for _ in range(7))
    return f"+998({prefix}){rest[:3]}-{rest[3:5]}-{rest[5:7]}"


def classify_error(text: str) -> Optional[str]:
    """Определяет известный тип ошибки сайта по тексту уведомления."""
    low = norm_text(text).replace("’", "'").replace("ʻ", "'")
    if ("тизимда мавжуд" in low or "қайта киритиб бўлмайди" in low
            or "tizimda mavjud" in low):
        return ERR_EXISTS
    if "topilmadi" in low or "топилмади" in low:
        is_dead = ("vafot" in low or "status = 2" in low or "status=2" in low
                   or "status_name = vafot" in low)
        is_active = ("aktiv" in low or "status = 1" in low or "status=1" in low)
        if is_dead:
            return ERR_DEAD
        if is_active:
            return ERR_ACTIVE
    return None
