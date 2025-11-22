"""
Logging utilities for the scraper
"""

import sys
from pathlib import Path
from loguru import logger


def setup_logging(level: str = "INFO", log_file: str = None):
    """
    Setup logging configuration

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file (optional)
    """
    # Remove default handler
    logger.remove()

    # Convert string level to loguru level
    level_map = {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL"
    }

    log_level = level_map.get(level.upper(), "INFO")

    # Console handler
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan> | <level>{message}</level>",
        colorize=True
    )

    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_path,
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
            rotation="10 MB",
            retention="1 week",
            encoding="utf-8"
        )

    logger.info(f"Logging initialized with level: {log_level}")


def get_logger(name: str):
    """
    Get a logger instance for a specific module

    Args:
        name: Module name

    Returns:
        Logger instance
    """
    return logger.bind(name=name)
