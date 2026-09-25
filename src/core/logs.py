import contextlib
import functools
import logging
import time

from . import settings


logger = logging.getLogger("mahalla")
actions = logging.getLogger("mahalla.actions")


def configure(log_file: str, actions_file: str) -> None:
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(asctime)s | %(message)s",
                                               datefmt="%H:%M:%S"))
        logger.addHandler(console)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(file_handler)
    if not actions.handlers:
        actions.setLevel(logging.DEBUG)
        handler = logging.FileHandler(actions_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s.%(msecs)03d | %(levelname)-7s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"))
        actions.addHandler(handler)
        actions.propagate = False


def brief(value, limit: int = None) -> str:
    """Короткое однострочное представление значения для лога."""
    limit = settings.TRACE_VALUE_LIMIT if limit is None else limit
    if value is None:
        return "—"
    if isinstance(value, str):
        text = " ".join(value.split())
        return text[:limit] + ("…" if len(text) > limit else "") if text else '""'
    if isinstance(value, (list, tuple, set)):
        parts = [brief(v, 60) for v in list(value)[:6]]
        more = f", +{len(value) - 6}" if len(value) > 6 else ""
        return "[" + ", ".join(parts) + more + "]"
    if isinstance(value, dict):
        parts = [f"{k}={brief(v, 60)}" for k, v in list(value.items())[:6]]
        more = f", +{len(value) - 6}" if len(value) > 6 else ""
        return "{" + ", ".join(parts) + more + "}"
    text = str(value)
    return text[:limit] + ("…" if len(text) > limit else "")


def _call_text(fn, args, kwargs) -> str:
    params = list(args)

    if params and not isinstance(params[0], (int, float, str, bytes)) \
            and fn.__qualname__.split(".")[0] == type(params[0]).__name__:
        params = params[1:]
    parts = []
    names = getattr(fn, "__code__", None)
    argnames = list(names.co_varnames[1:names.co_argcount]) if names else []
    for name, value in zip(argnames, params):
        if name in ("self", "cls"):
            continue
        parts.append(f"{name}={brief(value)}")
    if len(params) > len(argnames):
        for value in params[len(argnames):]:
            parts.append(brief(value))
    for name, value in kwargs.items():
        parts.append(f"{name}={brief(value)}")
    return ", ".join(parts)


def _result_text(result) -> str:
    if result is None:
        return "None"
    if isinstance(result, bool) or isinstance(result, (int, float, str)):
        return brief(result)
    if isinstance(result, (list, tuple)):
        head = ", ".join(brief(v, 80) for v in list(result)[:3])
        more = f", +{len(result) - 3}" if len(result) > 3 else ""
        return f"{type(result).__name__}[{len(result)}] = [{head}{more}]"
    if isinstance(result, dict):
        head = ", ".join(f"{k}={brief(v, 80)}" for k, v in list(result.items())[:3])
        more = f", +{len(result) - 3}" if len(result) > 3 else ""
        return f"dict[{len(result)}] = {{{head}{more}}}"
    return brief(str(result), 200)


def log_action(fn):
    """Логирует вход, выход, длительность в секундах и ошибку каждого вызова."""
    name = fn.__qualname__

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if name.endswith(".js") and not settings.TRACE_JS:
            return fn(*args, **kwargs)
        call = _call_text(fn, args, kwargs)
        started = time.perf_counter()
        actions.debug(f"→ {name}({call})")
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            elapsed = time.perf_counter() - started
            actions.error(f"✖ {name}({call}) — {type(exc).__name__}: "
                          f"{brief(str(exc), 200)} | {elapsed:.2f} с")
            raise
        elapsed = time.perf_counter() - started
        actions.info(f"← {name}({call}) = {_result_text(result)} | {elapsed:.2f} с")
        return result

    wrapper.__traced__ = True
    return wrapper


def trace_methods(cls) -> None:
    """Оборачивает все методы класса (кроме служебных) трассировкой."""
    skip = {"__init__", "__del__", "close", "quit"}
    for name, obj in list(vars(cls).items()):
        if not callable(obj) or isinstance(obj, (staticmethod, classmethod, property)):
            continue
        if name.startswith("__") or name in skip or getattr(obj, "__traced__", False):
            continue
        setattr(cls, name, log_action(obj))


@contextlib.contextmanager
def timed(action_name: str, detail: str = "", quiet: bool = False):
    """
    Замер этапа алгоритма. Пишет в основной лог начало/конец и длительность,
    подробности — в actions-лог.
    """
    label = f"{action_name}" + (f" ({detail})" if detail else "")
    if not quiet:
        logger.info(f"▶ {label}")
    actions.debug(f"СТАРТ ЭТАПА: {label}")
    started = time.perf_counter()
    try:
        yield
    except Exception as exc:
        elapsed = time.perf_counter() - started
        logger.error(f"■ {label}: ОШИБКА после {elapsed:.2f} с — "
                     f"{type(exc).__name__}: {brief(str(exc), 200)}")
        actions.error(f"ОШИБКА ЭТАПА: {label} | {elapsed:.2f} с | "
                      f"{type(exc).__name__}: {brief(str(exc), 300)}")
        raise
    else:
        elapsed = time.perf_counter() - started
        logger.info(f"■ {label}: готово за {elapsed:.2f} с")
        actions.info(f"КОНЕЦ ЭТАПА: {label} | {elapsed:.2f} с")
