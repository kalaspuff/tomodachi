import os
import asyncio
import signal
import tomodachi
from typing import Any  # noqa
from tomodachi.transport.schedule import schedule


@tomodachi.service
class SchedulerService(object):
    name = 'test_schedule'
    uuid = None
    closer = asyncio.Future()  # type: Any
    seconds_triggered = 0

    @schedule(interval='every second')
    async def every_second(self) -> None:
        self.seconds_triggered += 1

    @schedule(interval='*/2 * * * *')
    async def every_second_minute(self) -> None:
        pass

    @schedule(timestamp='00:00')
    async def midnight(self) -> None:
        pass

    @schedule(timestamp='1:59:59')
    async def soon_two_am(self) -> None:
        pass

    @schedule(timestamp='2017-08-01 00:00:00')
    async def birthday_boy(self) -> None:
        pass

    @schedule(timestamp='2017-08-01 08:00')
    async def birthday_boy_wakeup(self) -> None:
        pass

    async def _started_service(self) -> None:
        async def _async() -> None:
            async def sleep_and_kill() -> None:
                await asyncio.sleep(8.0)
                if not self.closer.done():
                    self.closer.set_result(None)

            asyncio.ensure_future(sleep_and_kill())
            await self.closer
            os.kill(os.getpid(), signal.SIGINT)
        asyncio.ensure_future(_async())

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
