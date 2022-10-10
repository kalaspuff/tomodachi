import asyncio
from typing import Any

from run_test_service_helper import start_service


def test_schedule_service(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service("tests/services/schedule_service.py", monkeypatch, loop=loop)

    assert services is not None
    assert len(services) == 1
    instance = services.get("test_schedule")
    assert instance is not None

    assert instance.uuid is not None

    async def _async(loop: Any) -> None:
        seconds = instance.seconds_triggered
        third_seconds_triggered = instance.third_seconds_triggered

        await asyncio.sleep(1.5)

        assert instance.seconds_triggered > seconds
        assert instance.third_seconds_triggered == third_seconds_triggered

        seconds = instance.seconds_triggered

        await asyncio.sleep(4)

        assert instance.seconds_triggered > seconds
        assert instance.third_seconds_triggered > third_seconds_triggered

    loop.run_until_complete(_async(loop))
    instance.stop_service()
    loop.run_until_complete(future)
