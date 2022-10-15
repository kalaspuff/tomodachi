import asyncio

import tomodachi


class NonDecoratedService(object):
    name = "test_non_decorated"

    async def _started_service(self) -> None:
        await asyncio.sleep(0.1)
        tomodachi.exit()
