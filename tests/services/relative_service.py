import tomodachi

from .relative_import.import_file import noop


@tomodachi.service
class RelativeService(tomodachi.Service):
    name = 'test_relative'

    start = False
    started = False
    stop = False

    async def _start_service(self) -> None:
        noop()
        self.start = True

    async def _started_service(self) -> None:
        self.started = True

    async def _stop_service(self) -> None:
        self.stop = True
