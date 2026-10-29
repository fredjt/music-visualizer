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

    # Avoid adding a console handler twice. A file handler attached via
    # attach_file_handler does not count as a console handler.
    if any(not isinstance(h, logging.FileHandler) for h in logger.handlers):
        return logger

    logger.setLevel(_default_level)

    # Create console handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(_default_level)
    handler._av_console = True  # marker: owned by this module (see set_level)

    # Create formatter
    formatter = ColoredFormatter(
        "%(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False  # Don't propagate to root logger

    return logger


def attach_file_handler(path: str, level: int = DEBUG) -> logging.FileHandler:
    """
    Attach a file handler that tees log output to a file.

    The file handler keeps its own level (DEBUG by default) so that
    ``--log-file`` captures full detail even when the console is
    quieter (e.g. with ``--quiet``). Console level changes via
    ``set_level`` do not affect file handlers.

    Args:
        path: File to append log records to.
        level: Minimum level recorded to the file.

    Returns:
        The attached FileHandler.
    """
    target = logging.getLogger("audio_visualizer")
    if not target.handlers:  # ensure the default logger exists
        get_logger()
    handler = logging.FileHandler(path, mode="a", encoding="utf-8")
    handler.setLevel(level)
    handler._av_log_file = True  # marker: owned by this module (see set_level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    for logger in logging.Logger.manager.loggerDict.values():
        if isinstance(logger, logging.Logger) and logger.name.startswith("audio_visualizer"):
            logger.addHandler(handler)
    return handler


def set_level(level: int) -> None:
    """
    Set the global log level.

    File handlers (see attach_file_handler) keep their own level so a
    log file can capture DEBUG detail while the console stays quieter.

    Args:
        level: Log level (logging.ERROR, WARNING, INFO, DEBUG)
    """
    global _default_level
    _default_level = level

    # Update all existing loggers. Only handlers created by this module
    # (marked _av_console / _av_log_file) are touched: third-party
    # handlers (e.g. pytest's caplog handlers, which are shared across
    # tests and stay attached to our loggers) keep whatever level their
    # owner manages.
    for name in logging.Logger.manager.loggerDict:
        if name.startswith("audio_visualizer"):
            logger = logging.getLogger(name)
            our_levels = []
            for handler in logger.handlers:
                if getattr(handler, "_av_console", False):
                    handler.setLevel(level)
                    our_levels.append(level)
                elif getattr(handler, "_av_log_file", False):
                    our_levels.append(handler.level)
            # The logger-level gate must stay at the quietest of our
            # handlers, or a DEBUG file handler would be starved when the
            # console is set to a higher level (e.g. --quiet).
            logger.setLevel(min(our_levels) if our_levels else level)


# Create default logger instance
logger = get_logger()
