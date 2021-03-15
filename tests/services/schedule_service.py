import asyncio
import os
import signal

import tomodachi
from tomodachi.transport.schedule import heartbeat, schedule


@tomodachi.service
class SchedulerService(tomodachi.Service):
    name = "test_schedule"
    uuid = None
    closer: asyncio.Future = asyncio.Future()
    seconds_triggered = 0
    third_seconds_triggered = 0

    @heartbeat
    async def every_second(self) -> None:
        self.seconds_triggered += 1

    @schedule(interval="3 seconds")
    async def every_third_second(self) -> None:
        self.third_seconds_triggered += 1

    @schedule(interval="*/2 * * * *")
    async def every_second_minute(self) -> None:
        pass

    @schedule(timestamp="00:00")
    async def midnight(self) -> None:
        pass

    @schedule(timestamp="01:59:59")
    async def soon_two_am(self) -> None:
        pass

    @schedule(timestamp="2017-08-01 00:00:00", timezone="Europe/Stockholm")
    async def birthday_boy(self) -> None:
        pass

    @schedule(timestamp="2017-08-01 08:00", timezone="Europe/Stockholm")
    async def birthday_boy_wakeup(self) -> None:
        pass

    @schedule(interval="*/15 8-18 * * mon-fri", timezone="GMT +01:00")
    async def work_hours_in_gmt_1(self) -> None:
        pass

    async def _started_service(self) -> None:
        async def _async() -> None:
            async def sleep_and_kill() -> None:
                await asyncio.sleep(8.0)
                if not self.closer.done():
                    self.closer.set_result(None)

            task = asyncio.ensure_future(sleep_and_kill())
            await self.closer
            if not task.done():
                task.cancel()
            os.kill(os.getpid(), signal.SIGINT)

        asyncio.ensure_future(_async())

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)
