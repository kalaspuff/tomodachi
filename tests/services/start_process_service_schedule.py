import asyncio

import tomodachi
from tomodachi.transport.schedule import schedule


@tomodachi.service
class SchedulerService(tomodachi.Service):
    name = "test_schedule"
    uuid = None
    closer: asyncio.Future
    function_order = []

    @schedule(interval="5 seconds", immediately=True)
    async def every_fifth_second(self) -> None:
        self.function_order.append("every_fifth_second")

    async def _start_service(self) -> None:
        self.closer = asyncio.Future()
        await asyncio.sleep(2)
        self.function_order.append("_start_service")

    async def _started_service(self) -> None:
        self.function_order.append("_started_service")

        async def _async() -> None:
            async def sleep_and_kill() -> None:
                await asyncio.sleep(12.0)
                if not self.closer.done():
                    self.closer.set_result(None)

            task = asyncio.ensure_future(sleep_and_kill())
            await self.closer
            if not task.done():
                task.cancel()
            tomodachi.exit()

        asyncio.ensure_future(_async())

    def stop_service(self) -> None:
        self.function_order.append("stop_service")
        if not self.closer.done():
            self.closer.set_result(None)

    async def _stopping_service(self) -> None:
        self.function_order.append("_stopping_service")

    async def _stop_service(self) -> None:
        self.function_order.append("_stop_service")
