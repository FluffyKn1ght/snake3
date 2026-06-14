from abc import ABC, abstractmethod
from enum import Enum
from io import TextIOWrapper
from typing import Dict
import colorama as c


class LogLevel(Enum):
    """Represents different log levels."""

    DEBUG = 0
    """Debug logs."""

    INFO = 1
    """Info logs."""

    WARN = 2
    """Warning logs."""

    ERROR = 3
    """Error logs."""

    _FATAL = 4
    """Critical error logs. This should only be used by the server."""


class BaseLogger(ABC):
    """Abstract base logger class.

    Attributes:
        level: The minimum log level that will actually be logged
    """

    _TEMPLATES: Dict[LogLevel, str] = {
        LogLevel.DEBUG: f"{c.Fore.WHITE}[DEBUG] {"{text}"}{c.Style.RESET_ALL}",
        LogLevel.INFO: f"{c.Fore.WHITE}{c.Style.BRIGHT}[INFO] {"{text}"}{c.Style.RESET_ALL}",
        LogLevel.WARN: f"{c.Fore.YELLOW}{c.Style.BRIGHT}[WARN] {"{text}"}{c.Style.RESET_ALL}",
        LogLevel.ERROR: f"{c.Fore.RED}{c.Style.BRIGHT}[ERROR] {"{text}"}{c.Style.RESET_ALL}",
        LogLevel._FATAL: f"{c.Back.RED}{c.Fore.BLACK}[FATAL] {"{text}"}{c.Style.RESET_ALL}",
    }

    _RAW_TEMPLATES: Dict[LogLevel, str] = {
        LogLevel.DEBUG: "[DEBUG] {text}",
        LogLevel.INFO: "[INFO] {text}",
        LogLevel.WARN: "[WARN] {text}",
        LogLevel.ERROR: "[ERROR] {text}",
        LogLevel._FATAL: "[FATAL] {text}",
    }

    def __init__(self, level: LogLevel) -> None:
        self.level: LogLevel = level

    def debug(self, text: str) -> None:
        """Logs a debug message.

        This is a shorthand for BaseLogger().log(text, LogLevel.DEBUG)

        Args:
            text: The text to log
        """

        self.log(text, LogLevel.DEBUG)

    def info(self, text: str) -> None:
        """Logs an info message.

        This is a shorthand for BaseLogger().log(text, LogLevel.INFO)

        Args:
            text: The text to log
        """

        self.log(text, LogLevel.INFO)

    def warn(self, text: str) -> None:
        """Logs a warning message.

        This is a shorthand for BaseLogger().log(text, LogLevel.WARN)

        Args:
            text: The text to log
        """

        self.log(text, LogLevel.WARN)

    def error(self, text: str) -> None:
        """Logs an error message.

        This is a shorthand for BaseLogger().log(text, LogLevel.ERROR)

        Args:
            text: The text to log
        """

        self.log(text, LogLevel.ERROR)

    def log(self, text: str, level: LogLevel) -> None:
        """Logs the provided text at the provided log level.

        For ease of use, shorthand functions such as BaseLogger().info() are
        provided. It is recommended to use those instead of BaseLogger().log()

        Args:
            text: The text to log
            level: The level to log the text at
        """

        if level.value >= self.level.value:
            self._print(
                BaseLogger._TEMPLATES[level].format(text=text),
                BaseLogger._RAW_TEMPLATES[level].format(text=text),
            )

    @abstractmethod
    def _print(self, text: str, raw_text: str) -> None:
        """(Private method)

        Prints the specified piece of text to the log.

        This is where the core behavior of the logger is customized.

        Args:
            text: The formatted text to log. This might have color codes mixed in.
            raw_text: The raw text to log. This will never have color codes mixed in.
        """
        pass


class PrintLogger(BaseLogger):
    """Simple logger that prints out text to the console."""

    def __init__(self, level: LogLevel) -> None:
        """Creates a new PrintLogger.

        Args:
            level: The level of the logger
        """

        super().__init__(level)

    def _print(self, text: str, raw_text: str) -> None:
        print(text)


class ForwardLogger(BaseLogger):
    """Logger that forwards text to another logger.

    Attributes:
        forward_to: Which logger to forward the text to
        name: The name to prefix all logged text with
    """

    def __init__(self, level: LogLevel, forward_to: BaseLogger, name: str) -> None:
        """Creates a new ForwardLogger.

        Args:
            level: The level of the logger
            forward_to: Which logger to forward the text to
            name: The name to prefix all logged text with
        """

        super().__init__(level)
        self.forward_to = forward_to
        self.name = name

    def log(self, text: str, level: LogLevel) -> None:
        """Logs the provided text at the provided log level.

        For ease of use, shorthand functions such as BaseLogger().info() are
        provided. It is recommended to use those instead of BaseLogger().log()

        Args:
            text: The text to log
            level: The level to log the text at
        """

        self.forward_to._print(
            BaseLogger._TEMPLATES[level].format(text=f"({self.name}) {text}"),
            BaseLogger._RAW_TEMPLATES[level].format(text=f"({self.name}) {text}"),
        )

    def _print(self, text: str, raw_text: str) -> None:
        # doesn't actually ever get called
        return super()._print(text, raw_text)


class FileLogger(BaseLogger):
    """Logger that also saves logs to a file.

    Attributes:
        file: The file handle to write logs to
    """

    def __init__(self, level: LogLevel, fpath: str) -> None:
        """Creates a new FileLogger.

        Args:
            level: The level of the logger
            fpath: The path of the log file to write logs to

        Raises:
            OSError - Failed to open log file for writing
        """

        super().__init__(level)

        try:
            self.file: TextIOWrapper = open(fpath, "w")
        except Exception as e:
            raise OSError(e)

    def _print(self, text: str, raw_text: str) -> None:
        print(text)
        self.file.write(raw_text + "\n")
