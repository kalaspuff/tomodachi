import asyncio
import logging
import os
from logging.handlers import WatchedFileHandler

import tomodachi


@tomodachi.service
class LoggingService(tomodachi.Service):
    name = "test_logging"
    log_path = "/tmp/7815c7d6-5637-4bfd-ad76-324f4329a6b8.log"

    def __init__(self) -> None:
        try:
            os.remove(self.log_path)
        except OSError:
            pass

    def log_setup(self, filename: str) -> None:
        wfh = WatchedFileHandler(filename=filename)
        wfh.setLevel(logging.DEBUG)
        wfh.setFormatter(tomodachi.logging.JSONFormatter)
        tomodachi.logging.getLogger().addHandler(wfh)

    async def _start_service(self) -> None:
        self.log_setup(filename=self.log_path)
        self.log("_start_service", level=logging.INFO)

    async def _started_service(self) -> None:
        self.log("_started_service", level=logging.INFO)
        await asyncio.sleep(0.1)
        tomodachi.exit()

    async def _stop_service(self) -> None:
        self.log("_stop_service", level=logging.INFO)
