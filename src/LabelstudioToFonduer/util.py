# -*- coding: utf-8 -*-
"""Logger and formatter"""
import logging


class CustomFormatter(logging.Formatter):
    def __init__(self, fmt: str, datefmt) -> None:
        super().__init__(fmt, datefmt)
        self.fmt = fmt
        self.white = "\x1b[0;20m"
        self.grey = "\x1b[2;37;20m"
        self.yellow = "\x1b[33;20m"
        self.red = "\x1b[31;20m"
        self.bold_red = "\x1b[31;1m"
        self.reset = "\x1b[0m"
        self.green = "\x1b[2;32;2m"

        self.colors = {
            logging.DEBUG: self.white,
            logging.INFO: self.grey,
            logging.WARNING: self.yellow,
            logging.ERROR: self.red,
            logging.CRITICAL: self.bold_red,
        }

    def colorize(self, record_level: int) -> str:
        """Colorize the log record.

        Args:
            record_level (int): Level of the log record.
        Returns:
            str: formatted record.
        """
        colorized = self.fmt.replace(
            "%(levelname)s", self.colors[record_level] + "%(levelname)s" + self.reset
        )
        colorized = colorized.replace("%(asctime)s", self.green + "%(asctime)s" + self.reset)
        colorized = colorized.replace("%(name)s", self.grey + "%(name)s" + self.reset)
        colorized = colorized.replace("%(lineno)s", self.grey + "%(lineno)s" + self.reset)

        if "✓" in colorized:
            colorized.replace("✓", self.green + "✓" + self.reset)
        if "✗" in colorized:
            colorized.replace("✗", self.red + "✗" + self.reset)
        return colorized

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record.

        Args:
            record (logging.LogRecord): Record to be formatted.

        Returns:
            str: formatted record.
        """
        log_fmt = self.colorize(record.levelno)

        formatter = logging.Formatter(log_fmt, datefmt=self.datefmt)
        return formatter.format(record)


def init_logger(name: str) -> logging.Logger:
    """Initialize a logger.

    Args:
        name (str): Name of the logger.

    Returns:
        logging.Logger: Initialized logger.
    """
    logger = logging.getLogger(name)

    # Create handlers
    consol_handler = logging.StreamHandler()
    file_handler = logging.FileHandler("app.log")

    consol_handler.setLevel(logging.DEBUG)
    file_handler.setLevel(logging.INFO)

    # Create formatters and add it to handlers
    consol_handler.setFormatter(
        CustomFormatter(
            fmt="[%(asctime)s][%(levelname)s] %(name)s:%(lineno)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s][%(levelname)s] %(name)s:%(lineno)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    # Add handlers to the logger
    logger.addHandler(consol_handler)
    logger.addHandler(file_handler)
    return logger


def green(string: str) -> str:
    return "\x1b[32;1m" + string + "\x1b[0m"


def red(string) -> str:
    return "\x1b[31;1m" + string + "\x1b[0m"


def highlight_span(text: str, from_: int, to: int) -> str:
    """Highlight a given span in a text green.

    Args:
        text (str): Text to highlight.
        from_ (int): From index.
        to (int): To index.

    Returns:
        str: Highlighted text.
    """
    text_highlight = text[:from_] + "\x1b[6;30;42m" + text[from_:to] + "\x1b[0m" + text[to:]
    return text_highlight
