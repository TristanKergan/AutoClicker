"""Application logging configuration.

All logs go to a file under ``~/.cache/autoclicker``. No console handler is
attached, so the GUI never pops a terminal window.
"""
from __future__ import annotations

import logging
import os

APP_NAME = "autoclicker"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the application logger.

    Safe to call multiple times — it only attaches handlers once.
    """
    logger = logging.getLogger(APP_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", APP_NAME)
    try:
        os.makedirs(cache_dir, exist_ok=True)
        log_path = os.path.join(cache_dir, f"{APP_NAME}.log")
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(file_handler)
    except OSError as exc:  # pragma: no cover - filesystem issue
        # If we cannot write a log file, fail silently — never crash the GUI.
        logging.getLogger("stderr").warning("Logging disabled: %s", exc)

    return logger


log = setup_logging()
