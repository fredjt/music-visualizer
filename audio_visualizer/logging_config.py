"""
Logging Configuration

Provides a structured logging system for the audio visualizer.
Supports multiple verbosity levels: ERROR, WARNING, INFO, DEBUG.

Usage:
    from audio_visualizer.logging_config import logger

    logger.error("Something went wrong")
    logger.warning("A warning")
    logger.info("Informational message")
    logger.debug("Debug details")
"""

import logging
import sys

# Log levels
ERROR = logging.ERROR
WARNING = logging.WARNING
INFO = logging.INFO
DEBUG = logging.DEBUG

# Default log level (can be overridden via set_level)
_default_level = INFO

# Color codes for terminal output
COLORS = {
    "ERROR": "\033[91m",  # Red
    "WARNING": "\033[93m",  # Yellow
    "INFO": "\033[0m",  # Reset
    "DEBUG": "\033[96m",  # Cyan
    "RESET": "\033[0m",  # Reset
}


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels."""

    def format(self, record):
        color = COLORS.get(record.levelname, "")
        reset = COLORS["RESET"]
        record.levelname = f"{color}{record.levelname[:4]}{reset}"
        return super().format(record)


def get_logger(name: str = "audio_visualizer") -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (used for module-specific loggers)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(_default_level)

    # Create console handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(_default_level)

    # Create formatter
    formatter = ColoredFormatter(
        "%(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False  # Don't propagate to root logger

    return logger


def set_level(level: int) -> None:
    """
    Set the global log level.

    Args:
        level: Log level (logging.ERROR, WARNING, INFO, DEBUG)
    """
    global _default_level
    _default_level = level

    # Update all existing loggers
    for name in logging.Logger.manager.loggerDict:
        if name.startswith("audio_visualizer"):
            logger = logging.getLogger(name)
            for handler in logger.handlers:
                handler.setLevel(level)
            logger.setLevel(level)


# Create default logger instance
logger = get_logger()
