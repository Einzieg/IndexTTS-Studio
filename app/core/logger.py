from __future__ import annotations

import logging
from pathlib import Path


_CONFIGURED = False


def configure_logging(log_dir: Path, level: str = "INFO") -> logging.Logger:
    global _CONFIGURED

    logger = logging.getLogger("indextts_studio")
    if _CONFIGURED:
        logger.setLevel(level)
        return logger

    log_dir.mkdir(parents=True, exist_ok=True)
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_dir / "indextts-studio.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    _CONFIGURED = True
    return logger


def get_logger(name: str = "indextts_studio") -> logging.Logger:
    return logging.getLogger(name)
