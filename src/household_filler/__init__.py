from . import cli
from .automation import NewkadastrAutomation
from .config import PROFILE
from .model import ExcelReader, ExcelRow, ReportWriter

from ..core.state import CadasterRegistry, IgnoreList, Progress, StreetScanState
from ..core.logs import trace_methods


for _cls in (NewkadastrAutomation, ExcelReader, ExcelRow, ReportWriter,
             Progress, IgnoreList, CadasterRegistry, StreetScanState):
    trace_methods(_cls)
