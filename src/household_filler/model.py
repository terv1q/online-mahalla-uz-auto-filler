import openpyxl

from ..core.logs import logger
from ..core.selectors import (
    HEADER_FILL_COLOR,
    HEADER_FONT_COLOR,
    PINFL_SPLIT_RE,
    REPORT_SHEETS,
    SHEET_NOT_ENTERED,
)
from ..core.settings import (
    EXCEL_DATE_MAX,
    EXCEL_DATE_MIN,
    NOTICE_TEXT_LIMIT,
    PINFL_LENGTH,
)
from ..core.utils import (
    birth_from_pinfl,
    digits_only,
    generate_uzbek_phone,
    normalize_code,
    normalize_date,
    url_params,
)
from .config import (
    NOT_ENTERED_HEADERS,
    NOT_ENTERED_WIDTHS,
    REPORT_HEADERS,
    REPORT_WIDTHS,
    START_ROW,
)
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from openpyxl.styles import Alignment, Font, PatternFill
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class ExcelRow:
    """Строка household_entries.xlsx: A № | B КАДАСТР | C ПИНФЛ | D УЛИЦА | E ДОМ | F ДР1 | G ПИНФЛ2 | H ДР2."""
    row_index: int
    number: str = ""
    cadaster: str = ""
    pinfl_raw: str = ""
    street_url: str = ""
    house: str = ""
    birth1: str = ""
    pinfl2_raw: str = ""
    birth2: str = ""
    phone: str = ""
    street_name: str = ""

    @property
    def code(self) -> str:
        """Ключ прогресса/отчёта — кадастровый номер."""
        return normalize_code(self.cadaster)

    def pinfl_candidates(self) -> List[Tuple[str, str]]:
        """
        Пары (ПИНФЛ, дата рождения) в порядке проверки:
        сначала колонка C + F, затем G + H; внутри колонки — все значения,
        перечисленные через запятую. Дата берётся из столбца, а если её нет —
        вычисляется из самого ПИНФЛ.
        """
        pairs: List[Tuple[str, str]] = []
        sources = ((self.pinfl_raw, self.birth1), (self.pinfl2_raw, self.birth2))
        for raw, birth in sources:
            explicit = normalize_date(birth)
            for chunk in PINFL_SPLIT_RE.split(raw or ""):
                digits = digits_only(chunk)
                if len(digits) < PINFL_LENGTH:
                    continue
                digits = digits[:PINFL_LENGTH]
                derived = birth_from_pinfl(digits)
                for date in (explicit, derived):
                    if not date:
                        continue
                    pair = (digits, date)
                    if pair not in pairs:
                        pairs.append(pair)
        return pairs

    def has_pinfl(self) -> bool:
        return bool(self.pinfl_candidates())

    def get_formatted_phone(self) -> str:
        return (self.phone or "").strip()

    def street_label(self) -> str:
        if self.street_name:
            return self.street_name
        params = url_params(self.street_url)
        street_id = params.get("street_id", "")
        return f"street_id={street_id}" if street_id else (self.street_url or "—")


class ExcelReader:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {self.file_path}")

    def read_rows(self, start_row: int = START_ROW) -> List[ExcelRow]:
        workbook = openpyxl.load_workbook(self.file_path, data_only=True)
        worksheet = workbook.active
        rows: List[ExcelRow] = []
        seen = set()
        duplicates = 0
        first = max(2, start_row)
        skipped = first - 2
        for idx in range(first, worksheet.max_row + 1):
            try:
                row = ExcelRow(
                    row_index=idx,
                    number=self._cell(worksheet, idx, 1),
                    cadaster=self._cell(worksheet, idx, 2),
                    pinfl_raw=self._cell(worksheet, idx, 3),
                    street_url=self._cell(worksheet, idx, 4),
                    house=self._cell(worksheet, idx, 5),
                    birth1=self._cell(worksheet, idx, 6),
                    pinfl2_raw=self._cell(worksheet, idx, 7),
                    birth2=self._cell(worksheet, idx, 8),
                )
            except Exception as exc:
                logger.warning(f"Excel, строка {idx}: ошибка чтения ({exc})")
                continue
            if not row.code:
                continue
            if row.code in seen:
                duplicates += 1
                continue
            seen.add(row.code)
            row.phone = generate_uzbek_phone()
            rows.append(row)
        workbook.close()
        logger.info(f"Excel: строк {len(rows)}, старт со строки листа {first}"
                    + (f", пропущено строк {skipped}" if skipped else "")
                    + (f", дубликатов пропущено {duplicates}" if duplicates else ""))
        return rows

    @staticmethod
    def _cell(worksheet, row: int, col: int) -> str:
        value = worksheet.cell(row, col).value
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y")
        if isinstance(value, str) and value.startswith("="):
            return ""
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if isinstance(value, int) and EXCEL_DATE_MIN < value < EXCEL_DATE_MAX:
            return (datetime(1899, 12, 30) + timedelta(days=value)).strftime("%d.%m.%Y")
        return str(value).strip()


class ReportWriter:
    def __init__(self, path: str):
        self.path = Path(path)
        if self.path.exists():
            try:
                self.wb = openpyxl.load_workbook(self.path)
            except Exception as exc:
                logger.warning(f"Отчёт не открылся ({exc}), создан новый")
                self.wb = self._new_workbook()
        else:
            self.wb = self._new_workbook()

        for name in REPORT_SHEETS:
            if name not in self.wb.sheetnames:
                self._create_sheet(name)
        self.save()

    @staticmethod
    def _new_workbook():
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        return wb

    def _create_sheet(self, name: str) -> None:
        ws = self.wb.create_sheet(name)
        headers = NOT_ENTERED_HEADERS if name == SHEET_NOT_ENTERED else REPORT_HEADERS
        widths = NOT_ENTERED_WIDTHS if name == SHEET_NOT_ENTERED else REPORT_WIDTHS
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True, color=HEADER_FONT_COLOR)
            cell.fill = PatternFill("solid", fgColor=HEADER_FILL_COLOR)
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for idx, width in enumerate(widths):
            ws.column_dimensions[openpyxl.utils.get_column_letter(idx + 1)].width = width
        ws.freeze_panes = "A2"

    def add(self, sheet: str, street: str, code: str, house: str, pinfl: str,
            birth: str, phone: str, status: str, error_type: str = "",
            notice: str = "", url: str = "") -> None:
        ws = self.wb[sheet]
        ws.append([ws.max_row, datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                   street, code, house, pinfl, birth, phone, status, error_type,
                   (notice or "")[:NOTICE_TEXT_LIMIT], url])
        ws.cell(ws.max_row, 11).alignment = Alignment(wrap_text=True, vertical="top")
        self.save()

    def add_not_entered(self, code: str, street: str, house: str, pinfl: str,
                        birth: str, phone: str, error: str) -> None:
        ws = self.wb[SHEET_NOT_ENTERED]
        ws.append([ws.max_row, datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                   code, street, house, pinfl, birth, phone,
                   (error or "")[:NOTICE_TEXT_LIMIT]])
        ws.cell(ws.max_row, 9).alignment = Alignment(wrap_text=True, vertical="top")
        self.save()

    def save(self) -> None:
        try:
            self.wb.save(self.path)
        except PermissionError:
            alt = self.path.with_name(
                f"{self.path.stem}_{datetime.now().strftime('%H%M%S')}{self.path.suffix}")
            try:
                self.wb.save(alt)
                logger.warning(f"Отчёт занят, сохранён как {alt}")
                self.path = alt
            except Exception as exc:
                logger.error(f"Отчёт не сохранён: {exc}")
        except Exception as exc:
            logger.error(f"Отчёт не сохранён: {exc}")
