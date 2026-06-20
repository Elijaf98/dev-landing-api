"""Настройка логирования.

Пишем одновременно в файл (с ротацией) и в консоль. Логи запросов и ошибок
складываются в logs/app.log — это закрывает требование ТЗ «логирование в файл».
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import Settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Чтобы при повторном вызове setup_logging (например, в тестах) не плодить хендлеры.
_configured = False


def setup_logging(settings: Settings) -> None:
    global _configured
    if _configured:
        return

    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Файл с ротацией: 5 МБ на файл, держим 5 архивных копий.
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # uvicorn заводит свои хендлеры — снимаем их, чтобы не было дублей в консоли.
    for noisy in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(noisy).handlers.clear()
        logging.getLogger(noisy).propagate = True

    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
