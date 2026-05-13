import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os


_LOGGER = None


class _MilodoFormatter(logging.Formatter):
    def format(self, record):
        record.module_name = record.name
        return super().format(record)


def setup_logger(name="milodo", log_dir=".milodo"):
    global _LOGGER

    if _LOGGER is not None:
        return _LOGGER

    debug_enabled = os.getenv("MILODO_DEBUG") == "1"
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    logger.propagate = False

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    formatter = _MilodoFormatter(
        "[%(asctime)s] [%(levelname)s] [%(module_name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path / "milodo.log",
        maxBytes=5 * 1024 * 1024,  # 5 Mo
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    _LOGGER = logger
    return _LOGGER


def log_info(message):
    setup_logger().info(message)


def log_warn(message):
    setup_logger().warning(message)


def log_error(message):
    setup_logger().error(message)


def log_debug(message):
    setup_logger().debug(message)
