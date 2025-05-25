import datetime
import json
import platform
from functools import cached_property
from pathlib import Path
from threading import Lock, local
from typing import Any, Dict

from aiologger import Logger
from aiologger.formatters.json import ExtendedJsonFormatter
from aiologger.handlers.files import AsyncFileHandler
from aiologger.handlers.streams import AsyncStreamHandler
from aiologger.records import LogRecord
from pydantic import PrivateAttr


from . import EnvSettings

_async_logger_lock = Lock()
_async_logger_instance = None


class ContextAwareFormatter(ExtendedJsonFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._local = local()

    @property
    def context(self) -> Dict[str, Any]:
        if not hasattr(self._local, 'context'):
            self._local.context = {}
        return self._local.context

    def add_context(self, **values: Dict[str, Any]):
        self.context.update(values)

    def format(self, record: LogRecord) -> str:
        record_dict = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created,
                tz=datetime.timezone.utc
            ).isoformat(),
            "severity": record.levelname,
            "message": record.msg,
            "logger": record.name,
            "location": f"{record.pathname}:{record.lineno}",
        }
        record_dict.update({"context": self.context.copy()})
        return self.serializer(record_dict)


class AsyncLogger(EnvSettings):
    APP_NAME: str = "my_app"
    LOG_PATH: str = "run_logs"
    LOG_LEVEL: str = "INFO"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024
    LOG_BACKUP_COUNT: int = 5

    _logger: Logger = PrivateAttr()
    _formatter: ContextAwareFormatter = PrivateAttr()

    def prefix(self):
        return "LOG_"

    def __new__(cls, *args, **kwargs):
        global _async_logger_instance, _async_logger_lock
        with _async_logger_lock:
            if not _async_logger_instance:
                _async_logger_instance = super().__new__(cls)
            return _async_logger_instance

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._formatter = ContextAwareFormatter(
            serializer=lambda obj: json.dumps(
                obj,
                default=str,
                ensure_ascii=False,
                indent=2 if self.LOG_LEVEL == "DEBUG" else None
            )
        )
        self.__configure_logger()

    def __configure_logger(self):
        self._logger = Logger(
            name=self.APP_NAME,
            level=self.LOG_LEVEL
        )

        # 文件处理器（始终异步）
        file_handler = AsyncFileHandler(
            filename=str(self.__log_file),
            encoding="utf-8"
        )
        file_handler.formatter = self._formatter
        self._logger.add_handler(file_handler)

        # 控制台处理器（Windows特殊处理）
        if platform.system() == "Windows":
            pass
        else:
            console_handler = AsyncStreamHandler()
            console_handler.formatter = self._formatter
            self._logger.add_handler(console_handler)

    @property
    def __log_dir(self) -> Path:
        log_dir = Path(self.LOG_PATH)
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    @property
    def __log_file(self) -> Path:
        return self.__log_dir / f"{self.APP_NAME}.log"

    @cached_property
    def raw_logger(self) -> Logger:
        return self._logger

    @classmethod
    def get_logger(cls, **values: Dict[str, Any]) -> "AsyncLogger":
        logger = cls()
        logger.set_context(**values)
        return logger

    def set_context(self, **values: Dict[str, Any]) -> None:
        self._formatter.add_context(**values)

    async def shutdown(self):
        await self._logger.shutdown()
        self._formatter.context.clear()
